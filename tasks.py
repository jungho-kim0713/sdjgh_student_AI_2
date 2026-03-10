"""
Celery 백그라운드 작업 시스템

문서 업로드 후 벡터화를 백그라운드에서 비동기로 처리합니다.
대용량 PDF도 사용자는 즉시 응답을 받고, 처리는 백그라운드에서 진행됩니다.
"""

import os
import datetime
from celery import Celery
from flask import Flask

from services.file_service import extract_text_from_file
from services.chunking_service import chunk_text
from services.embedding_service import generate_embeddings_batch

# Celery 앱 초기화
celery = Celery(
    'tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Celery 설정
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1시간 타임아웃
    task_soft_time_limit=3300,  # 55분 소프트 타임아웃
    worker_prefetch_multiplier=1,  # 한 번에 하나씩 처리
    worker_max_tasks_per_child=50,  # 50개 작업 후 워커 재시작
)


def init_celery(app: Flask):
    """
    Flask 앱과 Celery를 연동

    Args:
        app: Flask 앱 인스턴스
    """
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        """Flask 앱 컨텍스트 안에서 실행되는 Task"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


@celery.task(bind=True, max_retries=3)
def process_document_async(self, document_id: int):
    """
    문서 벡터화 백그라운드 작업

    전체 파이프라인:
    1. 문서 정보 조회
    2. 텍스트 추출 (PDF, DOCX, TXT 등)
    3. 청킹 (전략: paragraph/sentence/fixed)
    4. 임베딩 생성 (배치)
    5. pgvector에 저장

    Args:
        document_id: 처리할 문서 ID

    Returns:
        {
            "success": True,
            "document_id": 문서 ID,
            "chunk_count": 생성된 청크 수,
            "processing_time": 처리 시간(초)
        }

    Raises:
        Exception: 처리 실패 시 재시도 또는 에러 저장
    """
    from extensions import db
    from models import KnowledgeDocument, DocumentChunk, PersonaKnowledgeBase

    start_time = datetime.datetime.utcnow()

    # 1. 문서 조회
    doc = db.session.get(KnowledgeDocument, document_id)
    if not doc:
        raise ValueError(f"문서를 찾을 수 없습니다: document_id={document_id}")

    try:
        # 상태 업데이트: processing
        doc.processing_status = 'processing'
        db.session.commit()

        print(f"📄 문서 처리 시작: {doc.filename} (ID: {document_id})")

        # 2. 텍스트 추출
        if not os.path.exists(doc.file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {doc.file_path}")

        with open(doc.file_path, 'rb') as f:
            file_content = f.read()

        print(f"  ├─ 텍스트 추출 중... (파일 크기: {len(file_content)} bytes)")
        extracted_text = extract_text_from_file(file_content, doc.filename)

        if not extracted_text or not extracted_text.strip():
            raise ValueError("추출된 텍스트가 비어있습니다.")

        doc.extracted_text = extracted_text
        print(f"  ├─ 추출 완료 (텍스트 길이: {len(extracted_text)} 문자)")

        # 3. 청킹
        kb = db.session.get(PersonaKnowledgeBase, doc.knowledge_base_id)
        if not kb:
            raise ValueError(f"지식 베이스를 찾을 수 없습니다: {doc.knowledge_base_id}")

        print(f"  ├─ 청킹 시작 (전략: {kb.chunk_strategy}, 크기: {kb.chunk_size}, 중복: {kb.chunk_overlap})")
        chunks = chunk_text(
            extracted_text,
            strategy=kb.chunk_strategy,
            chunk_size=kb.chunk_size,
            overlap=kb.chunk_overlap
        )

        if not chunks:
            raise ValueError("청킹 결과가 비어있습니다.")

        print(f"  ├─ 청킹 완료 ({len(chunks)}개 청크 생성)")

        # 3.5. Smart Indexing (Contextual Retrieval) - 청크별 문맥 요약 생성
        print(f"  ├─ 청크별 문맥 요약(Context) 생성 중...")
        from services.ai_service import generate_ai_response
        
        # 전체 문서의 앞부분(최대 1000자)을 사용하여 문서의 전반적인 맥락을 파악
        document_context = extracted_text[:1000]
        
        # 요약 프롬프트 템플릿 (Anthropic Contextual Retrieval 방식)
        system_prompt = (
            "당신은 문서 검색(RAG) 시스템의 인덱싱 도우미입니다. "
            "주어진 [전체 문서 맥락]과 [현재 청크]를 읽고, 이 청크가 문서 내에서 어떤 정보인지, "
            "주요 키워드와 핵심 맥락을 1~2문장으로 짧게 요약해주세요. "
            "이 요약본은 데이터베이스에 벡터로 저장되어 향후 사용자 질문과 매칭될 매우 중요한 데이터입니다. "
            "답변은 요약된 텍스트만 출력하세요."
        )
        
        chunk_summaries = []
        # 빠르고 저렴한 모델 사용 (Gemini 2.5 Flash 우선, 없으면 gpt-4.1-mini)
        summary_model_id = "gemini-2.5-flash" if os.getenv("GOOGLE_API_KEY") else ("gpt-4.1-mini" if os.getenv("OPENAI_API_KEY") else "grok-4-1-fast-reasoning")
        
        import time
        for i, chunk_text in enumerate(chunks):
            # API 제한 시간 등을 고려한 약간의 딜레이
            if i > 0 and i % 10 == 0:
                time.sleep(1)
                
            user_prompt = f"[전체 문서 맥락 (앞부분)]\n{document_context}\n\n[현재 청크]\n{chunk_text}"
            try:
                # 임시 업로드 폴더 빈 값 전달
                summary = generate_ai_response(
                    model_id=summary_model_id,
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=150,
                    upload_folder=""
                )
                chunk_summaries.append(summary.strip())
            except Exception as e:
                print(f"     ⚠️ 청크 {i} 요약 실패, 원본 일부 대체: {e}")
                # 실패 시 청크 앞부분을 요약으로 대체
                chunk_summaries.append(chunk_text[:150])

        # 4. 임베딩 생성 (배치) - 원본 텍스트가 아닌 '요약본 + 원본 텍스트'를 함께 임베딩
        print(f"  ├─ 임베딩 생성 중... (OpenAI API 호출)")
        embeddings = generate_embeddings_batch(chunk_summaries)

        if len(embeddings) != len(chunks):
            raise ValueError(f"임베딩 수 불일치: {len(embeddings)} != {len(chunks)}")

        print(f"  ├─ 임베딩 생성 완료 ({len(embeddings)}개)")

        # 5. DB 저장
        print(f"  ├─ DB 저장 중...")

        # 기존 청크 삭제 (재처리 시)
        DocumentChunk.query.filter_by(document_id=doc.id).delete()

        # 새 청크 저장
        for i, (chunk_content, summary, embedding) in enumerate(zip(chunks, chunk_summaries, embeddings)):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_content,
                content_length=len(chunk_content),
                embedding=embedding,
                chunk_metadata={"context_summary": summary}
            )
            db.session.add(chunk)

        # 문서 상태 업데이트: completed
        doc.chunk_count = len(chunks)
        doc.processing_status = 'completed'
        doc.processed_at = datetime.datetime.utcnow()
        doc.error_message = None

        db.session.commit()

        # 처리 시간 계산
        end_time = datetime.datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        print(f"  └─ ✅ 처리 완료! (소요 시간: {processing_time:.2f}초)")

        return {
            "success": True,
            "document_id": document_id,
            "filename": doc.filename,
            "chunk_count": len(chunks),
            "processing_time": processing_time
        }

    except Exception as e:
        # 에러 처리
        error_msg = str(e)
        print(f"  └─ ❌ 처리 실패: {error_msg}")

        doc.processing_status = 'failed'
        doc.error_message = error_msg
        db.session.commit()

        # 재시도 (최대 3번)
        if self.request.retries < self.max_retries:
            print(f"     ⟳ 재시도 {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=e, countdown=60)  # 60초 후 재시도
        else:
            print(f"     ⨯ 최대 재시도 횟수 초과")
            raise


@celery.task
def cleanup_old_failed_documents():
    """
    오래된 실패 문서 정리 (주기적 실행)

    - 7일 이상 지난 failed 상태 문서 삭제
    - pending 상태로 24시간 이상 방치된 문서 failed로 변경
    """
    from extensions import db
    from models import KnowledgeDocument

    now = datetime.datetime.utcnow()
    deleted_count = 0

    try:
        # 1. 7일 이상 지난 failed 문서 삭제
        cutoff_failed = now - datetime.timedelta(days=7)
        old_failed_docs = KnowledgeDocument.query.filter(
            KnowledgeDocument.processing_status == 'failed',
            KnowledgeDocument.uploaded_at < cutoff_failed
        ).all()

        for doc in old_failed_docs:
            # 파일도 함께 삭제
            if os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception:
                    pass

            db.session.delete(doc)
            deleted_count += 1

        # 2. 24시간 이상 pending 상태인 문서 → failed로 변경
        cutoff_pending = now - datetime.timedelta(hours=24)
        stuck_docs = KnowledgeDocument.query.filter(
            KnowledgeDocument.processing_status == 'pending',
            KnowledgeDocument.uploaded_at < cutoff_pending
        ).all()

        for doc in stuck_docs:
            doc.processing_status = 'failed'
            doc.error_message = '처리 시간 초과 (24시간)'

        db.session.commit()

        print(f"🧹 정리 완료: {deleted_count}개 문서 삭제, {len(stuck_docs)}개 문서 failed로 변경")

        return {
            "deleted_count": deleted_count,
            "stuck_count": len(stuck_docs)
        }

    except Exception as e:
        db.session.rollback()
        print(f"❌ 정리 실패: {e}")
        raise


@celery.task
def reprocess_failed_documents():
    """
    실패한 문서 자동 재처리 (주기적 실행)

    - failed 상태이고 재시도 횟수가 3번 미만인 문서 재처리
    """
    from extensions import db
    from models import KnowledgeDocument

    try:
        failed_docs = KnowledgeDocument.query.filter(
            KnowledgeDocument.processing_status == 'failed'
        ).limit(10).all()  # 한 번에 최대 10개

        reprocess_count = 0
        for doc in failed_docs:
            # 재처리 시작
            doc.processing_status = 'pending'
            doc.error_message = None
            db.session.commit()

            # 백그라운드 작업 시작
            process_document_async.delay(doc.id)
            reprocess_count += 1

        print(f"🔄 재처리 시작: {reprocess_count}개 문서")

        return {"reprocess_count": reprocess_count}

    except Exception as e:
        db.session.rollback()
        print(f"❌ 재처리 실패: {e}")
        raise


# Celery Beat 스케줄 (주기적 작업)
celery.conf.beat_schedule = {
    'cleanup-old-failed-documents': {
        'task': 'tasks.cleanup_old_failed_documents',
        'schedule': 86400.0,  # 24시간마다
    },
    'reprocess-failed-documents': {
        'task': 'tasks.reprocess_failed_documents',
        'schedule': 3600.0,  # 1시간마다
    },
}
