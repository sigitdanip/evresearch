"""
tools/scraper.py — BeautifulSoup HTML scraper
"""
from __future__ import annotations

import json

import requests
from bs4 import BeautifulSoup
from crewai.tools import tool

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def _scrape_text(url: str, max_chars: int = 8000) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
    except Exception as exc:
        return f"SCRAPE_ERROR: {exc}"


@tool("WebScraper")
def scrape_page(url: str) -> str:
    """
    Scrape and return the plain-text content of a web page.
    Args: url (str) — fully qualified URL to scrape.
    Returns: Plain text content (up to 8000 characters).
    Use to extract vehicle specification data from manufacturer pages.
    """
    return _scrape_text(url)
