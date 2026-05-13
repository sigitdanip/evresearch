"""
tools/pdf_reader.py — pdfplumber-based regulation PDF text extractor
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import requests
from crewai.tools import tool

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False


def _extract_pdf_text(source: str, max_chars: int = 10000) -> str:
    """Extract text from a PDF at a local path or URL."""
    if not _HAS_PDFPLUMBER:
        return "ERROR: pdfplumber not installed. Run: uv add pdfplumber"
    try:
        if source.startswith("http://") or source.startswith("https://"):
            resp = requests.get(source, timeout=30)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                return _read_local_pdf(tmp_path, max_chars)
            finally:
                os.unlink(tmp_path)
        else:
            return _read_local_pdf(source, max_chars)
    except Exception as exc:
        return f"PDF_READ_ERROR: {exc}"


def _read_local_pdf(path: str, max_chars: int) -> str:
    with pdfplumber.open(path) as pdf:
        texts = []
        total = 0
        for page in pdf.pages:
            t = page.extract_text() or ""
            texts.append(t)
            total += len(t)
            if total >= max_chars:
                break
    combined = "\n".join(texts)
    return combined[:max_chars]


@tool("PDFReader")
def read_pdf(source: str) -> str:
    """
    Extract text from a PDF document (local path or URL).
    Args: source (str) — local file path or HTTPS URL to a PDF.
    Returns: Extracted plain text (up to 10,000 characters).
    Use for reading SNI standards, Kemenhub regulations, and PM documents.
    Key Indonesian regulation PDFs:
      - PM 98/2017: Standar Pelayanan Minimal Angkutan
      - Permenhub 44/2020: Kendaraan Bermotor Listrik Berbasis Baterai
      - SNI 09-0683: Persyaratan Teknis Karoseri Bus
    """
    return _extract_pdf_text(source)
