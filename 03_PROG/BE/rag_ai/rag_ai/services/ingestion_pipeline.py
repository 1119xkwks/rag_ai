# ingestion_pipeline.py
# PDF 업로드부터 벡터 DB 저장까지 한 번에 수행하는 인입 파이프라인입니다.
# 단계: PDF 바이트 → 텍스트 추출 → 청크 분할 → 임베딩 생성 → Qdrant 저장

from typing import Any

from rag_ai.config import settings
from rag_ai.ingestion.chunker import chunk_text
from rag_ai.ingestion.pdf_loader import load_text_from_pdf_bytes
from rag_ai.services.embedding_service import embed_texts
from rag_ai.services.vector_service import (
    ensure_collection,
    get_qdrant_client,
    upsert_chunks,
)


def run_ingestion(
    pdf_bytes: bytes,
    source_name: str = "",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict[str, Any]:
    """
    PDF 바이트를 받아 텍스트 추출 → 청킹 → 임베딩 → Qdrant 저장까지 실행합니다.

    인자:
        pdf_bytes: PDF 파일의 바이트 내용 (예: 업로드된 파일)
        source_name: 문서 출처 표시용 이름 (payload에 저장되어 나중에 필터링 가능)
        chunk_size: 청크 크기. None이면 설정값 사용
        chunk_overlap: 청크 겹침. None이면 설정값 사용

    반환:
        인입 결과 요약 (chunk 개수, 저장된 포인트 ID 개수, 사용한 컬렉션명 등)
    """
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    collection = settings.qdrant_collection

    # 1단계: PDF에서 텍스트 추출
    full_text = load_text_from_pdf_bytes(pdf_bytes)
    if not full_text.strip():
        return {"ok": False, "error": "PDF에서 추출된 텍스트가 없습니다.", "chunks_created": 0}

    # 2단계: 텍스트를 청크로 분할
    chunks = chunk_text(full_text, chunk_size=size, chunk_overlap=overlap)
    if not chunks:
        return {"ok": False, "error": "생성된 청크가 없습니다.", "chunks_created": 0}

    # 3단계: 각 청크를 임베딩 벡터로 변환
    # 문서 임베딩도 설정된 embedding_provider를 따라야,
    # 질문 임베딩과 동일한 벡터 공간에서 검색이 정확해집니다.
    vectors = embed_texts(chunks, provider=settings.embedding_provider)

    # 4단계: Qdrant 연결 후 컬렉션 존재 확인(없으면 생성)
    client = get_qdrant_client()
    ensure_collection(client, collection, dim=len(vectors[0]) if vectors else 1536)

    # 5단계: 각 청크에 대한 메타데이터 (출처 등) 구성 후 Qdrant에 저장
    metadata_list = [{"source": source_name or "upload"}] * len(chunks)
    ids = upsert_chunks(client, collection, vectors, chunks, metadata_list=metadata_list)

    return {
        "ok": True,
        "chunks_created": len(chunks),
        "points_upserted": len(ids),
        "collection": collection,
        "source": source_name or "upload",
    }
