"""
time_tool.py
학습용 현재 시간 조회 도구 함수.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def get_current_time(*, timezone: str = "Asia/Seoul") -> dict[str, Any]:
    """
    현재 시간을 반환합니다.

    Args:
        timezone: IANA timezone string (예: Asia/Seoul, UTC)
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception as e:
        raise ValueError(f"유효하지 않은 timezone입니다: {timezone}") from e

    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "unix": int(now.timestamp()),
    }
