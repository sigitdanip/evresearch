"""
tools/web_search.py — Serper.dev wrapper (free tier, 2500 req/month)
"""
from __future__ import annotations

import json
import os
import time

import requests
from crewai.tools import tool


SERPER_URL = "https://google.serper.dev/search"
_LAST_CALL: float = 0.0
_MIN_INTERVAL: float = 1.5  # seconds between calls


def _call_serper(query: str, num: int = 5) -> list[dict]:
    global _LAST_CALL
    elapsed = time.time() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return [{"error": "SERPER_API_KEY not set in environment"}]
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": num}
    for attempt in range(3):
        try:
            resp = requests.post(SERPER_URL, headers=headers, json=payload, timeout=15)
            _LAST_CALL = time.time()
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("organic", [])[:num]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    })
                return results
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return [{"error": f"Serper failed after 3 attempts for query: {query}"}]


@tool("WebSearch")
def web_search(query: str) -> str:
    """
    Search the web using Serper.dev.
    Args: query (str) — search query string.
    Returns: JSON string with list of {title, url, snippet}.
    Use for finding vehicle specifications, standards documents, and supplier data.
    """
    results = _call_serper(query, num=5)
    return json.dumps(results, ensure_ascii=False)
