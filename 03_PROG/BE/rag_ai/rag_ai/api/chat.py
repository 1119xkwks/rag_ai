# chat.py
# 최소 RAG API: 질문을 받으면 Qdrant 검색 + LLM 답변 생성까지 수행합니다.

from fastapi import APIRouter
from pydantic import BaseModel, Field

from rag_ai.services.rag_service import answer_with_rag

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatAskRequest(BaseModel):
    # 사용자가 입력하는 질문 텍스트
    question: str = Field(..., description="사용자 질문")

    # 몇 개의 관련 문서 청크를 가져올지 (기본값 5)
    top_k: int = Field(5, ge=1, le=20, description="검색 결과 상위 몇 개를 사용할지")

    # (선택) 특정 문서(source)로 제한해서 검색하고 싶을 때 사용
    # 예: PDF 인입 시 source를 파일명으로 넣었으니, 질문할 때 같은 값을 주면 그 문서 범위에서만 검색함
    source: str = Field("", description="(선택) source 필터. 비우면 전체에서 검색")


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
    result = answer_with_rag(
        question=req.question,
        top_k=req.top_k,
        source=req.source.strip() or None,
    )
    return result

