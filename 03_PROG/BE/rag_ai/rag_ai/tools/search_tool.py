"""
search_tool.py
학습용 DuckDuckGo 검색 도구 함수.
"""

from __future__ import annotations

import re
from typing import Any

import httpx


def _candidate_queries(query: str) -> list[str]:
    """
    자연어 질문형 쿼리를 DDG 친화적인 키워드형으로 몇 가지 변환합니다.
    """
    q = (query or "").strip()
    if not q:
        return []

    def clean(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    candidates: list[str] = []
    candidates.append(clean(q))

    # 문장부호 제거
    no_punct = re.sub(r"[.!?…]+$", "", q).strip()
    candidates.append(clean(no_punct))

    # 한국어 질문 종결 표현 제거
    trimmed = re.sub(
        r"\s*(알려줘|알려주세요|찾아줘|찾아주세요|설명해줘|설명해주세요|약력을 알려줘|약력을 알려주세요)\s*[.!?…]*\s*$",
        "",
        no_punct,
    ).strip()
    candidates.append(clean(trimmed))

    # 주제어만 남기는 약식 변환
    keyword_like = re.sub(r"\s*(에 대해|에대해)\s*", " ", trimmed).strip()
    candidates.append(clean(keyword_like))

    # 중복 제거(순서 유지)
    unique: list[str] = []
    seen = set()
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _extract_ddg_items(data: dict[str, Any], query: str, max_items: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    # 1) Instant Answer
    abstract_text = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    if abstract_text:
        results.append(
            {
                "title": (data.get("Heading") or query).strip(),
                "snippet": abstract_text,
                "url": abstract_url,
                "source": "Abstract",
            }
        )

    # 2) Answer / Definition
    answer_text = (data.get("Answer") or "").strip()
    answer_url = (data.get("AnswerType") or "").strip()
    if answer_text:
        results.append(
            {
                "title": (data.get("Heading") or query).strip(),
                "snippet": answer_text,
                "url": answer_url,
                "source": "Answer",
            }
        )

    definition = (data.get("Definition") or "").strip()
    definition_url = (data.get("DefinitionURL") or "").strip()
    if definition:
        results.append(
            {
                "title": (data.get("Heading") or query).strip(),
                "snippet": definition,
                "url": definition_url,
                "source": "Definition",
            }
        )

    # 3) Related topics
    def append_topic(topic: dict[str, Any]) -> None:
        text = (topic.get("Text") or "").strip()
        first_url = (topic.get("FirstURL") or "").strip()
        if text:
            results.append(
                {
                    "title": text.split(" - ")[0].strip(),
                    "snippet": text,
                    "url": first_url,
                    "source": "RelatedTopics",
                }
            )

    for topic in data.get("RelatedTopics", []):
        if "Topics" in topic and isinstance(topic["Topics"], list):
            for nested in topic["Topics"]:
                if len(results) >= max_items:
                    break
                if isinstance(nested, dict):
                    append_topic(nested)
        elif isinstance(topic, dict):
            append_topic(topic)
        if len(results) >= max_items:
            break

    # URL 기준 중복 제거
    uniq: list[dict[str, Any]] = []
    seen_key = set()
    for item in results:
        key = (item.get("url") or item.get("snippet") or "").strip()
        if not key or key in seen_key:
            continue
        seen_key.add(key)
        uniq.append(item)
        if len(uniq) >= max_items:
            break
    return uniq


def search_duckduckgo(*, query: str, max_items: int = 5) -> dict[str, Any]:
    """
    DuckDuckGo Instant Answer API를 사용해 검색 결과를 가져옵니다.

    주의: Instant Answer API 특성상 일반 웹 검색 결과가 적을 수 있으며,
    요약/관련 토픽 위주로 결과가 반환됩니다.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("query가 비어 있습니다.")
    if max_items <= 0:
        raise ValueError("max_items는 1 이상이어야 합니다.")

    url = "https://api.duckduckgo.com/"
    tried_queries = _candidate_queries(q)
    results: list[dict[str, Any]] = []
    used_query = q

    with httpx.Client(timeout=20.0) as client:
        for candidate in tried_queries:
            params = {
                "q": candidate,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "0",
            }
            res = client.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            items = _extract_ddg_items(data, candidate, max_items=max_items)
            if items:
                used_query = candidate
                results = items
                break

    return {
        "query": q,
        "used_query": used_query,
        "tried_queries": tried_queries,
        "count": min(len(results), max_items),
        "items": results[:max_items],
    }
