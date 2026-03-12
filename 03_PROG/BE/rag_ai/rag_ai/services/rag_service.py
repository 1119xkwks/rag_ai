# rag_service.py
# 질문이 들어왔을 때 RAG 흐름(검색 → 컨텍스트 구성 → LLM 답변)을 수행하는 서비스입니다.
#
# 이 파일의 목적:
# - API 레이어(`/chat/ask`)에서는 HTTP 입/출력만 다루고,
# - 실제 RAG 로직은 여기 서비스 레이어에 모아두기 위함입니다.

from typing import Any, List

import httpx
import json
import logging
import time
from openai import APIConnectionError
from openai import APITimeoutError
from openai import OpenAI

from rag_ai.config import settings
from rag_ai.services.embedding_service import embed_single
from rag_ai.services.vector_service import ensure_collection, get_qdrant_client, search_similar

logger = logging.getLogger("rag_ai.services.rag")


def _llm_full_url(provider: str, model_name: str) -> str:
    """
    provider별 LLM 호출 full URL을 사람이 바로 확인할 수 있는 형태로 반환합니다.
    """
    if provider == "vllm":
        return f"{settings.vllm_api_url.rstrip('/')}/chat/completions"
    if provider == "openai":
        return "https://api.openai.com/v1/chat/completions"
    # Gemini는 model별 endpoint를 사용합니다.
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"


def _embedding_full_url(provider: str) -> str:
    """
    provider별 임베딩 호출 full URL을 반환합니다.
    """
    if provider == "vllm":
        return f"{settings.vllm_api_url.rstrip('/')}/embeddings"
    if provider == "openai":
        return "https://api.openai.com/v1/embeddings"
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_embedding_model}:embedContent"
    )


def build_context_from_hits(hits: List[dict[str, Any]], max_chars: int = 4000) -> str:
    """
    Qdrant 검색 결과(hits)에서 payload.text를 모아 LLM에 넣을 컨텍스트 문자열을 만듭니다.

    인자:
        hits: vector_service.search_similar()의 반환 결과 리스트
        max_chars: 컨텍스트가 너무 길어지지 않도록 최대 글자 수 제한

    반환:
        LLM 프롬프트에 넣을 컨텍스트 텍스트(문서 발췌 모음)
    """
    parts: List[str] = []
    total = 0

    for idx, hit in enumerate(hits, start=1):
        payload = hit.get("payload") or {}
        text = (payload.get("text") or "").strip()
        source = payload.get("source") or ""

        if not text:
            continue

        # 사람(학습자)이 보면 출처를 추적하기 쉬우므로, 간단한 헤더를 붙입니다.
        header = f"[{idx}] source={source} score={hit.get('score')}\n"
        block = header + text + "\n"

        # max_chars를 넘기면 더 이상 추가하지 않습니다.
        if total + len(block) > max_chars:
            break

        parts.append(block)
        total += len(block)

    return "\n".join(parts).strip()


def answer_with_rag(
    question: str,
    top_k: int = 5,
    source: str | None = None,
    llm_provider_override: str | None = None,
    embedding_provider_override: str | None = None,
    llm_model_override: str | None = None,
) -> dict[str, Any]:
    """
    질문을 받아 RAG 방식으로 답변을 생성합니다.

    인자:
        question: 사용자 질문(자연어)
        top_k: Qdrant에서 가져올 관련 청크 개수
        source: (선택) 특정 문서(source) 범위에서만 검색하고 싶을 때 사용
        llm_provider_override: (선택) 요청 단위 provider 오버라이드 값 (openai | vllm | gemini)
        embedding_provider_override: (선택) 요청 단위 임베딩 provider 오버라이드 값 (openai | vllm | gemini)
        llm_model_override: (선택) 요청 단위 모델명 오버라이드

    반환:
        answer: 최종 답변
        contexts: 사용된 검색 결과(원문/score/source 등)
    """
    if not question or not question.strip():
        return {"ok": False, "error": "question이 비어 있습니다."}

    # 요청 값이 있으면 우선 사용하고, 없으면 서버 기본값(settings.llm_provider)을 사용합니다.
    provider = (llm_provider_override or settings.llm_provider).strip().lower()
    embedding_provider = (
        embedding_provider_override or settings.embedding_provider
    ).strip().lower()

    # 허용되지 않은 값이면 미리 에러를 반환해, 어떤 값이 가능한지 안내합니다.
    if provider not in {"openai", "vllm", "gemini"}:
        return {
            "ok": False,
            "error": "llm_provider는 openai, vllm, gemini 중 하나여야 합니다.",
        }

    if embedding_provider not in {"openai", "vllm", "gemini"}:
        return {
            "ok": False,
            "error": "embedding_provider는 openai, vllm, gemini 중 하나여야 합니다.",
        }

    # LLM provider가 OpenAI일 때만 OPENAI_API_KEY를 필수로 체크합니다.
    if provider == "openai" and not settings.openai_api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY가 설정되어 있지 않습니다. (.env 또는 환경 변수에 설정 필요)",
        }

    # 임베딩 provider가 openai라면 OpenAI 키가 필요합니다.
    if embedding_provider == "openai" and not settings.openai_api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY가 없어 질문 임베딩을 만들 수 없습니다.",
        }

    if embedding_provider == "gemini" and not settings.gemini_api_key:
        return {
            "ok": False,
            "error": "GEMINI_API_KEY가 없어 Gemini 임베딩을 만들 수 없습니다.",
        }

    # 1) 질문을 임베딩해서 벡터로 변환합니다.
    t0 = time.perf_counter()
    logger.debug(
        "[RAG_STEP_START] step=embed_question provider=%s full_url=%s question_len=%s",
        embedding_provider,
        _embedding_full_url(embedding_provider),
        len(question),
    )
    try:
        query_vector = embed_single(question, provider=embedding_provider)
    except APITimeoutError:
        timeout_sec = (
            settings.vllm_timeout_sec if embedding_provider == "vllm" else settings.openai_timeout_sec
        )
        return {
            "ok": False,
            "error": (
                "질문 임베딩 생성이 timeout 되었습니다. "
                f"embedding_provider={embedding_provider}, timeout_sec={timeout_sec}"
            ),
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "error": (
                "질문 임베딩 생성이 timeout 되었습니다. "
                f"embedding_provider={embedding_provider}, timeout_sec={settings.gemini_timeout_sec}"
            ),
        }
    if not query_vector:
        return {"ok": False, "error": "질문 임베딩 생성에 실패했습니다."}
    logger.debug(
        "[RAG_STEP_DONE] step=embed_question provider=%s vector_dim=%s elapsed_ms=%.1f",
        embedding_provider,
        len(query_vector),
        (time.perf_counter() - t0) * 1000,
    )

    # 2) Qdrant에서 유사한 청크를 검색합니다.
    #    연결 실패 시 "어디로 붙으려 했는지(host/port)"를 같이 반환해 진단을 쉽게 합니다.
    t1 = time.perf_counter()
    logger.debug(
        "[RAG_STEP_START] step=qdrant_search host=%s port=%s collection=%s top_k=%s source=%s",
        settings.qdrant_host,
        settings.qdrant_port,
        settings.qdrant_collection,
        top_k,
        source or "",
    )
    try:
        qdrant = get_qdrant_client()
        # 컬렉션이 아직 없으면(초기 상태) 자동으로 생성해 404를 방지합니다.
        # 벡터 차원은 현재 질문 임베딩 벡터 길이에 맞춥니다.
        ensure_collection(
            client=qdrant,
            collection_name=settings.qdrant_collection,
            dim=len(query_vector),
        )
        hits = search_similar(
            client=qdrant,
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            top_k=top_k,
            source=source,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": (
                "Qdrant 검색 중 연결 오류가 발생했습니다. "
                f"target={settings.qdrant_host}:{settings.qdrant_port}, "
                f"collection={settings.qdrant_collection}, detail={e!s}"
            ),
        }
    logger.debug(
        "[RAG_STEP_DONE] step=qdrant_search hits=%s elapsed_ms=%.1f",
        len(hits),
        (time.perf_counter() - t1) * 1000,
    )

    # 3) 검색 결과에서 LLM에 넣을 컨텍스트를 구성합니다.
    context = build_context_from_hits(hits)

    # 4) LLM에게 “문서 컨텍스트 기반으로 답변”하도록 요청합니다.
    #    - 아직 스트리밍/툴 호출은 하지 않고, 가장 단순한 형태로 구현합니다.
    t2 = time.perf_counter()
    logger.debug(
        "[RAG_STEP_START] step=llm_generate provider=%s model=%s full_url=%s context_len=%s",
        provider,
        settings.gemini_chat_model if provider == "gemini" else (
            settings.vllm_model_name if provider == "vllm" else settings.openai_chat_model
        ),
        _llm_full_url(
            provider,
            settings.gemini_chat_model if provider == "gemini" else (
                settings.vllm_model_name if provider == "vllm" else settings.openai_chat_model
            ),
        ),
        len(context),
    )

    # provider 설정에 따라 OpenAI 또는 vLLM(OpenAI 호환) 클라이언트를 생성합니다.
    if provider == "vllm":
        # 회사 내부 vLLM 서버: OpenAI 호환 엔드포인트를 사용합니다.
        # - base_url: 예) http://192.168.1.111:8000/v1
        # - api_key: vLLM은 보통 키가 필요 없지만, 클라이언트가 필드를 요구하므로 dummy 사용
        client = OpenAI(
            base_url=settings.vllm_api_url,
            api_key=settings.vllm_api_key or "EMPTY",
            timeout=settings.vllm_timeout_sec,
        )
        model_name = llm_model_override or settings.vllm_model_name
    elif provider == "gemini":
        # Gemini는 REST API(generateContent)로 호출합니다.
        if not settings.gemini_api_key:
            return {
                "ok": False,
                "error": "GEMINI_API_KEY가 설정되어 있지 않습니다.",
            }
        model_name = llm_model_override or settings.gemini_chat_model
    else:
        # 기본: OpenAI Chat API 사용
        client = OpenAI(
            api_key=settings.openai_api_key or None,
            timeout=settings.openai_timeout_sec,
        )
        model_name = llm_model_override or settings.openai_chat_model

    # source가 있으면 RAG 컨텍스트 기반 프롬프트를 사용하고,
    # source가 비어 있으면 사용자가 입력한 질문 원문만 그대로 전달합니다.
    if source:
        system_prompt = (
            "너는 문서 기반 질의응답 도우미다.\n"
            "사용자가 질문하면, 제공된 문서 컨텍스트 안에서만 근거를 찾아 답변한다.\n"
            "컨텍스트에 근거가 부족하면, 모른다고 말하고 어떤 정보가 더 필요한지 제안한다.\n"
            "답변은 한국어로, 가능한 한 간결하고 명확하게 작성한다."
        )
        user_prompt = (
            "아래는 문서에서 검색된 발췌 내용(컨텍스트)이다.\n"
            "이 컨텍스트를 근거로 질문에 답하라.\n\n"
            f"## 컨텍스트\n{context if context else '(검색 결과 없음)'}\n\n"
            f"## 질문\n{question}\n"
        )
    else:
        system_prompt = (
            "너는 도움이 되는 한국어 AI 도우미다.\n"
            "사용자의 질문 의도를 파악해 정확하고 간결하게 답변한다."
        )
        user_prompt = question

    # 디버깅 편의를 위해 LLM 요청 payload를 JSON 문자열로 출력합니다.
    # SDK 기본 로그는 Python dict 형태(repr)로 보일 수 있어, 사람이 읽기 쉬운 JSON 로그를 별도로 남깁니다.
    if provider in {"openai", "vllm"}:
        llm_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        logger.debug(
            "[LLM_PAYLOAD_JSON] provider=%s full_url=%s payload=%s",
            provider,
            _llm_full_url(provider, model_name),
            json.dumps(llm_payload, ensure_ascii=False),
        )

    if provider == "gemini":
        gemini_payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        logger.debug(
            "[LLM_PAYLOAD_JSON] provider=gemini full_url=%s payload=%s",
            _llm_full_url(provider, model_name),
            json.dumps(gemini_payload, ensure_ascii=False),
        )

        # Gemini API의 generateContent 형식으로 요청합니다.
        # 참고: system_prompt는 systemInstruction에 넣고, 질문+컨텍스트는 user content로 보냅니다.
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        )
        timeout = httpx.Timeout(
            connect=min(settings.gemini_timeout_sec, 30.0),
            read=settings.gemini_timeout_sec,
            write=min(settings.gemini_timeout_sec, 30.0),
            pool=min(settings.gemini_timeout_sec, 30.0),
        )
        try:
            with httpx.Client(timeout=timeout) as http_client:
                response = http_client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                json=gemini_payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            return {
                "ok": False,
                "error": (
                    "Gemini LLM 요청이 timeout 되었습니다. "
                    f"provider=gemini, model={model_name}, timeout_sec={settings.gemini_timeout_sec}"
                ),
            }

        candidates = data.get("candidates", [])
        if not candidates:
            return {"ok": False, "error": "Gemini 응답에 candidates가 없습니다."}

        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        answer = ""
        for part in parts:
            text = part.get("text")
            if text:
                answer += text
        answer = answer.strip()
    else:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,  # 너무 창의적이지 않게(근거 기반 답변 유도)
            )
            answer = (completion.choices[0].message.content or "").strip()
        except APIConnectionError as e:
            # 내부망 LLM 서버(vLLM) 접근 실패 시 원인 파악이 쉽도록 endpoint 정보를 포함해 반환
            # 예: VPN 미연결, 방화벽 차단, 서버 down, 잘못된 IP/포트
            endpoint = settings.vllm_api_url if provider == "vllm" else "openai"
            return {
                "ok": False,
                "error": (
                    "LLM 서버 연결에 실패했습니다. "
                    f"provider={provider}, endpoint={endpoint}, model={model_name}, detail={e!s}"
                ),
            }
        except APITimeoutError:
            return {
                "ok": False,
                "error": (
                    "LLM 요청이 timeout 되었습니다. "
                    f"provider={provider}, model={model_name}, "
                    f"timeout_sec={settings.vllm_timeout_sec if provider == 'vllm' else settings.openai_timeout_sec}"
                ),
            }

    logger.debug(
        "[RAG_STEP_DONE] step=llm_generate provider=%s model=%s answer_len=%s elapsed_ms=%.1f",
        provider,
        model_name,
        len(answer),
        (time.perf_counter() - t2) * 1000,
    )

    return {
        "ok": True,
        "answer": answer,
        "contexts": hits,  # 프론트에서 “근거”로 보여줄 수 있도록 그대로 반환
        "used_source_filter": source or "",
        "used_llm_provider": provider,
        "used_llm_model": model_name,
        "used_embedding_provider": embedding_provider,
        "collection": settings.qdrant_collection,
    }


def list_available_models(provider: str) -> dict[str, Any]:
    """
    provider별 사용 가능한 모델 목록을 조회합니다.

    반환 형식:
    {
        "ok": True/False,
        "provider": "...",
        "models": ["model-a", "model-b", ...],
        "error": "..."  # 실패 시
    }
    """
    p = (provider or "").strip().lower()
    if p not in {"openai", "vllm", "gemini"}:
        return {
            "ok": False,
            "provider": p,
            "models": [],
            "error": "provider는 openai, vllm, gemini 중 하나여야 합니다.",
        }

    # Gemini는 우선 설정된 모델을 중심으로 간단 목록을 제공합니다.
    # (필요 시 Google 모델 목록 API 호출로 확장 가능)
    if p == "gemini":
        models = [settings.gemini_chat_model]
        # 중복 제거
        models = list(dict.fromkeys([m for m in models if m]))
        return {"ok": True, "provider": "gemini", "models": models}

    # OpenAI / vLLM은 OpenAI 호환 API의 /v1/models를 조회합니다.
    try:
        if p == "vllm":
            client = OpenAI(
                base_url=settings.vllm_api_url,
                api_key=settings.vllm_api_key or "EMPTY",
                timeout=settings.vllm_timeout_sec,
            )
        else:
            if not settings.openai_api_key:
                return {
                    "ok": False,
                    "provider": "openai",
                    "models": [],
                    "error": "OPENAI_API_KEY가 설정되어 있지 않습니다.",
                }
            client = OpenAI(
                api_key=settings.openai_api_key or None,
                timeout=settings.openai_timeout_sec,
            )

        logger.debug(
            "[MODEL_LIST_START] provider=%s full_url=%s",
            p,
            f"{settings.vllm_api_url.rstrip('/')}/models" if p == "vllm" else "https://api.openai.com/v1/models",
        )
        res = client.models.list()
        model_ids = sorted({m.id for m in res.data if getattr(m, "id", None)})
        logger.debug("[MODEL_LIST_DONE] provider=%s count=%s", p, len(model_ids))
        return {"ok": True, "provider": p, "models": model_ids}
    except APIConnectionError as e:
        endpoint = settings.vllm_api_url if p == "vllm" else "https://api.openai.com/v1"
        return {
            "ok": False,
            "provider": p,
            "models": [],
            "error": f"모델 목록 서버 연결 실패 provider={p}, endpoint={endpoint}, detail={e!s}",
        }
    except APITimeoutError:
        timeout_sec = settings.vllm_timeout_sec if p == "vllm" else settings.openai_timeout_sec
        return {
            "ok": False,
            "provider": p,
            "models": [],
            "error": f"모델 목록 조회 timeout provider={p}, timeout_sec={timeout_sec}",
        }
    except Exception as e:
        return {
            "ok": False,
            "provider": p,
            "models": [],
            "error": f"모델 목록 조회 실패 provider={p}, detail={e!s}",
        }

