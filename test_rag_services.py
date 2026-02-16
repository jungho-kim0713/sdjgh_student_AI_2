"""
RAG 서비스 테스트 스크립트

임베딩 생성, 청킹, 비용 추정 기능을 테스트합니다.
"""

import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화 (직접)
import openai
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    try:
        import httpx
        http_client = httpx.Client()
        openai_client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            http_client=http_client
        )
        # services.ai_service의 openai_client를 덮어쓰기
        import services.ai_service
        services.ai_service.openai_client = openai_client
        print("✅ OpenAI 클라이언트 초기화 성공")
    except Exception as e:
        print(f"⚠️ OpenAI 클라이언트 초기화 실패: {e}")

from services.embedding_service import (
    generate_embedding,
    generate_embeddings_batch,
    estimate_embedding_cost
)
from services.chunking_service import (
    chunk_text,
    chunk_by_paragraph,
    chunk_by_sentence,
    chunk_fixed,
    estimate_chunk_count
)


def test_embedding():
    """임베딩 생성 테스트"""
    print("\n=== 임베딩 생성 테스트 ===")

    test_text = "안녕하세요. 이것은 임베딩 테스트입니다."

    try:
        # 단일 임베딩 생성
        print(f"입력 텍스트: {test_text}")
        embedding = generate_embedding(test_text)
        print(f"✅ 임베딩 생성 성공!")
        print(f"   - 차원: {len(embedding)}")
        print(f"   - 첫 5개 값: {embedding[:5]}")

        # 배치 임베딩 생성
        test_texts = [
            "첫 번째 테스트 문장입니다.",
            "두 번째 테스트 문장입니다.",
            "세 번째 테스트 문장입니다."
        ]
        print(f"\n배치 임베딩 테스트: {len(test_texts)}개 문장")
        embeddings = generate_embeddings_batch(test_texts)
        print(f"✅ 배치 임베딩 생성 성공!")
        print(f"   - 생성된 임베딩 수: {len(embeddings)}")

        # 비용 추정
        cost_info = estimate_embedding_cost(test_texts)
        print(f"\n비용 추정:")
        print(f"   - 총 문자 수: {cost_info['total_chars']}")
        print(f"   - 예상 토큰 수: {cost_info['estimated_tokens']}")
        print(f"   - 예상 비용: ${cost_info['estimated_cost_usd']:.6f}")

        return True

    except Exception as e:
        print(f"❌ 임베딩 생성 실패: {e}")
        return False


def test_chunking():
    """청킹 서비스 테스트"""
    print("\n=== 청킹 서비스 테스트 ===")

    # 테스트 텍스트 (한글 + 영어)
    test_text = """
머신러닝(Machine Learning)은 인공지능의 한 분야입니다.

머신러닝은 데이터로부터 패턴을 학습하여 예측이나 결정을 수행합니다. 크게 지도학습, 비지도학습, 강화학습으로 나뉩니다.

지도학습(Supervised Learning)은 레이블이 있는 데이터로 학습합니다. 예를 들어, 이메일 스팸 분류나 이미지 인식 등이 있습니다.

비지도학습(Unsupervised Learning)은 레이블 없는 데이터에서 패턴을 찾습니다. 클러스터링이나 차원 축소가 대표적입니다.

강화학습(Reinforcement Learning)은 보상을 최대화하는 행동을 학습합니다. 게임 AI나 로봇 제어에 사용됩니다.
    """.strip()

    print(f"원본 텍스트 길이: {len(test_text)} 문자\n")

    # 1. Paragraph 청킹 테스트
    print("1. Paragraph 청킹 (max_size=200, overlap=50)")
    chunks_para = chunk_by_paragraph(test_text, max_size=200, overlap=50)
    print(f"   - 생성된 청크 수: {len(chunks_para)}")
    for i, chunk in enumerate(chunks_para[:2]):  # 처음 2개만 출력
        print(f"   - 청크 {i+1} ({len(chunk)}자): {chunk[:50]}...")

    # 2. Sentence 청킹 테스트
    print("\n2. Sentence 청킹 (max_size=150, overlap=30)")
    chunks_sent = chunk_by_sentence(test_text, max_size=150, overlap=30)
    print(f"   - 생성된 청크 수: {len(chunks_sent)}")
    for i, chunk in enumerate(chunks_sent[:2]):
        print(f"   - 청크 {i+1} ({len(chunk)}자): {chunk[:50]}...")

    # 3. Fixed 청킹 테스트
    print("\n3. Fixed 청킹 (chunk_size=100, overlap=20)")
    chunks_fixed = chunk_fixed(test_text, chunk_size=100, overlap=20)
    print(f"   - 생성된 청크 수: {len(chunks_fixed)}")
    for i, chunk in enumerate(chunks_fixed[:2]):
        print(f"   - 청크 {i+1} ({len(chunk)}자): {chunk[:50]}...")

    # 4. 청크 개수 추정 테스트
    print("\n4. 청크 개수 추정")
    estimated = estimate_chunk_count(test_text, strategy='paragraph', chunk_size=200)
    actual = len(chunks_para)
    print(f"   - 추정 개수: {estimated}")
    print(f"   - 실제 개수: {actual}")

    return True


def test_integration():
    """통합 테스트: 청킹 + 임베딩"""
    print("\n=== 통합 테스트: 청킹 + 임베딩 ===")

    test_text = """
확률과 통계는 수학의 중요한 분야입니다.

확률은 불확실한 사건이 일어날 가능성을 수치로 나타냅니다. 예를 들어, 동전을 던졌을 때 앞면이 나올 확률은 1/2입니다.

통계는 데이터를 수집하고 분석하여 의미 있는 정보를 추출합니다. 평균, 분산, 표준편차 등의 개념을 사용합니다.
    """.strip()

    try:
        # 1. 텍스트를 청킹
        print("1. 텍스트 청킹...")
        chunks = chunk_by_paragraph(test_text, max_size=150, overlap=30)
        print(f"   ✅ {len(chunks)}개 청크 생성")

        # 2. 각 청크의 임베딩 생성
        print("\n2. 청크 임베딩 생성...")
        embeddings = generate_embeddings_batch(chunks)
        print(f"   ✅ {len(embeddings)}개 임베딩 생성")

        # 3. 비용 추정
        cost_info = estimate_embedding_cost(chunks)
        print(f"\n3. 예상 비용:")
        print(f"   - 총 문자 수: {cost_info['total_chars']}")
        print(f"   - 예상 토큰 수: {cost_info['estimated_tokens']}")
        print(f"   - 예상 비용: ${cost_info['estimated_cost_usd']:.6f}")

        print("\n✅ 통합 테스트 성공!")
        return True

    except Exception as e:
        print(f"❌ 통합 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("RAG 서비스 테스트 시작")
    print("=" * 60)

    results = []

    # 청킹 테스트 (API 키 불필요)
    results.append(("청킹 서비스", test_chunking()))

    # 임베딩 테스트 (API 키 필요)
    results.append(("임베딩 생성", test_embedding()))

    # 통합 테스트
    results.append(("통합 테스트", test_integration()))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    for name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패. 로그를 확인하세요.")

    sys.exit(0 if all_passed else 1)
