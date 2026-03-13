# text_cleanup_service.py
# PDF에서 추출된 난잡한 텍스트를 LLM으로 정제해
# "### 헤더 + 본문" 형태의 마크다운으로 바꾸는 서비스입니다.

from typing import Any

import httpx
import logging
import time
from openai import OpenAI

from rag_ai.config import settings

logger = logging.getLogger("rag_ai.services.text_cleanup")


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
        "출력은 순수 마크다운 텍스트만 출력해 주세요.\n\n"
        "=== 원문 시작 ===\n"
        f"{raw_text}\n"
        "=== 원문 끝 ===\n"
    )


def preprocess_text_with_llm(
    raw_text: str,
    provider: str,
    model_override: str | None = None,
) -> str:
    """
    원문 텍스트를 LLM으로 정제해 마크다운 문자열로 반환합니다.

    인자:
        raw_text: PDF 추출 원문 텍스트
        provider: openai | vllm | gemini
        model_override: 사용 모델 강제 지정(선택)
    """
    p = (provider or "").strip().lower()
    if p not in {"openai", "vllm", "gemini"}:
        raise ValueError("cleanup provider는 openai, vllm, gemini 중 하나여야 합니다.")

    model_name = (model_override or _default_model_for_provider(p)).strip()
    prompt = _build_cleanup_prompt(raw_text)
    system_text = (
        "너는 문서 정제 도우미다. 손상된 PDF 추출 텍스트를 가독성 높은 구조로 정리한다."
    )

    if p == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        )
        t = time.perf_counter()
        logger.debug(
            "[CLEANUP_LLM_START] provider=gemini model=%s full_url=%s raw_text_len=%s",
            model_name,
            url,
            len(raw_text),
        )
        timeout = httpx.Timeout(
            connect=min(settings.gemini_timeout_sec, 30.0),
            read=settings.gemini_timeout_sec,
            write=min(settings.gemini_timeout_sec, 30.0),
            pool=min(settings.gemini_timeout_sec, 30.0),
        )

        with httpx.Client(timeout=timeout) as client:
            res = client.post(
                url,
                params={"key": settings.gemini_api_key},
                json={
                    "system_instruction": {"parts": [{"text": system_text}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0},
                },
            )
            res.raise_for_status()
            data: dict[str, Any] = res.json()

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
        return text

    if p == "vllm":
        t = time.perf_counter()
        logger.debug(
            "[CLEANUP_LLM_START] provider=vllm model=%s full_url=%s raw_text_len=%s",
            model_name,
            f"{settings.vllm_api_url.rstrip('/')}/chat/completions",
            len(raw_text),
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
        logger.debug(
            "[CLEANUP_LLM_START] provider=openai model=%s full_url=%s raw_text_len=%s",
            model_name,
            "https://api.openai.com/v1/chat/completions",
            len(raw_text),
        )
        client = OpenAI(
            api_key=settings.openai_api_key or None,
            timeout=settings.openai_timeout_sec,
        )

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    text = (completion.choices[0].message.content or "").strip()
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

