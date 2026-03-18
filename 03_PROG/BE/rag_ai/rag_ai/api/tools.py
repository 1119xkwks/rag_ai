# tools.py
# 학습용 Tool 레지스트리 조회/실행 API.

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from rag_ai.tools import get_tool_spec, list_tool_specs, run_tool

router = APIRouter(prefix="/tools", tags=["tools"])
logger = logging.getLogger("rag_ai.api.tools")


class ToolRunRequest(BaseModel):
    tool_name: str = Field(..., description="실행할 tool 이름")
    args: dict[str, Any] = Field(default_factory=dict, description="tool 입력 인자")


@router.get("")
async def list_tools() -> dict[str, Any]:
    """
    설치된 도구 목록/스키마 반환.
    """
    tools = list_tool_specs()
    return {"ok": True, "count": len(tools), "tools": tools}


@router.get("/{tool_name:path}")
async def get_tool(tool_name: str) -> dict[str, Any]:
    """
    단일 도구 스펙 조회.
    """
    try:
        spec = get_tool_spec(tool_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "tool": spec}


@router.post("/run")
async def run_tool_api(req: ToolRunRequest) -> dict[str, Any]:
    """
    도구 실행.
    """
    logger.info("[TOOL_RUN] name=%s args=%s", req.tool_name, req.args)
    try:
        result = run_tool(req.tool_name, req.args)
    except Exception as e:
        # 학습용으로 도구 입력 오류/실행 오류를 메시지로 그대로 반환
        logger.error("[TOOL_RUN_ERROR] name=%s detail=%s", req.tool_name, e)
        raise HTTPException(status_code=400, detail=f"tool 실행 실패: {e!s}")
    logger.info("[TOOL_RUN_DONE] name=%s", req.tool_name)
    return {"ok": True, "tool_name": req.tool_name, "result": result}
