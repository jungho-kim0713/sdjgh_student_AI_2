"""
RAG (Retrieval-Augmented Generation) 검색 서비스

페르소나별 지식 베이스에서 관련 문서를 검색하고 컨텍스트를 구성합니다.
두 가지 검색 전략을 지원합니다:
- Soft Top-K: 예측 가능, 비용 통제 용이 (기본 추천)
- Gap-based: 적응적, 자동 최적화 (고급 옵션)
"""

from typing import List, Dict
from services.embedding_service import generate_embedding
from extensions import db


def search_knowledge_base(
    persona_id: int,
    query: str,
    strategy: str = 'soft_topk',
    top_k: int = 3,
    max_k: int = 7,
    threshold: float = 0.5,
    gap_threshold: float = 0.1
) -> List[Dict]:
    """
    RAG 검색 실행 (두 전략 지원)

    Args:
        persona_id: 페르소나 ID
        query: 검색 질문
        strategy: 'soft_topk' | 'gap_based'
        top_k: Soft Top-K의 최소값 또는 고정 Top-K
        max_k: Soft Top-K의 최대값
        threshold: 유사도 임계값 (0.0 ~ 1.0)
        gap_threshold: Gap-based 전략에서 사용할 gap 임계값

    Returns:
        검색 결과 리스트 [
            {
                "content": "청크 내용",
                "filename": "파일명",
                "metadata": {...},
                "similarity": 0.85
            },
            ...
        ]

    Raises:
        ValueError: 임베딩 생성 실패 시
        Exception: DB 쿼리 실패 시
    """
    try:
        # 1. 질문 임베딩 생성
        query_embedding = generate_embedding(query)

        # 2. 전략에 따라 검색 실행
        if strategy == 'soft_topk':
            return _search_soft_topk(
                persona_id, query_embedding, top_k, max_k, threshold
            )
        elif strategy == 'gap_based':
            return _search_gap_based(
                persona_id, query_embedding, threshold, gap_threshold
            )
        else:
            # 기본값: Soft Top-K
            return _search_soft_topk(
                persona_id, query_embedding, top_k, max_k, threshold
            )

    except Exception as e:
        print(f"⚠️ RAG 검색 실패: {e}")
        raise


def _search_soft_topk(
    persona_id: int,
    query_embedding: List[float],
    min_k: int,
    max_k: int,
    threshold: float
) -> List[Dict]:
    """
    Soft Top-K 전략 (추천)

    특징:
    - 최소 min_k개 보장 (데이터가 부족해도 최선을 다함)
    - 최대 max_k개까지 검색 (비용 통제)
    - 유사도 threshold 이상인 것만 포함 (품질 보장)

    동작:
    1. threshold 이상 & max_k개 이하 검색
    2. 결과가 min_k 미만이면 threshold 무시하고 min_k개 강제 검색

    Args:
        persona_id: 페르소나 ID
        query_embedding: 질문 임베딩 벡터
        min_k: 최소 검색 개수
        max_k: 최대 검색 개수
        threshold: 유사도 임계값

    Returns:
        검색 결과 리스트
    """
    # Step 1: threshold 이상 & max_k개 이하 검색
    sql = """
        SELECT
            dc.content,
            kd.filename,
            dc.chunk_metadata,
            1 - (dc.embedding <=> %s::vector) AS similarity
        FROM document_chunk dc
        JOIN knowledge_document kd ON dc.document_id = kd.id
        JOIN persona_knowledge_base pkb ON kd.knowledge_base_id = pkb.id
        WHERE pkb.persona_id = %s
          AND pkb.is_active = TRUE
          AND kd.processing_status = 'completed'
          AND 1 - (dc.embedding <=> %s::vector) >= %s
        ORDER BY dc.embedding <=> %s::vector
        LIMIT %s
    """

    result = db.session.execute(
        sql,
        (query_embedding, persona_id, query_embedding, threshold, query_embedding, max_k)
    )

    docs = [
        {
            "content": row[0],
            "filename": row[1],
            "metadata": row[2],
            "similarity": float(row[3])
        }
        for row in result
    ]

    # Step 2: 최소 min_k개 보장 (threshold 무시)
    if len(docs) < min_k:
        sql_fallback = """
            SELECT
                dc.content,
                kd.filename,
                dc.chunk_metadata,
                1 - (dc.embedding <=> %s::vector) AS similarity
            FROM document_chunk dc
            JOIN knowledge_document kd ON dc.document_id = kd.id
            JOIN persona_knowledge_base pkb ON kd.knowledge_base_id = pkb.id
            WHERE pkb.persona_id = %s
              AND pkb.is_active = TRUE
              AND kd.processing_status = 'completed'
            ORDER BY dc.embedding <=> %s::vector
            LIMIT %s
        """
        result_fallback = db.session.execute(
            sql_fallback,
            (query_embedding, persona_id, query_embedding, min_k)
        )
        docs = [
            {
                "content": row[0],
                "filename": row[1],
                "metadata": row[2],
                "similarity": float(row[3])
            }
            for row in result_fallback
        ]

    return docs


def _search_gap_based(
    persona_id: int,
    query_embedding: List[float],
    threshold: float,
    gap_threshold: float
) -> List[Dict]:
    """
    Gap-based 전략 (고급)

    특징:
    - 적응적: 질문마다 자동으로 최적 개수 결정
    - 똑똑함: 유사도 패턴에서 자연스러운 구분점 감지

    동작:
    1. 충분히 많은 문서를 가져옴 (최대 50개)
    2. 유사도 순으로 정렬된 목록에서 gap 분석
    3. gap >= gap_threshold인 지점에서 중단 (자연스러운 경계)

    Args:
        persona_id: 페르소나 ID
        query_embedding: 질문 임베딩 벡터
        threshold: 최소 유사도 임계값
        gap_threshold: Gap 임계값 (예: 0.1 = 10% 차이)

    Returns:
        검색 결과 리스트

    Example:
        유사도: [0.92, 0.90, 0.88, 0.52, 0.50]
                                    ^^^^
                                    Gap = 0.36 → 여기서 중단!
        결과: 처음 3개만 반환
    """
    # Step 1: 충분히 많은 문서 가져오기 (최대 50개)
    sql = """
        SELECT
            dc.content,
            kd.filename,
            dc.chunk_metadata,
            1 - (dc.embedding <=> %s::vector) AS similarity
        FROM document_chunk dc
        JOIN knowledge_document kd ON dc.document_id = kd.id
        JOIN persona_knowledge_base pkb ON kd.knowledge_base_id = pkb.id
        WHERE pkb.persona_id = %s
          AND pkb.is_active = TRUE
          AND kd.processing_status = 'completed'
          AND 1 - (dc.embedding <=> %s::vector) >= %s
        ORDER BY dc.embedding <=> %s::vector
        LIMIT 50
    """

    result = db.session.execute(
        sql,
        (query_embedding, persona_id, query_embedding, threshold, query_embedding)
    )

    all_docs = [
        {
            "content": row[0],
            "filename": row[1],
            "metadata": row[2],
            "similarity": float(row[3])
        }
        for row in result
    ]

    if not all_docs:
        return []

    # Step 2: Gap 분석하여 자연스러운 구분점 찾기
    selected_docs = [all_docs[0]]  # 첫 번째는 무조건 포함

    for i in range(1, len(all_docs)):
        # 이전 문서와 현재 문서의 유사도 차이 계산
        gap = selected_docs[-1]['similarity'] - all_docs[i]['similarity']

        if gap >= gap_threshold:
            # 큰 gap 발견 → 자연스러운 경계로 판단, 여기서 중단
            break

        selected_docs.append(all_docs[i])

        # 안전장치: 최대 20개까지만
        if len(selected_docs) >= 20:
            break

    return selected_docs


def format_rag_context(retrieved_docs: List[dict]) -> str:
    """
    검색된 문서를 AI 프롬프트용 컨텍스트 형식으로 포맷팅

    Args:
        retrieved_docs: 검색 결과 리스트

    Returns:
        포맷팅된 컨텍스트 문자열

    Example:
        === 관련 참고 자료 ===

        [자료 1] 파일명: python_basics.pdf
        유사도: 0.92
        내용:
        변수는 데이터를 저장하는 공간입니다...

        [자료 2] 파일명: exercises.docx
        유사도: 0.78
        내용:
        변수 선언 예제: x = 10...

        위 자료를 참고하여 답변하되, 자료에 없는 내용은 일반 지식으로 답변하세요.
    """
    if not retrieved_docs:
        return ""

    context = "=== 관련 참고 자료 ===\n\n"

    for i, doc in enumerate(retrieved_docs):
        context += f"[자료 {i+1}] 파일명: {doc['filename']}\n"
        context += f"유사도: {doc['similarity']:.2f}\n"

        # 메타데이터에 페이지 정보가 있으면 표시
        if doc.get('metadata') and doc['metadata'].get('page'):
            context += f"페이지: {doc['metadata']['page']}\n"

        context += f"내용:\n{doc['content']}\n\n"

    context += "위 자료를 참고하여 답변하되, 자료에 없는 내용은 일반 지식으로 답변하세요.\n"
    return context


def get_rag_statistics(persona_id: int) -> Dict:
    """
    페르소나의 RAG 통계 정보 조회

    Args:
        persona_id: 페르소나 ID

    Returns:
        {
            "knowledge_base_count": 지식 베이스 개수,
            "document_count": 문서 개수,
            "chunk_count": 청크 개수,
            "processing_count": 처리 중인 문서 수,
            "failed_count": 실패한 문서 수
        }
    """
    # 지식 베이스 개수
    kb_count_sql = """
        SELECT COUNT(*)
        FROM persona_knowledge_base
        WHERE persona_id = %s AND is_active = TRUE
    """
    kb_count = db.session.execute(kb_count_sql, (persona_id,)).scalar() or 0

    # 문서 개수 및 상태별 통계
    doc_stats_sql = """
        SELECT
            COUNT(*) as total_docs,
            SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as completed_docs,
            SUM(CASE WHEN processing_status = 'processing' THEN 1 ELSE 0 END) as processing_docs,
            SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed_docs,
            SUM(chunk_count) as total_chunks
        FROM knowledge_document kd
        JOIN persona_knowledge_base pkb ON kd.knowledge_base_id = pkb.id
        WHERE pkb.persona_id = %s
    """
    doc_stats = db.session.execute(doc_stats_sql, (persona_id,)).fetchone()

    return {
        "knowledge_base_count": int(kb_count),
        "document_count": int(doc_stats[0]) if doc_stats else 0,
        "completed_count": int(doc_stats[1]) if doc_stats else 0,
        "processing_count": int(doc_stats[2]) if doc_stats else 0,
        "failed_count": int(doc_stats[3]) if doc_stats else 0,
        "chunk_count": int(doc_stats[4]) if doc_stats else 0
    }
