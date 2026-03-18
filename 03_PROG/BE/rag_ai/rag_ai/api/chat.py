# chat.py
# 최소 RAG API: 질문을 받으면 Qdrant 검색 + LLM 답변 생성까지 수행합니다.

import logging
import asyncio
import json
import threading
import time
from queue import Empty, Queue

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
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
    use_vector_db: bool = Field(False, description="Vector DB 사용 여부")
    # (선택) source 미지정 일반 질의에서 tool-calling 사용 여부
    use_tools: bool = Field(True, description="tool-calling 사용 여부")


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
        "[CHAT_ASK] question_len=%s top_k=%s source=%s llm_provider=%s embedding_provider=%s use_vector_db=%s use_tools=%s",
        len(req.question or ""),
        req.top_k,
        req.source or "",
        req.llm_provider or "",
        req.embedding_provider or "",
        req.use_vector_db,
        req.use_tools,
    )

    result = answer_with_rag(
        question=req.question,
        top_k=req.top_k,
        source=req.source.strip() or None,
        llm_provider_override=req.llm_provider.strip() or None,
        embedding_provider_override=req.embedding_provider.strip() or None,
        llm_model_override=req.llm_model.strip() or None,
        use_vector_db=req.use_vector_db,
        use_tools=req.use_tools,
    )

    logger.debug(
        "[CHAT_ASK_DONE] ok=%s used_llm_provider=%s used_embedding_provider=%s",
        result.get("ok"),
        result.get("used_llm_provider", ""),
        result.get("used_embedding_provider", ""),
    )
    return result


@router.post("/ask-stream")
async def chat_ask_stream(req: ChatAskRequest):
    """
    RAG 채팅을 SSE(Server-Sent Events)로 스트리밍합니다.
    이벤트: type=log (message) / type=result (answer, contexts, ...) / type=error (error)
    """
    log_queue: Queue = Queue()
    result_holder: list[tuple[str, dict | str]] = []
    sentinel = ("_END_", None)

    def push_log(message: str) -> None:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info("%s", message)
        log_queue.put(("LOG", f"{now} | INFO | rag_ai.api.chat | {message}"))

    push_log(
        f"[ask-stream] 시작. question_len={len(req.question or '')}, top_k={req.top_k}, source={req.source or '-'}, llm_provider={req.llm_provider or '-'}, embedding_provider={req.embedding_provider or '-'}, use_vector_db={req.use_vector_db}, use_tools={req.use_tools}"
    )

    def run_ask() -> None:
        try:
            result = answer_with_rag(
                question=req.question,
                top_k=req.top_k,
                source=req.source.strip() or None,
                llm_provider_override=req.llm_provider.strip() or None,
                embedding_provider_override=req.embedding_provider.strip() or None,
                llm_model_override=req.llm_model.strip() or None,
                use_vector_db=req.use_vector_db,
                use_tools=req.use_tools,
                progress_callback=push_log,
            )
            result_holder.append(("RESULT", result))
        except Exception as e:
            result_holder.append(("ERROR", str(e)))
        finally:
            log_queue.put(sentinel)

    thread = threading.Thread(target=run_ask)
    thread.start()

    def _queue_get_no_block():
        try:
            return log_queue.get(timeout=0.25)
        except Empty:
            return None

    heartbeat_interval = 15.0

    async def event_stream():
        loop = asyncio.get_event_loop()
        last_heartbeat = time.monotonic()
        try:
            while True:
                item = await loop.run_in_executor(None, _queue_get_no_block)
                if item is None:
                    now = time.monotonic()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    await asyncio.sleep(0.05)
                    continue

                if item == sentinel:
                    if result_holder:
                        kind, value = result_holder[0]
                        if kind == "RESULT":
                            payload = {"type": "result", **value}
                        else:
                            payload = {"type": "error", "ok": False, "error": str(value)}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    break

                if item[0] == "LOG":
                    last_heartbeat = time.monotonic()
                    yield f"data: {json.dumps({'type': 'log', 'message': item[1]}, ensure_ascii=False)}\n\n"
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

