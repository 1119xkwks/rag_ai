# text_cleanup_service.py
# PDF에서 추출된 난잡한 텍스트를 LLM으로 정제해
# "### 헤더 + 본문" 형태의 마크다운으로 바꾸는 서비스입니다.
# Gemini일 때 원문이 길면 Files API로 첨부해 요청합니다.

import json
from typing import Any

import httpx
import logging
import time
from openai import OpenAI

from rag_ai.config import settings

logger = logging.getLogger("rag_ai.services.text_cleanup")

_GEMINI_UPLOAD_BASE = "https://generativelanguage.googleapis.com/upload/v1beta"
_GEMINI_FILES_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_MAX_RETRIES = 5
_GEMINI_BACKOFF_BASE_SEC = 2.0
_GEMINI_BACKOFF_MAX_SEC = 30.0


def _emit_llm_request_logs(
    prefix: str,
    *,
    url: str,
    payload: dict[str, Any],
    chunk_size: int = 2000,
) -> None:
    """LLM 요청 URL/payload를 backend logger와 SSE 로그에 남깁니다."""
    payload_json = json.dumps(payload, ensure_ascii=False)
    logger.info("%s request_url=%s", prefix, url)
    logger.info("%s payload_len=%s", prefix, len(payload_json))
    for i, start in enumerate(range(0, len(payload_json), chunk_size), start=1):
        chunk = payload_json[start : start + chunk_size]
        logger.info("%s payload_chunk[%s]=%s", prefix, i, chunk)


def _default_model_for_provider(provider: str) -> str:
    """provider별 기본 모델명을 반환합니다."""
    if provider == "vllm":
        return settings.vllm_model_name
    if provider == "gemini":
        return settings.gemini_chat_model
    return settings.openai_chat_model


def _build_cleanup_prompt(raw_text: str) -> str:
    """
    사용자 요청 문구를 기반으로 정제 프롬프트를 구성합니다.
    - 루비(주석) 제거
    - 원문 누락 없이 보존
    - 500~1000자 의미 단위 청크
    - ### 헤더 + 짧은 요약
    """
    return (
        "아래 원문을 정제해서 마크다운으로 출력해 주세요.\n"
        "500~1000자 정도의 의미 있는 청크로 분할해 주세요.\n"
        "루비(주석)는 생략하고 본문만 추출해 주세요.\n"
        "원문 내용은 생략하지 말고 최대한 보존해 주세요.\n"
        "각 청크는 반드시 '### '로 시작하는 짧은 요약 헤더를 포함해 주세요.\n"
        "출력은 순수 마크다운 텍스트만 출력해 주세요. '알겠습니다', '이해했습니다' 등의 인사말이나 지시사항 복창(예: We need to output markdown text...), 너의 계획이나 추론 과정은 일절 포함하지 마세요. 반드시 첫 번째 청크의 '### ' 헤더로 바로 응답을 시작해야 합니다.\n\n"
        "=== 원문 시작 ===\n"
        f"{raw_text}\n"
        "=== 원문 끝 ===\n"
    )


def _build_cleanup_prompt_file_instruction_only() -> str:
    """첨부 파일용: 원문 없이 지시문만 반환합니다."""
    return (
        "첨부한 원문 파일을 정제해서 마크다운으로 출력해 주세요.\n"
        "500~1000자 정도의 의미 있는 청크로 분할해 주세요.\n"
        "루비(주석)는 생략하고 본문만 추출해 주세요.\n"
        "원문 내용은 생략하지 말고 최대한 보존해 주세요.\n"
        "각 청크는 반드시 '### '로 시작하는 짧은 요약 헤더를 포함해 주세요.\n"
        "출력은 순수 마크다운 텍스트만 출력해 주세요. '알겠습니다', '이해했습니다' 등의 인사말이나 지시사항 복창(예: We need to output markdown text...), 너의 계획이나 추론 과정은 일절 포함하지 마세요. 반드시 첫 번째 청크의 '### ' 헤더로 바로 응답을 시작해야 합니다."
    )


def _gemini_upload_text_file(raw_text: str, timeout_sec: float) -> tuple[str, str]:
    """
    Gemini Files API로 텍스트를 업로드하고 (file_uri, file_name)을 반환합니다.
    file_name은 삭제 시 사용합니다.
    """
    file_bytes = raw_text.encode("utf-8")
    num_bytes = len(file_bytes)
    mime_type = "text/plain"
    display_name = "cleanup_raw.txt"

    start_url = f"{_GEMINI_UPLOAD_BASE}/files"
    with httpx.Client(
        timeout=httpx.Timeout(
            connect=30.0,
            read=timeout_sec,
            write=max(60.0, timeout_sec),
            pool=30.0,
        )
    ) as client:
        start_res = client.post(
            start_url,
            params={"key": settings.gemini_api_key},
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(num_bytes),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": display_name}},
        )
        start_res.raise_for_status()
        upload_url = start_res.headers.get("x-goog-upload-url")
        if not upload_url:
            raise ValueError("Gemini 파일 업로드 시작 응답에 x-goog-upload-url이 없습니다.")

        upload_res = client.post(
            upload_url,
            headers={
                "Content-Length": str(num_bytes),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            content=file_bytes,
        )
        upload_res.raise_for_status()
        data: dict[str, Any] = upload_res.json()
    file_info = data.get("file") or {}
    file_uri = file_info.get("fileUri") or file_info.get("uri") or ""
    file_name = (file_info.get("name") or "").strip()
    if not file_uri:
        raise ValueError("Gemini 파일 업로드 응답에 file_uri가 없습니다.")
    return file_uri, file_name


def _parse_retry_after_seconds(retry_after: str | None) -> float | None:
    """Retry-After 헤더(초 단위 정수)를 파싱합니다."""
    if not retry_after:
        return None
    try:
        sec = float(retry_after.strip())
        return sec if sec >= 0 else None
    except Exception:
        return None


def _gemini_generate_with_retry(
    *,
    client: httpx.Client,
    url: str,
    params: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Gemini generateContent 호출(429/5xx 재시도 포함)."""
    last_error: Exception | None = None
    for attempt in range(1, _GEMINI_MAX_RETRIES + 1):
        try:
            res = client.post(url, params=params, json=payload)
            if res.status_code in {429, 500, 502, 503, 504}:
                retry_after = _parse_retry_after_seconds(res.headers.get("Retry-After"))
                if attempt >= _GEMINI_MAX_RETRIES:
                    res.raise_for_status()
                backoff = retry_after if retry_after is not None else min(
                    _GEMINI_BACKOFF_BASE_SEC * (2 ** (attempt - 1)),
                    _GEMINI_BACKOFF_MAX_SEC,
                )
                logger.warning(
                    "[CLEANUP_LLM_RETRY] provider=gemini status=%s attempt=%s/%s wait_sec=%.1f",
                    res.status_code,
                    attempt,
                    _GEMINI_MAX_RETRIES,
                    backoff,
                )
                time.sleep(backoff)
                continue
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            last_error = e
            if attempt >= _GEMINI_MAX_RETRIES:
                raise
            backoff = min(
                _GEMINI_BACKOFF_BASE_SEC * (2 ** (attempt - 1)),
                _GEMINI_BACKOFF_MAX_SEC,
            )
            logger.warning(
                "[CLEANUP_LLM_RETRY] provider=gemini http_status_error attempt=%s/%s wait_sec=%.1f err=%s",
                attempt,
                _GEMINI_MAX_RETRIES,
                backoff,
                e,
            )
            time.sleep(backoff)
        except httpx.HTTPError as e:
            last_error = e
            if attempt >= _GEMINI_MAX_RETRIES:
                raise
            backoff = min(
                _GEMINI_BACKOFF_BASE_SEC * (2 ** (attempt - 1)),
                _GEMINI_BACKOFF_MAX_SEC,
            )
            logger.warning(
                "[CLEANUP_LLM_RETRY] provider=gemini http_error attempt=%s/%s wait_sec=%.1f err=%s",
                attempt,
                _GEMINI_MAX_RETRIES,
                backoff,
                e,
            )
            time.sleep(backoff)

    if last_error:
        raise last_error
    raise ValueError("Gemini generateContent 호출 실패")


def _strip_vllm_think_prefix(text: str) -> str:
    """
    vLLM 등 모델의 응답에서 '</think>' 블록이나 인사말, 복창 부분을 제거합니다.
    """
    import re
    # 1. <think> ... </think> 블록 제거
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # 2. 닫는 태그만 남아있을 경우 제거
    marker = "</think>"
    if marker in text:
        head, tail = text.split(marker, 1)
        text = tail if tail.strip() else text

    # 3. 모델이 인사말이나 지시사항 복창("We need to output...")을 먼저 한 뒤 ### 로 시작하는 경우, 첫 ### 이전의 텍스트 제거
    text_stripped = text.strip()
    # ### 로 시작하지 않고, 텍스트 중간에 ### 가 있는 경우, 불필요한 서론일 가능성이 높음
    if not text_stripped.startswith("###") and "###" in text_stripped:
        parts = text_stripped.split("###", 1)
        # 서론 부분(parts[0])이 영문 복창이나 단순 안내문(예: Here is the result)일 수 있으므로 제거
        return "###" + parts[1]

    return text_stripped


def preprocess_text_with_llm(
    raw_text: str,
    provider: str,
    model_override: str | None = None,
    gemini_use_file: bool | None = None,
) -> str:
    """
    원문 텍스트를 LLM으로 정제해 마크다운 문자열로 반환합니다.

    인자:
        raw_text: PDF 추출 원문 텍스트
        provider: openai | vllm | gemini
        model_override: 사용 모델 강제 지정(선택)
        gemini_use_file:
            - None: 길이 임계값 기준으로 자동 선택
            - True: Gemini Files API로 txt 첨부 강제
            - False: 인라인 텍스트 강제
    """
    p = (provider or "").strip().lower()
    if p not in {"openai", "vllm", "gemini"}:
        raise ValueError("cleanup provider는 openai, vllm, gemini 중 하나여야 합니다.")

    model_name = (model_override or _default_model_for_provider(p)).strip()
    prompt = _build_cleanup_prompt(raw_text)
    system_text = (
        "너는 문서 정제 도우미다. 손상된 PDF 추출 텍스트를 가독성 높은 구조로 정리한다.\n"
        "500~1000자 정도의 의미 있는 청크로 분할하여, 마크다운 형식의 텍스트로 출력해 주세요.\n"
        "주석(루비)는 생략하고 본문만 추출해 주세요. 원문은 생략하지 말고 그대로 출력해 주세요.\n"
        "결과는 아티팩트(artifact)로 출력해 주세요. 의미없는 공백이나 빈칸 표는 제거해주세요."
    )

    if p == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

        threshold = getattr(settings, "gemini_cleanup_file_threshold_chars", 30_000)
        use_file = (
            gemini_use_file
            if gemini_use_file is not None
            else (threshold > 0 and len(raw_text) > threshold)
        )

        if use_file:
            prompt = _build_cleanup_prompt_file_instruction_only()
            t = time.perf_counter()
            logger.info(
                "[CLEANUP_LLM] provider=gemini raw_text_len=%s → Files API 첨부 업로드",
                len(raw_text),
            )
            file_uri, file_name = _gemini_upload_text_file(
                raw_text, settings.gemini_timeout_sec
            )
            user_parts = [
                {"text": prompt},
                {"file_data": {"mime_type": "text/plain", "file_uri": file_uri}},
            ]
        else:
            prompt = _build_cleanup_prompt(raw_text)
            user_parts = [{"text": prompt}]

        url = f"{_GEMINI_FILES_BASE}/models/{model_name}:generateContent"
        request_payload = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": user_parts}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max(
                    256,
                    int(getattr(settings, "gemini_cleanup_max_output_tokens", 4096)),
                ),
            },
        }
        t = time.perf_counter()
        logger.debug(
            "[CLEANUP_LLM_START] provider=gemini model=%s use_file=%s raw_text_len=%s",
            model_name,
            use_file,
            len(raw_text),
        )
        _emit_llm_request_logs(
            f"[CLEANUP_LLM_REQUEST] provider=gemini model={model_name}",
            url=url,
            payload=request_payload,
        )
        timeout = httpx.Timeout(
            connect=min(settings.gemini_timeout_sec, 30.0),
            read=settings.gemini_timeout_sec,
            write=min(settings.gemini_timeout_sec, 30.0),
            pool=min(settings.gemini_timeout_sec, 30.0),
        )

        try:
            with httpx.Client(timeout=timeout) as client:
                data = _gemini_generate_with_retry(
                    client=client,
                    url=url,
                    params={"key": settings.gemini_api_key},
                    payload=request_payload,
                )
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                raise ValueError(e.response.text) from e
            raise

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini 정제 응답에 candidates가 없습니다.")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join([str(p.get("text", "")) for p in parts]).strip()
        if not text:
            raise ValueError("Gemini 정제 결과 텍스트가 비어 있습니다.")
        logger.debug(
            "[CLEANUP_LLM_DONE] provider=gemini model=%s cleaned_len=%s elapsed_ms=%.1f",
            model_name,
            len(text),
            (time.perf_counter() - t) * 1000,
        )

        if use_file and file_name:
            try:
                delete_name = file_name
                if delete_name.startswith("files/"):
                    delete_name = delete_name[len("files/"):]
                del_res = httpx.delete(
                    f"{_GEMINI_FILES_BASE}/files/{delete_name}",
                    params={"key": settings.gemini_api_key},
                    timeout=10.0,
                )
                if del_res.is_success:
                    logger.debug("[CLEANUP_LLM] Gemini 업로드 파일 삭제 완료 name=%s", file_name)
            except Exception as e:
                logger.debug("[CLEANUP_LLM] Gemini 업로드 파일 삭제 무시: %s", e)

        return text

    if p == "vllm":
        t = time.perf_counter()
        request_url = f"{settings.vllm_api_url.rstrip('/')}/chat/completions"
        request_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        logger.debug(
            "[CLEANUP_LLM_START] provider=vllm model=%s full_url=%s raw_text_len=%s",
            model_name,
            request_url,
            len(raw_text),
        )
        _emit_llm_request_logs(
            f"[CLEANUP_LLM_REQUEST] provider=vllm model={model_name}",
            url=request_url,
            payload=request_payload,
        )
        client = OpenAI(
            base_url=settings.vllm_api_url,
            api_key=settings.vllm_api_key or "EMPTY",
            timeout=settings.vllm_timeout_sec,
        )
    else:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        t = time.perf_counter()
        request_url = "https://api.openai.com/v1/chat/completions"
        request_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        logger.debug(
            "[CLEANUP_LLM_START] provider=openai model=%s full_url=%s raw_text_len=%s",
            model_name,
            request_url,
            len(raw_text),
        )
        _emit_llm_request_logs(
            f"[CLEANUP_LLM_REQUEST] provider=openai model={model_name}",
            url=request_url,
            payload=request_payload,
        )
        client = OpenAI(
            api_key=settings.openai_api_key or None,
            timeout=settings.openai_timeout_sec,
        )

    completion = client.chat.completions.create(**request_payload)
    text = (completion.choices[0].message.content or "").strip()
    if p == "vllm":
        text = _strip_vllm_think_prefix(text)
    if not text:
        raise ValueError("LLM 정제 결과 텍스트가 비어 있습니다.")
    logger.debug(
        "[CLEANUP_LLM_DONE] provider=%s model=%s cleaned_len=%s elapsed_ms=%.1f",
        p,
        model_name,
        len(text),
        (time.perf_counter() - t) * 1000,
    )
    return text

