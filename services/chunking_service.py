"""
텍스트 청킹 서비스

대용량 문서를 검색 가능한 작은 단위로 분할합니다.
세 가지 전략을 지원합니다: paragraph (문단), sentence (문장), fixed (고정 길이)
"""

from typing import List
import re


def chunk_text(
    text: str,
    strategy: str = 'paragraph',
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[str]:
    """
    텍스트를 청킹 전략에 따라 분할

    Args:
        text: 분할할 원본 텍스트
        strategy: 청킹 전략 ('paragraph' | 'sentence' | 'fixed')
        chunk_size: 청크 최대 크기 (문자 수)
        overlap: 청크 간 중복 크기 (문자 수)

    Returns:
        분할된 텍스트 조각 리스트
    """
    if not text or not text.strip():
        return []

    if strategy == 'paragraph':
        return chunk_by_paragraph(text, chunk_size, overlap)
    elif strategy == 'sentence':
        return chunk_by_sentence(text, chunk_size, overlap)
    elif strategy == 'fixed':
        return chunk_fixed(text, chunk_size, overlap)
    else:
        # 기본값: paragraph
        return chunk_by_paragraph(text, chunk_size, overlap)


def chunk_by_paragraph(text: str, max_size: int, overlap: int) -> List[str]:
    """
    문단 기반 청킹 (문단 경계 우선 유지)

    - 문단 구분자: 연속된 줄바꿈 (\n\n)
    - 문단 크기가 max_size를 초과하면 문장 단위로 재분할
    - 문단 경계를 최대한 유지하여 의미 보존

    Args:
        text: 원본 텍스트
        max_size: 청크 최대 크기
        overlap: 중복 크기

    Returns:
        분할된 청크 리스트
    """
    # 문단 분리 (연속된 줄바꿈 기준)
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 현재 청크에 문단 추가 가능한지 확인
        if len(current_chunk) + len(para) + 2 <= max_size:  # +2 for \n\n
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            # 현재 청크를 저장
            if current_chunk:
                chunks.append(current_chunk)

            # 문단이 max_size보다 크면 문장 단위로 분할
            if len(para) > max_size:
                para_chunks = chunk_by_sentence(para, max_size, overlap)
                chunks.extend(para_chunks)
                current_chunk = ""
            else:
                current_chunk = para

    # 마지막 청크 저장
    if current_chunk:
        chunks.append(current_chunk)

    # Overlap 적용
    if overlap > 0:
        chunks = apply_overlap(chunks, overlap)

    return chunks


def chunk_by_sentence(text: str, max_size: int, overlap: int) -> List[str]:
    """
    문장 기반 청킹 (문장 경계 우선 유지)

    - 한글/영어 문장 종결 부호 인식: . ! ? 。！？
    - 문장 크기가 max_size를 초과하면 고정 길이로 강제 분할

    Args:
        text: 원본 텍스트
        max_size: 청크 최대 크기
        overlap: 중복 크기

    Returns:
        분할된 청크 리스트
    """
    # 문장 분리 (한글/영어 종결 부호 기준)
    sentence_endings = r'[.!?。！？]\s+'
    sentences = re.split(f'({sentence_endings})', text)

    # 종결 부호와 문장을 다시 합침
    merged_sentences = []
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            merged_sentences.append(sentences[i] + sentences[i + 1].strip())
        else:
            merged_sentences.append(sentences[i])

    if not merged_sentences:
        merged_sentences = [text]

    chunks = []
    current_chunk = ""

    for sent in merged_sentences:
        sent = sent.strip()
        if not sent:
            continue

        # 현재 청크에 문장 추가 가능한지 확인
        if len(current_chunk) + len(sent) + 1 <= max_size:
            if current_chunk:
                current_chunk += " " + sent
            else:
                current_chunk = sent
        else:
            # 현재 청크를 저장
            if current_chunk:
                chunks.append(current_chunk)

            # 문장이 max_size보다 크면 고정 길이로 강제 분할
            if len(sent) > max_size:
                fixed_chunks = chunk_fixed(sent, max_size, 0)
                chunks.extend(fixed_chunks)
                current_chunk = ""
            else:
                current_chunk = sent

    # 마지막 청크 저장
    if current_chunk:
        chunks.append(current_chunk)

    # Overlap 적용
    if overlap > 0:
        chunks = apply_overlap(chunks, overlap)

    return chunks


def chunk_fixed(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    고정 길이 청킹 (단순 분할)

    - 텍스트를 chunk_size 단위로 기계적으로 분할
    - 단어 경계 무시 (극단적 상황용)

    Args:
        text: 원본 텍스트
        chunk_size: 청크 크기
        overlap: 중복 크기

    Returns:
        분할된 청크 리스트
    """
    if overlap >= chunk_size:
        overlap = chunk_size // 2  # 안전 장치

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += (chunk_size - overlap)

    return chunks


def apply_overlap(chunks: List[str], overlap: int) -> List[str]:
    """
    청크 간 중복 영역 추가 (컨텍스트 연속성 유지)

    Args:
        chunks: 원본 청크 리스트
        overlap: 중복할 문자 수

    Returns:
        중복 영역이 추가된 청크 리스트
    """
    if len(chunks) <= 1 or overlap <= 0:
        return chunks

    overlapped_chunks = [chunks[0]]

    for i in range(1, len(chunks)):
        prev_chunk = chunks[i - 1]
        curr_chunk = chunks[i]

        # 이전 청크의 마지막 overlap 문자를 현재 청크 앞에 추가
        if len(prev_chunk) >= overlap:
            overlap_text = prev_chunk[-overlap:]
            overlapped_chunks.append(overlap_text + " " + curr_chunk)
        else:
            overlapped_chunks.append(curr_chunk)

    return overlapped_chunks


def estimate_chunk_count(text: str, strategy: str = 'paragraph', chunk_size: int = 1000) -> int:
    """
    예상 청크 개수 계산 (실제 청킹 없이 빠르게 추정)

    Args:
        text: 원본 텍스트
        strategy: 청킹 전략
        chunk_size: 청크 크기

    Returns:
        예상 청크 개수
    """
    if not text:
        return 0

    # 대략적인 추정
    return max(1, len(text) // chunk_size)
