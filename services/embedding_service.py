"""
임베딩 생성 서비스

OpenAI text-embedding-3-small 모델을 사용하여 텍스트를 1536차원 벡터로 변환합니다.
RAG 시스템에서 문서 검색을 위해 사용됩니다.
"""

import os
from typing import List
from services.ai_service import openai_client


def generate_embedding(text: str) -> List[float]:
    """
    단일 텍스트의 임베딩 생성

    Args:
        text: 임베딩할 텍스트

    Returns:
        1536차원 벡터 (List[float])

    Raises:
        ValueError: OpenAI 클라이언트가 초기화되지 않은 경우
        Exception: API 호출 실패 시
    """
    if not openai_client:
        raise ValueError("OpenAI 클라이언트가 초기화되지 않았습니다. OPENAI_API_KEY를 확인하세요.")

    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"⚠️ 임베딩 생성 실패: {e}")
        raise


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    여러 텍스트의 임베딩을 배치로 생성 (효율성 향상)

    Args:
        texts: 임베딩할 텍스트 목록 (최대 2048개)

    Returns:
        1536차원 벡터 리스트

    Raises:
        ValueError: OpenAI 클라이언트가 초기화되지 않은 경우
        Exception: API 호출 실패 시
    """
    if not openai_client:
        raise ValueError("OpenAI 클라이언트가 초기화되지 않았습니다. OPENAI_API_KEY를 확인하세요.")

    if not texts:
        return []

    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"⚠️ 배치 임베딩 생성 실패: {e}")
        raise


def estimate_embedding_cost(texts: List[str]) -> dict:
    """
    임베딩 생성 예상 비용 계산

    Args:
        texts: 임베딩할 텍스트 목록

    Returns:
        {
            "total_chars": 총 문자 수,
            "estimated_tokens": 예상 토큰 수,
            "estimated_cost_usd": 예상 비용(USD)
        }
    """
    total_chars = sum(len(text) for text in texts)
    # 대략적인 토큰 계산 (한글: 2자당 1토큰, 영어: 4자당 1토큰)
    estimated_tokens = total_chars // 3  # 평균값 사용

    # text-embedding-3-small 가격: $0.02 / 1M tokens
    estimated_cost = (estimated_tokens / 1_000_000) * 0.02

    return {
        "total_chars": total_chars,
        "estimated_tokens": estimated_tokens,
        "estimated_cost_usd": round(estimated_cost, 6)
    }
