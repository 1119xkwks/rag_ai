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
