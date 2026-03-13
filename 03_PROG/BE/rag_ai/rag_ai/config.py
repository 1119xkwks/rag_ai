# config.py
# 환경 변수에서 읽어오는 설정값을 한곳에서 관리합니다.
# .env 파일 또는 시스템 환경 변수로 오버라이드할 수 있습니다.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 전역 설정. 환경 변수와 .env 파일을 자동으로 읽습니다."""

    # ----- Qdrant (Vector DB) -----
    # 로컬: localhost, K8s 클러스터 내부: qdrant 서비스명
    qdrant_host: str = "localhost"
    # 로컬에서 NodePort로 접속 시 30633, 클러스터 내부에서는 6333
    qdrant_port: int = 6333
    # 벡터 컬렉션 이름 (RAG용 문서들이 저장되는 공간)
    qdrant_collection: str = "rag_docs"

    # ----- OpenAI (Embedding / LLM) -----
    # API 키는 반드시 환경 변수 또는 .env에 설정. 기본값 없음.
    openai_api_key: str = ""
    # 임베딩 모델명. 차원 수는 모델에 따라 다름 (예: text-embedding-3-small → 1536)
    openai_embedding_model: str = "text-embedding-3-small"

    # ----- Gemini (Embedding / LLM) -----
    # Google AI Studio에서 발급받은 API 키를 사용합니다.
    gemini_api_key: str = ""
    # Gemini 임베딩 모델 (요청하신 기본값)
    gemini_embedding_model: str = "gemini-embedding-001"
    # Gemini 채팅 모델 (무료 티어/가용성은 계정 상태에 따라 달라질 수 있음)
    gemini_chat_model: str = "gemini-2.0-flash"

    # ----- LLM Provider 선택 -----
    # RAG 답변을 생성할 때 어떤 LLM 백엔드를 쓸지 선택합니다.
    # - "openai": OpenAI Chat API 사용
    # - "vllm"  : 회사 내부 vLLM(OpenAI 호환) 서버 사용
    # - "gemini": Gemini API 사용
    llm_provider: str = "openai"

    # OpenAI Chat 모델명 (llm_provider=openai 일 때 사용)
    openai_chat_model: str = "gpt-4o-mini"

    # ----- Embedding Provider 선택 -----
    # 질문/문서 임베딩 생성에 사용할 백엔드 기본값
    # - "openai": OpenAI Embeddings API
    # - "vllm"  : 회사 내부 vLLM(OpenAI 호환) 서버
    # - "gemini": Gemini Embeddings API
    embedding_provider: str = "openai"

    # vLLM(OpenAI 호환) 서버 설정 (llm_provider=vllm 일 때 사용)
    # 예: http://192.168.1.111:8000/v1
    vllm_api_url: str = "http://192.168.1.111:8000/v1"
    # vLLM은 보통 API 키가 필요 없지만, OpenAI 클라이언트 형식상 값이 필요할 수 있어서 기본 dummy 사용
    vllm_api_key: str = "EMPTY"
    # vLLM 서버에 전달할 model 이름 (예: qwen25-14b, vllm 등)
    vllm_model_name: str = "vllm"
    # vLLM 서버에서 임베딩 생성에 사용할 모델 이름
    # (서버에서 embeddings를 지원하는 모델명으로 지정)
    vllm_embedding_model: str = "vllm"

    # ----- API Timeout 설정(초) -----
    # 내부망 서버가 느릴 수 있어 기본값을 비교적 넉넉하게 둡니다.
    openai_timeout_sec: float = 60.0
    vllm_timeout_sec: float = 120.0
    gemini_timeout_sec: float = 120.0

    # ----- Logging 설정 -----
    # DEBUG / INFO / WARNING / ERROR 중 하나를 사용합니다.
    log_level: str = "INFO"
    # 이 시간(ms)보다 오래 걸린 요청은 별도로 WARNING 로그를 남깁니다.
    slow_request_ms: int = 3000

    # ----- Ingestion LLM 정제 기본값 -----
    # /documents/ingest에서 cleanup_provider를 비웠을 때 사용할 기본 provider
    # (비어 있으면 llm_provider를 그대로 사용)
    cleanup_provider: str = ""

    # ----- Ingestion 기본값 -----
    # 청크 하나당 목표 글자 수 (이 단위로 잘라서 벡터화함)
    chunk_size: int = 2000
    # 청크 간 겹치는 글자 수 (문맥 연속성 유지용)
    chunk_overlap: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 앱 전체에서 사용할 설정 인스턴스. 다른 모듈에서 from rag_ai.config import settings 로 사용.
settings = Settings()
