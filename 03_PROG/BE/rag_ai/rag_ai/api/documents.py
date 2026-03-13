# documents.py
# 문서 업로드 및 PDF 인입 API 엔드포인트를 정의합니다.

import asyncio
import json
import logging
import threading
import time
from queue import Empty, Queue

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag_ai.config import settings
from rag_ai.ingestion.chunker import chunk_markdown_by_delimiter, chunk_text
from rag_ai.ingestion.pdf_loader import ExtractionCancelled, load_text_from_pdf_bytes
from rag_ai.services.embedding_service import embed_texts
from rag_ai.services.ingestion_pipeline import run_ingestion
from rag_ai.services.text_cleanup_service import preprocess_text_with_llm
from rag_ai.services.vector_service import ensure_collection, get_qdrant_client, upsert_chunks

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("rag_ai.api.documents")

# SSE 스트림용: 로그 메시지를 큐에 넣는 핸들러
_LOG_QUEUE_SENTINEL = ("_END_", None)


class _QueueLogHandler(logging.Handler):
    """로그 레코드를 큐에 넣어 SSE로 전달할 수 있게 합니다."""

    def __init__(self, log_queue: Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put(("LOG", msg))
        except Exception:
            self.handleError(record)


def _normalize_extract_method(method: str) -> str:
    normalized = (method or settings.pdf_extract_method).strip().lower()
    if normalized not in {"pypdf", "vision_qwen"}:
        raise HTTPException(
            status_code=400,
            detail="extract_method는 pypdf 또는 vision_qwen 중 하나여야 합니다.",
        )
    return normalized


class CleanupTextRequest(BaseModel):
    # 사용자가 수정한 원문 텍스트(또는 PDF 추출 텍스트)
    text: str = Field(..., description="정제할 원문 텍스트")
    # 정제 수행 여부 (false면 text를 그대로 반환)
    use_cleanup: bool = Field(True, description="LLM 정제 사용 여부")
    # 정제용 provider (openai | vllm | gemini)
    cleanup_provider: str = Field("gemini", description="정제용 LLM provider")
    # 정제용 모델명 (비우면 provider 기본 모델 사용)
    cleanup_model: str = Field("", description="정제용 모델명 override")
    # 사용자가 지정하는 청크 구분 기호 (기본: ###)
    cleanup_delimiter: str = Field("###", description="정제 가이드용 청크 구분 기호")


class ChunkTextRequest(BaseModel):
    # 청킹할 텍스트(정제 결과 또는 원문)
    text: str = Field(..., description="청킹할 텍스트")
    # markdown h3(###) 우선 청킹 사용 여부
    prefer_markdown_h3: bool = Field(True, description="### 헤더 우선 청킹 사용 여부")
    # 마크다운 헤더 구분 기호 (기본: ###)
    chunk_delimiter: str = Field("###", description="헤더 구분 기호")
    # 글자수 기반 fallback 청킹 크기
    chunk_size: int = Field(2000, ge=200, le=8000, description="글자수 기반 청크 크기")
    # 글자수 기반 fallback overlap
    chunk_overlap: int = Field(200, ge=0, le=2000, description="글자수 기반 overlap")


class SaveChunksRequest(BaseModel):
    # Qdrant payload source 값
    source_name: str = Field("", description="저장할 source 이름 (비우면 upload)")
    # 저장할 청크 리스트
    chunks: list[str] = Field(default_factory=list, description="Vector DB에 저장할 청크 리스트")
    # 임베딩 provider override (openai | vllm | gemini), 비우면 설정값 사용
    embedding_provider: str = Field("", description="임베딩 provider override")


@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(..., description="업로드할 PDF 파일"),
    source_name: str = Query("", description="문서 출처 이름 (비우면 파일명 사용)"),
    extract_method: str = Query(
        "",
        description="PDF 텍스트 추출 방식 (pypdf | vision_qwen), 비우면 서버 기본값",
    ),
    use_llm_cleanup: bool = Query(
        False,
        description="True면 청킹 전에 LLM으로 텍스트 정제를 수행합니다.",
    ),
    cleanup_provider: str = Query(
        "",
        description="정제용 LLM provider (openai | vllm | gemini), 비우면 서버 기본값",
    ),
    cleanup_model: str = Query(
        "",
        description="정제용 모델명 override (선택)",
    ),
) -> dict:
    """
    PDF 파일을 업로드하면, 텍스트 추출 → 청킹 → 임베딩 → Qdrant 저장까지 한 번에 수행합니다.

    - file: PDF 파일 (multipart/form-data)
    - source_name: (선택) 문서 출처 이름. 비우면 "upload"로 저장됨

    반환: 인입 결과 요약 (chunks_created, points_upserted, collection 등)
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    # 업로드된 파일 내용을 바이트로 읽어서 파이프라인에 넘김
    try:
        pdf_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 읽기 실패: {e!s}")

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="파일 내용이 비어 있습니다.")

    # 출처 이름이 비어 있으면 업로드된 파일명 사용
    source = source_name.strip() or (file.filename or "upload")
    normalized_extract_method = _normalize_extract_method(extract_method)
    logger.debug(
        "[DOC_INGEST] filename=%s source=%s size_bytes=%s extract_method=%s use_llm_cleanup=%s cleanup_provider=%s cleanup_model=%s",
        file.filename,
        source,
        len(pdf_bytes),
        normalized_extract_method,
        use_llm_cleanup,
        cleanup_provider or "",
        cleanup_model or "",
    )

    result = run_ingestion(
        pdf_bytes,
        source_name=source,
        extract_method=normalized_extract_method,
        use_llm_cleanup=use_llm_cleanup,
        cleanup_provider=cleanup_provider.strip() or None,
        cleanup_model=cleanup_model.strip() or None,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "인입 실패"))

    logger.debug(
        "[DOC_INGEST_DONE] source=%s chunks_created=%s points_upserted=%s",
        source,
        result.get("chunks_created", 0),
        result.get("points_upserted", 0),
    )
    return result


@router.post("/extract-text")
async def extract_text_from_pdf(
    file: UploadFile = File(..., description="텍스트를 추출할 PDF 파일"),
    extract_method: str = Query(
        "",
        description="PDF 텍스트 추출 방식 (pypdf | vision_qwen), 비우면 서버 기본값",
    ),
) -> dict:
    """
    1단계용 API: PDF 업로드 -> 텍스트 추출만 수행.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    try:
        pdf_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 읽기 실패: {e!s}")

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="파일 내용이 비어 있습니다.")

    method = _normalize_extract_method(extract_method)
    logger.debug(
        "[DOC_EXTRACT_START] filename=%s size_bytes=%s method=%s",
        file.filename,
        len(pdf_bytes),
        method,
    )
    try:
        text = load_text_from_pdf_bytes(pdf_bytes, extract_method=method)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"텍스트 추출 실패: {e!s}")

    logger.debug(
        "[DOC_EXTRACT_DONE] filename=%s method=%s text_len=%s",
        file.filename,
        method,
        len(text),
    )
    return {
        "ok": True,
        "filename": file.filename,
        "extract_method": method,
        "text": text,
        "text_len": len(text),
    }


@router.post("/extract-text-stream")
async def extract_text_from_pdf_stream(
    file: UploadFile = File(..., description="텍스트를 추출할 PDF 파일"),
    extract_method: str = Query(
        "",
        description="PDF 텍스트 추출 방식 (pypdf | vision_qwen), 비우면 서버 기본값",
    ),
):
    """
    PDF 텍스트 추출을 수행하면서 진행 로그를 SSE(Server-Sent Events)로 실시간 스트리밍합니다.
    이벤트: type=log (message) / type=result (ok, text, text_len) / type=error (error)
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    try:
        pdf_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 읽기 실패: {e!s}")

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="파일 내용이 비어 있습니다.")

    try:
        method = _normalize_extract_method(extract_method)
    except HTTPException:
        raise

    log_queue: Queue = Queue()
    pdf_logger = logging.getLogger("rag_ai.ingestion.pdf_loader")
    handler = _QueueLogHandler(log_queue)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    pdf_logger.addHandler(handler)
    pdf_logger.setLevel(logging.INFO)

    log_queue.put(
        ("LOG", f"{time.strftime('%Y-%m-%d %H:%M:%S')} | INFO | rag_ai.api.documents | [extract-text-stream] 시작. method={method}, filename={file.filename}, size_bytes={len(pdf_bytes)}")
    )

    cancelled = threading.Event()
    result_holder: list[tuple[str, str | None]] = []

    def run_extraction() -> None:
        try:
            text = load_text_from_pdf_bytes(pdf_bytes, extract_method=method, cancelled=cancelled)
            result_holder.append(("RESULT", text))
        except ExtractionCancelled:
            result_holder.append(("CANCELLED", None))
        except Exception as e:
            result_holder.append(("ERROR", str(e)))
        finally:
            pdf_logger.removeHandler(handler)
            log_queue.put(_LOG_QUEUE_SENTINEL)

    thread = threading.Thread(target=run_extraction)
    thread.start()

    def _queue_get_no_block():
        try:
            return log_queue.get(timeout=0.25)
        except Empty:
            return None

    _heartbeat_interval = 15.0  # 페이지당 수 분 걸릴 수 있으므로 SSE 연결 유지용

    async def event_stream():
        loop = asyncio.get_event_loop()
        last_heartbeat = time.monotonic()
        try:
            while True:
                item = await loop.run_in_executor(None, _queue_get_no_block)
                if item is None:
                    now = time.monotonic()
                    if now - last_heartbeat >= _heartbeat_interval:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    await asyncio.sleep(0.05)
                    continue
                if item == _LOG_QUEUE_SENTINEL:
                    if result_holder:
                        kind, value = result_holder[0]
                        if kind == "RESULT":
                            payload = {
                                "type": "result",
                                "ok": True,
                                "text": value,
                                "text_len": len(value) if value else 0,
                            }
                        elif kind == "CANCELLED":
                            payload = {"type": "cancelled", "ok": False, "message": "취소되었습니다."}
                        else:
                            payload = {"type": "error", "ok": False, "error": value or ""}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    break
                if item[0] == "LOG":
                    last_heartbeat = time.monotonic()
                    yield f"data: {json.dumps({'type': 'log', 'message': item[1]}, ensure_ascii=False)}\n\n"
        except (GeneratorExit, BaseException):
            cancelled.set()
            raise
        finally:
            thread.join(timeout=2.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cleanup-text")
async def cleanup_text(req: CleanupTextRequest) -> dict:
    """
    2~3단계용 API: 텍스트를 LLM 정제하거나(옵션) 그대로 통과.
    """
    raw_text = (req.text or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="text가 비어 있습니다.")

    if not req.use_cleanup:
        delimiter = (req.cleanup_delimiter or "###").strip() or "###"
        prefixed_text = (
            "다음은 pdf의 글자만 추출한 내용입니다. 의미없는 데이터가 많지요.\n"
            "500~1000자 정도의 의미 있는 청크로 분할하여, 마크다운 형식의 텍스트로 출력해 주세요.\n"
            "주석(루비)는 생략하고 본문만 추출해 주세요. 원문은 생략하지 말고 그대로 출력해 주세요.\n"
            "결과는 아티팩트(artifact)로 출력해 주세요.\n"
            f"구분 기호는 {delimiter}로 지정하고, 청크의 헤더에 짧은 요약문을 포함해 주세요.\n\n"
            f"{raw_text}"
        )
        return {
            "ok": True,
            "cleanup_used": False,
            "provider": "",
            "model": "",
            "text": prefixed_text,
            "text_len": len(prefixed_text),
        }

    provider = (req.cleanup_provider or settings.cleanup_provider or settings.llm_provider).strip().lower()
    model = req.cleanup_model.strip() or ""
    logger.debug(
        "[DOC_CLEANUP_START] provider=%s model=%s text_len=%s",
        provider,
        model,
        len(raw_text),
    )
    try:
        cleaned = preprocess_text_with_llm(
            raw_text=raw_text,
            provider=provider,
            model_override=model or None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"텍스트 정제 실패: {e!s}")

    logger.debug(
        "[DOC_CLEANUP_DONE] provider=%s model=%s cleaned_len=%s",
        provider,
        model,
        len(cleaned),
    )
    return {
        "ok": True,
        "cleanup_used": True,
        "provider": provider,
        "model": model,
        "text": cleaned,
        "text_len": len(cleaned),
    }


@router.post("/chunk-text")
async def chunk_text_api(req: ChunkTextRequest) -> dict:
    """
    4단계용 API: 텍스트를 청킹하고 결과를 반환.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text가 비어 있습니다.")

    mode = "char_window"
    chunks: list[str] = []
    if req.prefer_markdown_h3:
        delimiter = (req.chunk_delimiter or "###").strip() or "###"
        chunks = chunk_markdown_by_delimiter(text, delimiter=delimiter)
        if chunks:
            mode = "markdown_delimiter"

    if not chunks:
        chunks = chunk_text(
            text,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
        )

    logger.debug(
        "[DOC_CHUNK_DONE] mode=%s chunks=%s delimiter=%s chunk_size=%s overlap=%s",
        mode,
        len(chunks),
        (req.chunk_delimiter or "###").strip() or "###",
        req.chunk_size,
        req.chunk_overlap,
    )
    return {
        "ok": True,
        "mode": mode,
        "chunks_count": len(chunks),
        "chunks": chunks,
    }


@router.post("/save-chunks")
async def save_chunks(req: SaveChunksRequest) -> dict:
    """
    5단계용 API: 확정된 청크를 임베딩 후 Qdrant에 저장.
    """
    chunks = [c for c in req.chunks if (c or "").strip()]
    if not chunks:
        raise HTTPException(status_code=400, detail="저장할 chunks가 없습니다.")

    provider = (req.embedding_provider or settings.embedding_provider).strip().lower()
    source = req.source_name.strip() or "upload"
    collection = settings.qdrant_collection

    logger.debug(
        "[DOC_SAVE_START] source=%s chunks=%s embedding_provider=%s collection=%s",
        source,
        len(chunks),
        provider,
        collection,
    )
    try:
        vectors = embed_texts(chunks, provider=provider)
        client = get_qdrant_client()
        ensure_collection(client, collection, dim=len(vectors[0]) if vectors else 1536)
        metadata_list = [{"source": source}] * len(chunks)
        ids = upsert_chunks(client, collection, vectors, chunks, metadata_list=metadata_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qdrant 저장 실패: {e!s}")

    logger.debug(
        "[DOC_SAVE_DONE] source=%s points_upserted=%s collection=%s",
        source,
        len(ids),
        collection,
    )
    return {
        "ok": True,
        "source": source,
        "collection": collection,
        "chunks_count": len(chunks),
        "points_upserted": len(ids),
    }
