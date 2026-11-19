"""HTML cleaning and text sanitization helpers."""

from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup


def clean_html(raw: str | None) -> str:
    """Convert HN comment HTML to plain text while preserving line breaks."""
    if not raw:
        return ""

    text = html.unescape(raw)
    # HN often uses bare <p> separators (no closing tags). Treat as line breaks.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)<p\s*/?>", "\n", text)
    text = re.sub(r"(?i)<p\s+[^>]*>", "\n", text)

    soup = BeautifulSoup(text, "lxml")
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        label = a.get_text(" ", strip=True)
        if href and href not in label:
            a.replace_with(f"{label} {href}".strip())
        else:
            a.replace_with(label or href)

    plain = soup.get_text("\n")
    plain = plain.replace("\xa0", " ")
    plain = re.sub(r"[ \t]+", " ", plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def sanitize_excel_cell(value: str | None) -> str:
    """Prevent formula injection when writing user-supplied text to Excel."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
