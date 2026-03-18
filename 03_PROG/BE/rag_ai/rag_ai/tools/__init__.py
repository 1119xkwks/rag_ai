"""
LLM이 호출할 수 있는 Tool 정의를 모아 두는 패키지.

예:
- base_tool.py   → 공통 인터페이스 / 추상 클래스
- math_tool.py   → 수학 계산용 도구
- time_tool.py   → 현재 시간 조회 도구
- search_tool.py → 외부 검색 (예: DuckDuckGo) 도구
"""

from rag_ai.tools.math_tool import calculate_compound_interest
from rag_ai.tools.registry import get_tool_spec, list_tool_specs, run_tool
from rag_ai.tools.search_tool import search_duckduckgo
from rag_ai.tools.time_tool import get_current_time

__all__ = [
    "calculate_compound_interest",
    "search_duckduckgo",
    "get_current_time",
    "list_tool_specs",
    "get_tool_spec",
    "run_tool",
]

