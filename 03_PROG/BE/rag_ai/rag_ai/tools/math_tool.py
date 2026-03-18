"""
math_tool.py
학습용 수학 도구 함수 모음.
"""

from __future__ import annotations

from typing import Any


def calculate_compound_interest(
    *,
    principal: float,
    annual_rate_percent: float,
    years: float,
    compounds_per_year: int = 1,
    contribution_per_period: float = 0.0,
) -> dict[str, Any]:
    """
    복리 계산.

    Args:
        principal: 초기 원금
        annual_rate_percent: 연 이율(%) 예: 5.0
        years: 투자 기간(년)
        compounds_per_year: 1년에 복리 계산 횟수
        contribution_per_period: 각 복리 주기마다 추가 납입금

    Returns:
        계산 결과 딕셔너리
    """
    if principal < 0:
        raise ValueError("principal은 0 이상이어야 합니다.")
    if years < 0:
        raise ValueError("years는 0 이상이어야 합니다.")
    if compounds_per_year <= 0:
        raise ValueError("compounds_per_year는 1 이상이어야 합니다.")

    rate = annual_rate_percent / 100.0
    periods = int(round(years * compounds_per_year))
    period_rate = rate / compounds_per_year

    amount = float(principal)
    for _ in range(periods):
        amount = amount * (1.0 + period_rate) + contribution_per_period

    contributed = principal + (contribution_per_period * periods)
    interest_earned = amount - contributed

    return {
        "principal": principal,
        "annual_rate_percent": annual_rate_percent,
        "years": years,
        "compounds_per_year": compounds_per_year,
        "contribution_per_period": contribution_per_period,
        "periods": periods,
        "final_amount": amount,
        "total_contributed": contributed,
        "interest_earned": interest_earned,
    }
