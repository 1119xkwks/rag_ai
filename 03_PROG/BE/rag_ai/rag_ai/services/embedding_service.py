# embedding_service.py
# 텍스트(또는 청크)를 벡터(숫자 배열)로 변환하는 서비스입니다.
# RAG에서는 이 벡터로 유사도 검색을 하므로, 같은 모델로 질문과 문서를 모두 임베딩해야 합니다.

from typing import List

import httpx
import json
import logging
from openai import OpenAI

from rag_ai.config import settings

logger = logging.getLogger("rag_ai.services.embedding")


def get_embedding_client(provider: str = "openai") -> OpenAI:
    """
    provider에 맞는 임베딩 클라이언트를 생성해서 반환합니다.

    - openai: OpenAI API 키 사용
    - vllm  : 내부 vLLM(OpenAI 호환) 엔드포인트 사용
    - gemini: Gemini는 OpenAI SDK가 아니라 REST API를 사용하므로 여기서는 None 대체로 처리
    """
    if provider == "gemini":
        # Gemini는 별도 REST 호출 함수(`embed_texts_with_gemini`)에서 처리합니다.
        # 타입 일관성을 위해 기본 OpenAI 객체를 반환하지 않고 예외를 던집니다.
        raise ValueError("gemini provider는 get_embedding_client()가 아닌 전용 함수로 처리합니다.")

    if provider == "vllm":
        # vLLM은 OpenAI 호환 API이므로 base_url만 바꿔 같은 SDK로 호출할 수 있습니다.
        return OpenAI(
            base_url=settings.vllm_api_url,
            api_key=settings.vllm_api_key or "EMPTY",
            timeout=settings.vllm_timeout_sec,
        )

    return OpenAI(
        api_key=settings.openai_api_key or None,
        timeout=settings.openai_timeout_sec,
    )


def embed_texts_with_gemini(texts: List[str]) -> List[List[float]]:
    """
    Gemini Embeddings REST API를 호출해서 임베딩 벡터를 생성합니다.

    참고:
        현재 구현은 텍스트마다 개별 요청을 보내는 단순한 형태입니다.
        학습용/소량 처리 기준으로는 이해하기 쉽고 디버깅이 편합니다.
    """
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

    model = settings.gemini_embedding_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
    logger.debug(
        "[EMBED_CALL] provider=gemini full_url=%s model=%s batch_size=%s",
        url,
        model,
        len(texts),
    )

    vectors: List[List[float]] = []
    # connect/read/write/pool timeout을 분리해 Gemini 호출 시 timeout 튜닝이 쉽도록 구성
    timeout = httpx.Timeout(
        connect=min(settings.gemini_timeout_sec, 30.0),
        read=settings.gemini_timeout_sec,
        write=min(settings.gemini_timeout_sec, 30.0),
        pool=min(settings.gemini_timeout_sec, 30.0),
    )
    with httpx.Client(timeout=timeout) as client:
        for text in texts:
            gemini_embed_payload = {
                "model": f"models/{model}",
                "content": {
                    "parts": [{"text": text}],
                },
            }
            logger.debug(
                "[EMBED_PAYLOAD_JSON] provider=gemini full_url=%s payload=%s",
                url,
                json.dumps(gemini_embed_payload, ensure_ascii=False),
            )
            response = client.post(
                url,
                params={"key": settings.gemini_api_key},
                json=gemini_embed_payload,
            )
            response.raise_for_status()
            data = response.json()
            vector = data.get("embedding", {}).get("values", [])
            if not vector:
                raise ValueError("Gemini 임베딩 응답에 벡터 값이 없습니다.")
            vectors.append(vector)

    return vectors


def embed_texts(texts: List[str], provider: str = "openai") -> List[List[float]]:
    """
    여러 개의 텍스트를 한 번에 임베딩 모델에 넣어 벡터 리스트로 반환합니다.

    인자:
        texts: 임베딩할 문자열 리스트 (예: chunker로 잘라낸 청크들)
        provider: 임베딩 백엔드 선택값 ("openai" | "vllm" | "gemini")

    반환:
        각 텍스트에 대응하는 벡터(실수 리스트)의 리스트.
        Qdrant에 저장할 때 이 벡터를 그대로 사용합니다.

    참고:
        OpenAI API는 한 번에 여러 텍스트를 받을 수 있어서, 배치로 호출하면 비용/속도에 유리합니다.
    """
    if not texts:
        return []

    if provider == "gemini":
        return embed_texts_with_gemini(texts)

    client = get_embedding_client(provider=provider)
    model = (
        settings.vllm_embedding_model
        if provider == "vllm"
        else settings.openai_embedding_model
    )
    full_url = (
        f"{settings.vllm_api_url.rstrip('/')}/embeddings"
        if provider == "vllm"
        else "https://api.openai.com/v1/embeddings"
    )
    logger.debug(
        "[EMBED_CALL] provider=%s full_url=%s model=%s batch_size=%s",
        provider,
        full_url,
        model,
        len(texts),
    )
    logger.debug(
        "[EMBED_PAYLOAD_JSON] provider=%s full_url=%s payload=%s",
        provider,
        full_url,
        json.dumps({"model": model, "input": texts}, ensure_ascii=False),
    )

    # OpenAI Embeddings API 호출. 입력이 리스트이면 응답도 각 텍스트당 벡터 하나씩 반환됨
    response = client.embeddings.create(input=texts, model=model)

    # 응답에서 embedding 벡터만 순서대로 꺼내서 리스트로 만듦
    vectors: List[List[float]] = [item.embedding for item in response.data]
    return vectors


def embed_single(text: str, provider: str = "openai") -> List[float]:
    """
    텍스트 하나만 임베딩할 때 편의용 함수.
    내부적으로 embed_texts([text])를 호출하고 첫 번째 벡터만 반환합니다.
    """
    vectors = embed_texts([text], provider=provider)
    return vectors[0] if vectors else []
