import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import Response

from rag_ai.api.chat import router as chat_router
from rag_ai.api.documents import router as documents_router
from rag_ai.config import settings

# 전체 애플리케이션 로그 레벨을 환경 변수(settings.log_level)에 맞춰 설정합니다.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("rag_ai.app")

# FastAPI 애플리케이션 인스턴스를 생성합니다.
# 이 객체가 전체 백엔드 서버의 진입점(엔트리 포인트)이 됩니다.
app = FastAPI(
    title="RAG AI Backend",
    description=(
        "학습용 RAG AI 백엔드 서비스입니다. "
        "PDF 문서 인입, 벡터 검색, LLM 호출, Tool/Agent 구조를 점진적으로 추가해 나갑니다."
    ),
    version="0.1.0",
)

# 문서 업로드·인입 API (POST /documents/ingest) 등록
app.include_router(documents_router)

# 채팅(RAG 질의) API (POST /chat/ask) 등록
app.include_router(chat_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """
    모든 HTTP 요청에 대해 시작/종료 로그를 남기는 미들웨어.

    로그 목적:
    - 어떤 endpoint가 호출됐는지 확인
    - 처리 시간(ms) 추적
    - 오래 걸린 요청(SLOW)을 빠르게 탐지
    """
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    # 요청 시작 로그: method, path, query, client ip를 함께 찍어 디버깅에 활용
    logger.debug(
        "[REQ_START] request_id=%s method=%s path=%s query=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        request.url.query,
        request.client.host if request.client else "-",
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "[REQ_ERROR] request_id=%s method=%s path=%s elapsed_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-Id"] = request_id

    # 종료 로그: status code + elapsed time
    logger.debug(
        "[REQ_END] request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    # 느린 요청은 WARNING으로도 남겨 운영 중 병목 탐색을 쉽게 합니다.
    if elapsed_ms >= settings.slow_request_ms:
        logger.warning(
            "[REQ_SLOW] request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f threshold_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            settings.slow_request_ms,
        )

    return response


@app.get("/health")
async def health_check() -> dict:
    """
    서버가 정상적으로 동작하는지 확인하기 위한 헬스 체크 엔드포인트.

    반환 값:
        서버 상태와 간단한 메시지를 담은 JSON 딕셔너리
    """

    # 클라이언트(또는 Kubernetes 등)가 이 경로를 호출해서
    # 백엔드 서버가 살아 있는지 쉽게 확인할 수 있습니다.
    return {
        "status": "ok",  # 서버 상태를 간단한 문자열로 표현
        "message": "RAG AI backend is running",  # 사람이 읽기 쉬운 설명 메시지
    }


@app.get("/")
async def root() -> dict:
    """
    기본 루트 엔드포인트.

    브라우저에서 백엔드 주소를 바로 열었을 때,
    이 프로젝트가 무엇을 하는 백엔드인지 간단히 소개하기 위한 용도입니다.
    """

    # 여기서는 아직 RAG 기능을 구현하지 않았기 때문에
    # 단순한 소개 메시지만 반환합니다.
    return {
        "service": "rag_ai_backend",
        "description": "RAG AI 학습용 백엔드 서버입니다.",
        "docs_url_hint": "상단 /docs 또는 /redoc 경로에서 자동 문서를 확인할 수 있습니다.",
    }

