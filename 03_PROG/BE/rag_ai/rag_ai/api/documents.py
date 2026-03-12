# documents.py
# 문서 업로드 및 PDF 인입 API 엔드포인트를 정의합니다.

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from rag_ai.services.ingestion_pipeline import run_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("rag_ai.api.documents")


@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(..., description="업로드할 PDF 파일"),
    source_name: str = Query("", description="문서 출처 이름 (비우면 파일명 사용)"),
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
    logger.debug(
        "[DOC_INGEST] filename=%s source=%s size_bytes=%s",
        file.filename,
        source,
        len(pdf_bytes),
    )

    result = run_ingestion(pdf_bytes, source_name=source)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "인입 실패"))

    logger.debug(
        "[DOC_INGEST_DONE] source=%s chunks_created=%s points_upserted=%s",
        source,
        result.get("chunks_created", 0),
        result.get("points_upserted", 0),
    )
    return result
