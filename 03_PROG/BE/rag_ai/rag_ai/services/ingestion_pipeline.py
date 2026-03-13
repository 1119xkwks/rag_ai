# ingestion_pipeline.py
# PDF 업로드부터 벡터 DB 저장까지 한 번에 수행하는 인입 파이프라인입니다.
# 단계: PDF 바이트 → 텍스트 추출 → 청크 분할 → 임베딩 생성 → Qdrant 저장

import logging
import time
from typing import Any

from rag_ai.config import settings
from rag_ai.ingestion.chunker import chunk_markdown_by_h3, chunk_text
from rag_ai.ingestion.pdf_loader import load_text_from_pdf_bytes
from rag_ai.services.embedding_service import embed_texts
from rag_ai.services.text_cleanup_service import preprocess_text_with_llm
from rag_ai.services.vector_service import (
    ensure_collection,
    get_qdrant_client,
    upsert_chunks,
)

logger = logging.getLogger("rag_ai.services.ingestion")


def run_ingestion(
    pdf_bytes: bytes,
    source_name: str = "",
    extract_method: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    use_llm_cleanup: bool = False,
    cleanup_provider: str | None = None,
    cleanup_model: str | None = None,
) -> dict[str, Any]:
    """
    PDF 바이트를 받아 텍스트 추출 → 청킹 → 임베딩 → Qdrant 저장까지 실행합니다.

    인자:
        pdf_bytes: PDF 파일의 바이트 내용 (예: 업로드된 파일)
        source_name: 문서 출처 표시용 이름 (payload에 저장되어 나중에 필터링 가능)
        extract_method: PDF 텍스트 추출 방식 (pypdf | vision_qwen), None이면 설정값 사용
        chunk_size: 청크 크기. None이면 설정값 사용
        chunk_overlap: 청크 겹침. None이면 설정값 사용
        use_llm_cleanup: True면 청킹 전에 LLM 정제를 먼저 수행
        cleanup_provider: 정제용 provider (openai | vllm | gemini), None이면 현재 llm_provider 사용
        cleanup_model: 정제용 모델명 override

    반환:
        인입 결과 요약 (chunk 개수, 저장된 포인트 ID 개수, 사용한 컬렉션명 등)
    """
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    collection = settings.qdrant_collection
    source = source_name or "upload"

    total_start = time.perf_counter()
    logger.debug(
        "[INGEST_START] source=%s bytes=%s extract_method=%s use_llm_cleanup=%s cleanup_provider=%s cleanup_model=%s embedding_provider=%s",
        source,
        len(pdf_bytes),
        extract_method or settings.pdf_extract_method,
        use_llm_cleanup,
        cleanup_provider or settings.cleanup_provider or settings.llm_provider,
        cleanup_model or "",
        settings.embedding_provider,
    )

    # 1단계: PDF에서 텍스트 추출
    t_extract = time.perf_counter()
    chosen_extract_method = (extract_method or settings.pdf_extract_method).strip().lower()
    logger.debug(
        "[INGEST_STEP_START] step=extract_text source=%s method=%s",
        source,
        chosen_extract_method,
    )
    full_text = load_text_from_pdf_bytes(pdf_bytes, extract_method=chosen_extract_method)
    logger.debug(
        "[INGEST_STEP_DONE] step=extract_text source=%s method=%s text_len=%s elapsed_ms=%.1f",
        source,
        chosen_extract_method,
        len(full_text),
        (time.perf_counter() - t_extract) * 1000,
    )
    if not full_text.strip():
        return {"ok": False, "error": "PDF에서 추출된 텍스트가 없습니다.", "chunks_created": 0}

    # 2단계: (선택) LLM 정제로 텍스트를 먼저 정리
    text_for_chunking = full_text
    cleanup_meta = {
        "llm_cleanup_used": False,
        "llm_cleanup_provider": "",
        "llm_cleanup_model": "",
    }
    if use_llm_cleanup:
        provider = (
            cleanup_provider or settings.cleanup_provider or settings.llm_provider
        ).strip().lower()
        t_cleanup = time.perf_counter()
        logger.debug(
            "[INGEST_STEP_START] step=llm_cleanup source=%s provider=%s model=%s",
            source,
            provider,
            cleanup_model or "",
        )
        try:
            text_for_chunking = preprocess_text_with_llm(
                raw_text=full_text,
                provider=provider,
                model_override=cleanup_model,
            )
            cleanup_meta = {
                "llm_cleanup_used": True,
                "llm_cleanup_provider": provider,
                "llm_cleanup_model": cleanup_model or "",
            }
            logger.debug(
                "[INGEST_STEP_DONE] step=llm_cleanup source=%s provider=%s cleaned_len=%s elapsed_ms=%.1f",
                source,
                provider,
                len(text_for_chunking),
                (time.perf_counter() - t_cleanup) * 1000,
            )
        except Exception as e:
            return {
                "ok": False,
                "error": f"LLM 정제 실패: {e!s}",
                "chunks_created": 0,
            }

    # 3단계: 텍스트를 청크로 분할
    # - LLM 정제를 썼다면 '###' 헤더 기준 청킹을 우선 시도
    # - 실패하면 기존 글자수 기반 청킹으로 fallback
    t_chunk = time.perf_counter()
    logger.debug("[INGEST_STEP_START] step=chunk source=%s", source)
    chunks = []
    if use_llm_cleanup:
        chunks = chunk_markdown_by_h3(text_for_chunking)
        if chunks:
            logger.debug(
                "[INGEST_CHUNK] mode=markdown_h3 chunks=%s source=%s",
                len(chunks),
                source,
            )

    if not chunks:
        chunks = chunk_text(text_for_chunking, chunk_size=size, chunk_overlap=overlap)
        logger.debug(
            "[INGEST_CHUNK] mode=char_window chunks=%s chunk_size=%s overlap=%s source=%s",
            len(chunks),
            size,
            overlap,
            source,
        )
    logger.debug(
        "[INGEST_STEP_DONE] step=chunk source=%s chunks=%s elapsed_ms=%.1f",
        source,
        len(chunks),
        (time.perf_counter() - t_chunk) * 1000,
    )

    if not chunks:
        return {"ok": False, "error": "생성된 청크가 없습니다.", "chunks_created": 0}

    # 4단계: 각 청크를 임베딩 벡터로 변환
    # 문서 임베딩도 설정된 embedding_provider를 따라야,
    # 질문 임베딩과 동일한 벡터 공간에서 검색이 정확해집니다.
    t_embed = time.perf_counter()
    logger.debug(
        "[INGEST_STEP_START] step=embed_chunks source=%s provider=%s chunks=%s",
        source,
        settings.embedding_provider,
        len(chunks),
    )
    vectors = embed_texts(chunks, provider=settings.embedding_provider)
    logger.debug(
        "[INGEST_STEP_DONE] step=embed_chunks source=%s vectors=%s dim=%s elapsed_ms=%.1f",
        source,
        len(vectors),
        len(vectors[0]) if vectors else 0,
        (time.perf_counter() - t_embed) * 1000,
    )

    # 5단계: Qdrant 연결 후 컬렉션 존재 확인(없으면 생성)
    t_qdrant_prepare = time.perf_counter()
    logger.debug(
        "[INGEST_STEP_START] step=qdrant_prepare source=%s host=%s port=%s collection=%s",
        source,
        settings.qdrant_host,
        settings.qdrant_port,
        collection,
    )
    client = get_qdrant_client()
    ensure_collection(client, collection, dim=len(vectors[0]) if vectors else 1536)
    logger.debug(
        "[INGEST_STEP_DONE] step=qdrant_prepare source=%s elapsed_ms=%.1f",
        source,
        (time.perf_counter() - t_qdrant_prepare) * 1000,
    )

    # 6단계: 각 청크에 대한 메타데이터 (출처 등) 구성 후 Qdrant에 저장
    t_upsert = time.perf_counter()
    logger.debug("[INGEST_STEP_START] step=qdrant_upsert source=%s points=%s", source, len(chunks))
    metadata_list = [{"source": source}] * len(chunks)
    ids = upsert_chunks(client, collection, vectors, chunks, metadata_list=metadata_list)
    logger.debug(
        "[INGEST_STEP_DONE] step=qdrant_upsert source=%s inserted=%s elapsed_ms=%.1f",
        source,
        len(ids),
        (time.perf_counter() - t_upsert) * 1000,
    )

    total_elapsed_ms = (time.perf_counter() - total_start) * 1000
    logger.debug("[INGEST_DONE] source=%s total_elapsed_ms=%.1f", source, total_elapsed_ms)

    return {
        "ok": True,
        "chunks_created": len(chunks),
        "points_upserted": len(ids),
        "collection": collection,
        "source": source,
        **cleanup_meta,
    }
