# chat.py
# 최소 RAG API: 질문을 받으면 Qdrant 검색 + LLM 답변 생성까지 수행합니다.

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from rag_ai.services.rag_service import answer_with_rag, list_available_models

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("rag_ai.api.chat")


class ChatAskRequest(BaseModel):
    # 사용자가 입력하는 질문 텍스트
    question: str = Field(..., description="사용자 질문")

    # 몇 개의 관련 문서 청크를 가져올지 (기본값 5)
    top_k: int = Field(5, ge=1, le=20, description="검색 결과 상위 몇 개를 사용할지")

    # (선택) 특정 문서(source)로 제한해서 검색하고 싶을 때 사용
    # 예: PDF 인입 시 source를 파일명으로 넣었으니, 질문할 때 같은 값을 주면 그 문서 범위에서만 검색함
    source: str = Field("", description="(선택) source 필터. 비우면 전체에서 검색")

    # (선택) 요청 단위로 LLM provider를 오버라이드합니다.
    # - "openai": OpenAI Chat API
    # - "vllm"  : 내부 vLLM(OpenAI 호환) 서버
    # - "gemini": Gemini API
    # - 공백    : 서버 기본 설정(settings.llm_provider) 사용
    llm_provider: str = Field(
        "",
        description="(선택) LLM provider override (openai | vllm | gemini)",
    )

    # (선택) 요청 단위 LLM 모델명 오버라이드
    # 예: vLLM provider에서 "qwen25-14b" 같은 모델명을 직접 지정
    llm_model: str = Field(
        "",
        description="(선택) LLM model override",
    )

    # (선택) 요청 단위 임베딩 provider 오버라이드
    # - "openai": OpenAI 임베딩 API
    # - "vllm"  : 내부 vLLM(OpenAI 호환) 임베딩 API
    # - "gemini": Gemini 임베딩 API
    # - 공백    : 서버 기본 설정(settings.embedding_provider) 사용
    embedding_provider: str = Field(
        "",
        description="(선택) Embedding provider override (openai | vllm | gemini)",
    )


@router.post("/ask")
async def chat_ask(req: ChatAskRequest) -> dict:
    """
    최소 RAG 엔드포인트.

    입력:
        - question: 사용자 질문
        - top_k: 검색에 사용할 청크 개수
        - source: (선택) 특정 문서로 검색 범위를 제한

    출력:
        - answer: LLM이 생성한 최종 답변
        - contexts: 근거로 사용된 문서 청크들(검색 결과)
    """
    logger.debug(
        "[CHAT_ASK] question_len=%s top_k=%s source=%s llm_provider=%s embedding_provider=%s",
        len(req.question or ""),
        req.top_k,
        req.source or "",
        req.llm_provider or "",
        req.embedding_provider or "",
    )

    result = answer_with_rag(
        question=req.question,
        top_k=req.top_k,
        source=req.source.strip() or None,
        llm_provider_override=req.llm_provider.strip() or None,
        embedding_provider_override=req.embedding_provider.strip() or None,
        llm_model_override=req.llm_model.strip() or None,
    )

    logger.debug(
        "[CHAT_ASK_DONE] ok=%s used_llm_provider=%s used_embedding_provider=%s",
        result.get("ok"),
        result.get("used_llm_provider", ""),
        result.get("used_embedding_provider", ""),
    )
    return result


@router.get("/models")
async def chat_models(
    llm_provider: str = Query("vllm", description="모델 목록 조회 대상 provider (openai | vllm | gemini)"),
) -> dict:
    """
    provider별 모델 목록 조회 엔드포인트.

    - vllm  : 내부 vLLM /v1/models 호출
    - openai: OpenAI /v1/models 호출
    - gemini: 현재 설정된 Gemini 모델 목록 반환(간단 목록)
    """
    logger.debug("[CHAT_MODELS] llm_provider=%s", llm_provider)
    result = list_available_models(llm_provider)
    logger.debug(
        "[CHAT_MODELS_DONE] ok=%s provider=%s count=%s",
        result.get("ok"),
        result.get("provider"),
        len(result.get("models", [])),
    )
    return result

