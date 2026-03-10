# chunker.py
# 긴 텍스트를 RAG 검색에 적합한 크기의 청크로 나누는 모듈입니다.
# 너무 긴 문장은 임베딩/검색 품질이 떨어질 수 있으므로, 일정 글자 수 단위로 자릅니다.

from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
) -> List[str]:
    """
    하나의 긴 텍스트를 지정한 크기와 겹침으로 잘라서 청크 리스트로 반환합니다.

    인자:
        text: 원본 전체 텍스트 (예: PDF에서 추출한 문자열)
        chunk_size: 한 청크의 목표 글자 수. 이 크기 단위로 잘라냅니다.
        chunk_overlap: 다음 청크가 이전 청크와 겹치는 글자 수.
                      겹치면 문맥이 끊기지 않아 검색 품질에 도움이 됩니다.

    반환:
        잘라진 텍스트 조각들의 리스트. 각 원소가 한 개의 청크입니다.

    사용 예:
        embedding_service에 넘기기 전에, 문서 텍스트를 이 함수로 청크 리스트로 만듭니다.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    # 시작 위치를 (chunk_size - overlap)만큼씩 뒤로 밀어가며 잘라냅니다.
    # overlap만큼 겹치면, 이전 청크 끝과 다음 청크 앞이 이어져 문맥이 유지됩니다.
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        # 다음 청크 시작: 겹치는 부분만큼만 뒤로 물려서 이동
        start = start + chunk_size - chunk_overlap
        if start >= len(text):
            break

    return chunks
