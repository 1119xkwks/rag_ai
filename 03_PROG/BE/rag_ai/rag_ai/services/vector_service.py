# vector_service.py
# Qdrant 벡터 DB에 접속해서 컬렉션을 만들고, 포인트(벡터+메타데이터)를 넣고 검색하는 서비스입니다.

import uuid
from typing import Any, List

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct

from rag_ai.config import settings

# text-embedding-3-small 기준 차원 수. 다른 모델 사용 시 여기만 바꾸면 됨
EMBEDDING_DIM = 1536


def get_qdrant_client() -> QdrantClient:
    """설정된 호스트/포트로 Qdrant 클라이언트를 생성해 반환합니다."""
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(client: QdrantClient, collection_name: str, dim: int = EMBEDDING_DIM) -> None:
    """
    컬렉션이 없으면 생성하고, 있으면 그대로 둡니다.
    벡터 차원(dim)은 사용하는 임베딩 모델과 동일해야 합니다.

    인자:
        client: Qdrant 클라이언트
        collection_name: 컬렉션 이름 (예: rag_docs)
        dim: 벡터 차원 수 (OpenAI text-embedding-3-small = 1536)
    """
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    if collection_name in names:
        return

    # 거리 지표: 코사인 유사도. RAG에서는 보통 코사인 또는 내적 사용
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )


def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    vectors: List[List[float]],
    texts: List[str],
    metadata_list: List[dict[str, Any]] | None = None,
) -> List[str]:
    """
    청크 벡터와 원문(및 메타데이터)을 Qdrant에 한 번에 넣습니다.
    각 포인트에 고유 ID를 부여해 나중에 검색 결과에서 원문을 찾을 수 있게 합니다.

    인자:
        client: Qdrant 클라이언트
        collection_name: 넣을 컬렉션 이름
        vectors: 임베딩 벡터 리스트 (embedding_service.embed_texts 결과)
        texts: 각 벡터에 대응하는 원문 텍스트 (payload에 저장됨)
        metadata_list: (선택) 각 포인트별 추가 메타데이터. 없으면 texts만 payload에 넣음

    반환:
        생성된 포인트 ID 목록 (UUID 문자열). 디버깅/삭제 시 사용 가능
    """
    if not vectors or len(vectors) != len(texts):
        return []

    points: List[PointStruct] = []
    ids: List[str] = []
    for i, (vec, text) in enumerate(zip(vectors, texts)):
        payload: dict[str, Any] = {"text": text}
        if metadata_list and i < len(metadata_list):
            payload.update(metadata_list[i])
        point_id = str(uuid.uuid4())
        ids.append(point_id)
        points.append(PointStruct(id=point_id, vector=vec, payload=payload))

    client.upsert(collection_name=collection_name, points=points, wait=True)
    return ids


def search_similar(
    client: QdrantClient,
    collection_name: str,
    query_vector: List[float],
    top_k: int = 5,
) -> List[dict[str, Any]]:
    """
    쿼리 벡터와 유사한 상위 top_k개 포인트를 검색합니다.
    RAG에서 사용자 질문을 임베딩한 뒤, 이 함수로 관련 청크를 가져옵니다.

    인자:
        client: Qdrant 클라이언트
        collection_name: 검색할 컬렉션
        query_vector: 질문(또는 검색어)의 임베딩 벡터
        top_k: 가져올 결과 개수

    반환:
        각 결과의 payload와 score를 담은 딕셔너리 리스트 (payload에 text 등이 있음)
    """
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
    )
    return [
        {"id": hit.id, "score": hit.score, "payload": hit.payload or {}}
        for hit in results
    ]
