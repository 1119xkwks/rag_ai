"""
pdf_loader.py
PDF 텍스트 추출 모듈.

- 기본: pypdf 텍스트 레이어 추출
- 옵션: vision_qwen (PDF를 이미지로 렌더링 후 Qwen-VL로 OCR/이해)
"""

import io
import logging
from pathlib import Path
import threading
from typing import Any, List

from pypdf import PdfReader

from rag_ai.config import settings

logger = logging.getLogger("rag_ai.ingestion.pdf_loader")


class ExtractionCancelled(Exception):
    """사용자 또는 클라이언트 연결 끊김으로 추출이 취소되었을 때 발생합니다."""
    pass

_QWEN_VL_PIPELINE: Any = None
_QWEN_VL_PIPELINE_MODEL_ID: str = ""


def _normalize_extract_method(extract_method: str | None) -> str:
    method = (extract_method or settings.pdf_extract_method or "pypdf").strip().lower()
    if method not in {"pypdf", "vision_qwen"}:
        raise ValueError("extract_method는 pypdf 또는 vision_qwen 중 하나여야 합니다.")
    return method


def _extract_text_with_pypdf_from_bytes(data: bytes) -> str:
    stream = io.BytesIO(data)
    reader = PdfReader(stream)
    parts: List[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_text_with_pypdf_from_path(file_path: str | Path) -> str:
    reader = PdfReader(Path(file_path))
    parts: List[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _get_qwen_vl_pipeline(model_id: str) -> Any:
    global _QWEN_VL_PIPELINE
    global _QWEN_VL_PIPELINE_MODEL_ID

    if _QWEN_VL_PIPELINE is not None and _QWEN_VL_PIPELINE_MODEL_ID == model_id:
        return _QWEN_VL_PIPELINE

    try:
        import torch
        from transformers import pipeline
    except Exception as e:
        raise RuntimeError(
            "vision_qwen 사용을 위해 transformers/torch가 필요합니다. "
            "예: pip install transformers accelerate torch torchvision pillow"
        ) from e

    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    logger.info(
        "[vision_qwen] Hugging Face에서 Qwen-VL 모델 다운로드/로딩 중 (최초 1회, 수 분~수십 분 소요 가능). model=%s",
        model_id,
    )
    _QWEN_VL_PIPELINE = pipeline(
        task="image-text-to-text",
        model=model_id,
        device_map="auto",
        torch_dtype=torch_dtype,
    )
    _QWEN_VL_PIPELINE_MODEL_ID = model_id
    logger.info("[vision_qwen] 모델 로딩 완료. model=%s", model_id)
    return _QWEN_VL_PIPELINE


def _render_pdf_pages_as_images(data: bytes, dpi: int, max_pages: int) -> List[Any]:
    try:
        import pypdfium2 as pdfium
    except Exception as e:
        raise RuntimeError(
            "vision_qwen 사용을 위해 pypdfium2가 필요합니다. 예: pip install pypdfium2"
        ) from e

    pdf = pdfium.PdfDocument(data)
    total_pages = len(pdf)
    page_limit = total_pages if max_pages <= 0 else min(total_pages, max_pages)
    images: List[Any] = []

    scale = max(dpi, 72) / 72.0
    for i in range(page_limit):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        images.append(bitmap.to_pil())
    return images


def _extract_text_from_qwen_output(raw_output: Any) -> str:
    """
    pipeline 출력 포맷이 모델/버전별로 달라서, 재귀적으로 텍스트를 수집합니다.
    """
    texts: List[str] = []

    def walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            if value.strip():
                texts.append(value.strip())
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            # 자주 나오는 키를 우선 탐색
            for key in ("generated_text", "text", "content", "message"):
                if key in value:
                    walk(value[key])
            # 나머지 값도 훑어서 누락을 줄임
            for v in value.values():
                walk(v)

    walk(raw_output)

    # 중복 문장 제거(순서 유지)
    unique_lines: List[str] = []
    seen = set()
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique_lines.append(t)
    return "\n".join(unique_lines).strip()


def _extract_text_with_qwen_vision(
    data: bytes,
    cancelled: threading.Event | None = None,
) -> str:
    """
    vision_qwen 동작 순서:
    1) PDF 각 페이지를 이미지로 렌더링 (pypdfium2)
    2) 최초 1회: Hugging Face에서 Qwen-VL 모델 다운로드 후 메모리 로드
    3) 각 페이지 이미지마다 Qwen-VL로 이미지→텍스트 추출 (OCR/이해)
    cancelled 가 설정되면 ExtractionCancelled 를 발생시킵니다.
    """
    if cancelled and cancelled.is_set():
        raise ExtractionCancelled()

    model_id = settings.qwen_vl_model_id
    max_pages = settings.qwen_vl_max_pages
    dpi = settings.qwen_vl_dpi
    max_new_tokens = settings.qwen_vl_max_new_tokens

    images = _render_pdf_pages_as_images(data=data, dpi=dpi, max_pages=max_pages)
    if not images:
        return ""

    if cancelled and cancelled.is_set():
        raise ExtractionCancelled()

    total = len(images)
    logger.info(
        "[vision_qwen] PDF → 이미지 변환 완료. 총 %s페이지. 이제 Qwen-VL로 페이지별 텍스트 추출을 시작합니다.",
        total,
    )

    pipe = _get_qwen_vl_pipeline(model_id)
    if cancelled and cancelled.is_set():
        raise ExtractionCancelled()

    page_texts: List[str] = []
    prompt = (
        "이 문서 이미지를 OCR/이해해서 텍스트를 최대한 빠짐없이 추출해 주세요. "
        "표의 헤더/셀 텍스트, 그래프 축/범례/라벨/주석 텍스트도 포함해 주세요. "
        "출력은 한국어 설명과 원문 텍스트를 함께, 읽기 순서를 유지해서 plain text로 출력하세요."
    )

    for page_idx, image in enumerate(images, start=1):
        if cancelled and cancelled.is_set():
            raise ExtractionCancelled()
        logger.info(
            "[vision_qwen] PDF 페이지 %s/%s Vision OCR 수행 중 (이미지→텍스트, 페이지당 수 분 걸릴 수 있음)",
            page_idx,
            total,
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        output = pipe(text=messages, max_new_tokens=max_new_tokens)
        extracted = _extract_text_from_qwen_output(output)
        page_texts.append(f"[PAGE {page_idx}]\n{extracted}".strip())
        logger.info(
            "[vision_qwen] PDF 페이지 %s/%s 완료. 추출 글자 수=%s",
            page_idx,
            total,
            len(extracted),
        )

    return "\n\n".join([t for t in page_texts if t.strip()])


def load_text_from_pdf(file_path: str | Path, extract_method: str = "pypdf") -> str:
    """
    PDF 파일 경로를 받아 전체 페이지의 텍스트를 하나의 문자열로 반환합니다.

    인자:
        file_path: PDF 파일의 경로 (문자열 또는 pathlib.Path)

    반환:
        모든 페이지 텍스트를 이어 붙인 하나의 문자열.
        페이지 구분은 공백/줄바꿈으로만 되어 있으므로, 필요 시 chunker에서 잘라 씁니다.

    사용 예:
        ingestion 단계에서 업로드된 PDF를 저장한 뒤, 그 경로를 넘겨 호출합니다.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

    method = _normalize_extract_method(extract_method)
    if method == "pypdf":
        return _extract_text_with_pypdf_from_path(path)

    with path.open("rb") as f:
        data = f.read()
    return _extract_text_with_qwen_vision(data)


def load_text_from_pdf_bytes(
    data: bytes,
    extract_method: str = "pypdf",
    cancelled: threading.Event | None = None,
) -> str:
    """
    PDF 바이트 데이터(예: 업로드된 파일 내용)에서 텍스트를 추출합니다.
    cancelled: 설정되면 vision_qwen 경로에서 주기적으로 확인 후 ExtractionCancelled 를 발생시킵니다.
    """
    if cancelled and cancelled.is_set():
        raise ExtractionCancelled()
    method = _normalize_extract_method(extract_method)
    logger.debug("[PDF_EXTRACT_START] method=%s bytes=%s", method, len(data))
    if method == "pypdf":
        text = _extract_text_with_pypdf_from_bytes(data)
    else:
        text = _extract_text_with_qwen_vision(data, cancelled=cancelled)
    logger.debug("[PDF_EXTRACT_DONE] method=%s text_len=%s", method, len(text))
    return text
