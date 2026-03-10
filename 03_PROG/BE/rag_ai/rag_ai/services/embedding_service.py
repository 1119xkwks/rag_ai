# embedding_service.py
# 텍스트(또는 청크)를 벡터(숫자 배열)로 변환하는 서비스입니다.
# RAG에서는 이 벡터로 유사도 검색을 하므로, 같은 모델로 질문과 문서를 모두 임베딩해야 합니다.

from typing import List

from openai import OpenAI

from rag_ai.config import settings


def get_embedding_client() -> OpenAI:
    """설정에 있는 API 키로 OpenAI 클라이언트를 만들어 반환합니다."""
    return OpenAI(api_key=settings.openai_api_key or None)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    여러 개의 텍스트를 한 번에 임베딩 모델에 넣어 벡터 리스트로 반환합니다.

    인자:
        texts: 임베딩할 문자열 리스트 (예: chunker로 잘라낸 청크들)

    반환:
        각 텍스트에 대응하는 벡터(실수 리스트)의 리스트.
        Qdrant에 저장할 때 이 벡터를 그대로 사용합니다.

    참고:
        OpenAI API는 한 번에 여러 텍스트를 받을 수 있어서, 배치로 호출하면 비용/속도에 유리합니다.
    """
    if not texts:
        return []

    client = get_embedding_client()
    model = settings.openai_embedding_model

    # OpenAI Embeddings API 호출. 입력이 리스트이면 응답도 각 텍스트당 벡터 하나씩 반환됨
    response = client.embeddings.create(input=texts, model=model)

    # 응답에서 embedding 벡터만 순서대로 꺼내서 리스트로 만듦
    vectors: List[List[float]] = [item.embedding for item in response.data]
    return vectors


def embed_single(text: str) -> List[float]:
    """
    텍스트 하나만 임베딩할 때 편의용 함수.
    내부적으로 embed_texts([text])를 호출하고 첫 번째 벡터만 반환합니다.
    """
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
