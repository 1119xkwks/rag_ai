# rag_service.py
# 질문이 들어왔을 때 RAG 흐름(검색 → 컨텍스트 구성 → LLM 답변)을 수행하는 서비스입니다.
#
# 이 파일의 목적:
# - API 레이어(`/chat/ask`)에서는 HTTP 입/출력만 다루고,
# - 실제 RAG 로직은 여기 서비스 레이어에 모아두기 위함입니다.

from typing import Any, List

from openai import OpenAI

from rag_ai.config import settings
from rag_ai.services.embedding_service import embed_single
from rag_ai.services.vector_service import get_qdrant_client, search_similar


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
) -> dict[str, Any]:
    """
    질문을 받아 RAG 방식으로 답변을 생성합니다.

    인자:
        question: 사용자 질문(자연어)
        top_k: Qdrant에서 가져올 관련 청크 개수
        source: (선택) 특정 문서(source) 범위에서만 검색하고 싶을 때 사용

    반환:
        answer: 최종 답변
        contexts: 사용된 검색 결과(원문/score/source 등)
    """
    if not question or not question.strip():
        return {"ok": False, "error": "question이 비어 있습니다."}

    if not settings.openai_api_key:
        # API 키가 없으면 LLM/임베딩 호출이 불가능하므로, 친절한 에러를 반환합니다.
        return {
            "ok": False,
            "error": "OPENAI_API_KEY가 설정되어 있지 않습니다. (.env 또는 환경 변수에 설정 필요)",
        }

    # 1) 질문을 임베딩해서 벡터로 변환합니다.
    query_vector = embed_single(question)
    if not query_vector:
        return {"ok": False, "error": "질문 임베딩 생성에 실패했습니다."}

    # 2) Qdrant에서 유사한 청크를 검색합니다.
    qdrant = get_qdrant_client()
    hits = search_similar(
        client=qdrant,
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        top_k=top_k,
        source=source,
    )

    # 3) 검색 결과에서 LLM에 넣을 컨텍스트를 구성합니다.
    context = build_context_from_hits(hits)

    # 4) LLM에게 “문서 컨텍스트 기반으로 답변”하도록 요청합니다.
    #    - 아직 스트리밍/툴 호출은 하지 않고, 가장 단순한 형태로 구현합니다.
    client = OpenAI(api_key=settings.openai_api_key or None)

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

    # 모델은 우선 범용으로 gpt-4o-mini를 사용 (비용/속도 균형)
    # 필요하면 settings로 빼서 바꿀 수 있습니다.
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # 너무 창의적이지 않게(근거 기반 답변 유도)
    )

    answer = (completion.choices[0].message.content or "").strip()

    return {
        "ok": True,
        "answer": answer,
        "contexts": hits,  # 프론트에서 “근거”로 보여줄 수 있도록 그대로 반환
        "used_source_filter": source or "",
        "collection": settings.qdrant_collection,
    }

