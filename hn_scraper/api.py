"""Hacker News API client (official Firebase API + free Algolia fallback)."""

from __future__ import annotations

import re
import time
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

import requests

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{item_id}"
DEFAULT_TIMEOUT = 25
DEFAULT_DELAY = 0.12  # polite pacing between Firebase item fetches
MAX_RETRIES = 3


class HNAPIError(Exception):
    """Raised when the Hacker News API cannot fulfill a request."""


def parse_item_id(url_or_id: str) -> int:
    """Extract a numeric item id from a HN URL or raw id string."""
    text = (url_or_id or "").strip()
    if not text:
        raise ValueError("Please provide a Hacker News thread URL or item id.")

    if text.isdigit():
        return int(text)

    parsed = urlparse(text)
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        candidate = query["id"][0]
        if candidate.isdigit():
            return int(candidate)

    match = re.search(r"(?:item\?id=|/item/)(\d+)", text)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d{5,})\b", text)
    if match:
        return int(match.group(1))

    raise ValueError(
        "Could not find a Hacker News item id. "
        "Expected a URL like https://news.ycombinator.com/item?id=50338726"
    )


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "HN-Developer-Scraper/1.0 (+local; educational use)",
            "Accept": "application/json",
        }
    )
    return session


def fetch_item(
    item_id: int,
    session: requests.Session | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any] | None:
    """Fetch a single HN item from the official Firebase API with retries."""
    own_session = session is None
    session = session or _session()
    url = f"{HN_API_BASE}/item/{item_id}.json"
    last_error: Exception | None = None
    response = None

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                time.sleep(min(2 ** attempt * 0.35, 5.0))
            except requests.HTTPError as exc:
                last_error = exc
                status = response.status_code if response is not None else "?"
                if response is not None and response.status_code >= 500:
                    time.sleep(min(2 ** attempt * 0.35, 5.0))
                    continue
                raise HNAPIError(f"HTTP {status} for item {item_id}") from exc
        raise HNAPIError(
            f"Failed to fetch item {item_id} after {MAX_RETRIES} attempts: {last_error}"
        )
    finally:
        if own_session:
            session.close()


def _algolia_child_to_comment(child: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an Algolia child node into Firebase-like comment dict."""
    if not child:
        return None
    if child.get("type") not in (None, "comment"):
        # Algolia may omit type for comments; skip non-comment if present
        if child.get("type") and child.get("type") != "comment":
            return None

    text = child.get("text")
    deleted = bool(child.get("deleted")) or text is None
    return {
        "id": child.get("id"),
        "by": child.get("author") or child.get("by"),
        "text": text,
        "type": "comment",
        "parent": child.get("parent_id") or child.get("parent"),
        "deleted": deleted,
        "dead": bool(child.get("dead")),
        "time": child.get("created_at_i") or child.get("time"),
    }


def fetch_top_level_comments_algolia(
    story_id: int,
    session: requests.Session | None = None,
    timeout: float = 90,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all top-level comments via the free Algolia HN API (one request).

    Used as a fallback when the Firebase API is unreachable. Data is still
    sourced from Hacker News; no paid enrichment is used.
    """
    own_session = session is None
    session = session or _session()
    url = ALGOLIA_ITEM_URL.format(item_id=story_id)
    try:
        if progress_callback:
            progress_callback(0, 1, "Fetching thread via Algolia HN API…")
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        children = data.get("children") or []
        total = len(children)
        comments: list[dict[str, Any]] = []
        for index, child in enumerate(children, start=1):
            if progress_callback and total:
                progress_callback(index, total, f"Parsing comment {index}/{total}")
            item = _algolia_child_to_comment(child)
            if not item:
                continue
            if item.get("deleted") or item.get("dead"):
                continue
            if not item.get("text") or not str(item["text"]).strip():
                continue
            comments.append(item)
        return comments
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        raise HNAPIError(f"Algolia fallback failed for story {story_id}: {exc}") from exc
    finally:
        if own_session:
            session.close()


def fetch_top_level_comments_firebase(
    story_id: int,
    delay: float = DEFAULT_DELAY,
    progress_callback: Callable[[int, int, str], None] | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Fetch all top-level comments via the official Firebase HN API."""
    own_session = session is None
    session = session or _session()
    try:
        story = fetch_item(story_id, session=session)
        if not story:
            raise HNAPIError(f"Story {story_id} not found.")

        kid_ids = story.get("kids") or []
        total = len(kid_ids)
        comments: list[dict[str, Any]] = []

        for index, kid_id in enumerate(kid_ids, start=1):
            if progress_callback:
                progress_callback(index, total, f"Fetching comment {index}/{total}")

            item = fetch_item(kid_id, session=session)
            if delay > 0:
                time.sleep(delay)

            if not item:
                continue
            if item.get("deleted") or item.get("dead"):
                continue
            if item.get("type") != "comment":
                continue
            text = item.get("text")
            if not text or not str(text).strip():
                continue

            comments.append(item)

        return comments
    finally:
        if own_session:
            session.close()


def fetch_top_level_comments(
    story_id: int,
    delay: float = DEFAULT_DELAY,
    progress_callback: Callable[[int, int, str], None] | None = None,
    prefer_algolia: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetch all top-level comments under a story.

    Tries the official Firebase API first (unless prefer_algolia=True).
    Falls back to the free Algolia HN API when Firebase is unreachable.
    Skips deleted/dead comments and comments without text.
    """
    session = _session()
    try:
        if prefer_algolia:
            return fetch_top_level_comments_algolia(
                story_id, session=session, progress_callback=progress_callback
            )

        try:
            # Probe story quickly; if it fails, use Algolia for the whole thread.
            story = fetch_item(story_id, session=session, timeout=20)
            if story and story.get("kids"):
                return fetch_top_level_comments_firebase(
                    story_id,
                    delay=delay,
                    progress_callback=progress_callback,
                    session=session,
                )
            # Empty kids or missing story — still try Algolia
            raise HNAPIError("Firebase story missing or has no kids")
        except HNAPIError:
            if progress_callback:
                progress_callback(
                    0,
                    1,
                    "Official HN API unavailable — falling back to Algolia mirror…",
                )
            return fetch_top_level_comments_algolia(
                story_id, session=session, progress_callback=progress_callback
            )
    finally:
        session.close()
