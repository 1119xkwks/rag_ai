"""
registry.py
학습용 Tool 레지스트리/스키마/실행기.

목적:
- 설치된 도구 목록과 입력 스키마를 한 곳에서 관리
- 이름으로 도구 실행
- 기본적인 입력 검증(필수값/타입)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Callable

from rag_ai.tools.math_tool import calculate_compound_interest
from rag_ai.tools.search_tool import search_duckduckgo
from rag_ai.tools.time_tool import get_current_time


ToolFunc = Callable[..., dict[str, Any]]
ToolLogCallback = Callable[[str], None]
logger = logging.getLogger("rag_ai.tools.registry")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    func: ToolFunc


_TOOL_SPECS: dict[str, ToolSpec] = {
    "maths.compound_interest": ToolSpec(
        name="maths.compound_interest",
        description="복리 계산 도구",
        input_schema={
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "초기 원금"},
                "annual_rate_percent": {"type": "number", "description": "연 이율(%)"},
                "years": {"type": "number", "description": "투자 기간(년)"},
                "compounds_per_year": {"type": "integer", "description": "연 복리 횟수", "default": 1},
                "contribution_per_period": {
                    "type": "number",
                    "description": "복리 주기마다 추가 납입금",
                    "default": 0.0,
                },
            },
            "required": ["principal", "annual_rate_percent", "years"],
        },
        func=calculate_compound_interest,
    ),
    "time.current": ToolSpec(
        name="time.current",
        description="현재 시간 조회 도구",
        input_schema={
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "IANA timezone", "default": "Asia/Seoul"},
            },
            "required": [],
        },
        func=get_current_time,
    ),
    "search.duckduckgo": ToolSpec(
        name="search.duckduckgo",
        description="DuckDuckGo 검색 도구",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어"},
                "max_items": {"type": "integer", "description": "최대 결과 개수", "default": 5},
            },
            "required": ["query"],
        },
        func=search_duckduckgo,
    ),
}


def list_tool_specs() -> list[dict[str, Any]]:
    """
    LLM/클라이언트에 노출 가능한 도구 스펙 목록 반환.
    """
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in _TOOL_SPECS.values()
    ]


def get_tool_spec(name: str) -> dict[str, Any]:
    spec = _TOOL_SPECS.get(name)
    if spec is None:
        raise ValueError(f"알 수 없는 tool입니다: {name}")
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
    }


def _validate_tool_args(spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
    schema = spec.input_schema
    props: dict[str, dict[str, Any]] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])

    for key in required:
        if key not in args:
            raise ValueError(f"{spec.name}: 필수 인자가 없습니다: {key}")

    validated: dict[str, Any] = {}
    for key, value in args.items():
        if key not in props:
            # MVP 단계에서는 추가 필드는 무시하지 않고 에러로 처리
            raise ValueError(f"{spec.name}: 정의되지 않은 인자입니다: {key}")

        expected_type = props[key].get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ValueError(f"{spec.name}: {key}는 string이어야 합니다.")
        if expected_type == "integer" and not isinstance(value, int):
            raise ValueError(f"{spec.name}: {key}는 integer여야 합니다.")
        if expected_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"{spec.name}: {key}는 number여야 합니다.")

        validated[key] = value

    # 기본값 채우기
    for key, prop in props.items():
        if key not in validated and "default" in prop:
            validated[key] = prop["default"]

    return validated


def run_tool(
    name: str,
    args: dict[str, Any] | None = None,
    log_callback: ToolLogCallback | None = None,
) -> dict[str, Any]:
    """
    이름으로 도구 실행.
    """
    spec = _TOOL_SPECS.get(name)
    if spec is None:
        raise ValueError(f"알 수 없는 tool입니다: {name}")

    normalized_args = args or {}
    validated_args = _validate_tool_args(spec, normalized_args)
    start = time.perf_counter()

    if log_callback is not None:
        log_callback(
            f"[tool.start] name={name} args={json.dumps(validated_args, ensure_ascii=False)}"
        )
    logger.info(
        "[TOOL_START] name=%s args=%s",
        name,
        json.dumps(validated_args, ensure_ascii=False),
    )

    try:
        result = spec.func(**validated_args)
        elapsed_ms = (time.perf_counter() - start) * 1000
        result_preview = json.dumps(result, ensure_ascii=False)
        if len(result_preview) > 300:
            result_preview = result_preview[:300] + "...(truncated)"
        logger.info(
            "[TOOL_DONE] name=%s elapsed_ms=%.1f result_preview=%s",
            name,
            elapsed_ms,
            result_preview,
        )
        if log_callback is not None:
            log_callback(
                f"[tool.done] name={name} elapsed_ms={elapsed_ms:.1f} result_preview={result_preview}"
            )
        return result
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "[TOOL_ERROR] name=%s elapsed_ms=%.1f detail=%s",
            name,
            elapsed_ms,
            e,
        )
        if log_callback is not None:
            log_callback(
                f"[tool.error] name={name} elapsed_ms={elapsed_ms:.1f} detail={e!s}"
            )
        raise
