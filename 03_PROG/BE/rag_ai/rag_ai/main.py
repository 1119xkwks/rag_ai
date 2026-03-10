from fastapi import FastAPI


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

