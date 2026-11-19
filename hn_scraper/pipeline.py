"""End-to-end extraction pipeline."""

from __future__ import annotations

import re
from typing import Callable

from .api import fetch_top_level_comments, parse_item_id
from .extractors import parse_candidate_comment


ProgressCallback = Callable[[float, str], None]

# Preferred geographic ordering for Excel / preview rows
REGION_SORT_ORDER = {
    "US": 0,
    "Canada": 1,
    "LATAM": 2,
    "Europe": 3,
    "Asia": 4,
    "Africa": 5,
    "Oceania": 6,
    "Other / Unknown": 7,
    "Unknown": 8,
}

MIN_YEARS_EXPERIENCE = 3


def _region_from_location(location: str) -> str:
    text = (location or "").strip()
    if " / " in text:
        return text.rsplit(" / ", 1)[-1].strip()
    return text or "Unknown"


def _is_india_candidate(record: dict) -> bool:
    location = (record.get("Country / Geographic Region") or "").lower()
    raw = (record.get("_location_raw") or "").lower()
    if location.startswith("india /") or location == "india":
        return True
    if re_search_india(raw):
        return True
    return False


def re_search_india(text: str) -> bool:
    """True when the Location field clearly indicates India."""
    return bool(
        re.search(
            r"(?i)\b(?:india|bangalore|bengaluru|hyderabad|mumbai|"
            r"chennai|pune|delhi|new delhi|noida|gurgaon|gurugram|kolkata)\b",
            text or "",
        )
    )


def _years_value(record: dict) -> int | None:
    raw = record.get("_years_experience")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def should_include_candidate(record: dict) -> bool:
    """Apply export filters: exclude India; drop <3 years when known."""
    if _is_india_candidate(record):
        return False
    years = _years_value(record)
    if years is not None and years < MIN_YEARS_EXPERIENCE:
        return False
    return True


def sort_records_by_region(records: list[dict]) -> list[dict]:
    """Sort candidates: US → Canada → LATAM → Europe → Asia → others."""

    def sort_key(record: dict) -> tuple:
        location = record.get("Country / Geographic Region") or ""
        region = _region_from_location(location)
        region_rank = REGION_SORT_ORDER.get(region, 50)
        country = location.split(" / ", 1)[0].strip().lower() if location else ""
        name = (record.get("Full Name") or "").strip()
        # Blank names last within the same country/region
        name_rank = 1 if not name else 0
        return (region_rank, country, name_rank, name.lower())

    return sorted(records, key=sort_key)


def extract_developers_from_url(
    url_or_id: str,
    delay: float = 0.12,
    progress_callback: ProgressCallback | None = None,
    prefer_algolia: bool = False,
) -> list[dict]:
    """
    Fetch a HN hiring thread and return deduplicated candidate records.

    Each record contains the five Excel columns plus internal metadata.
    Filters out India-based candidates and anyone with clearly stated
    experience under 3 years. Sorted US → Canada → LATAM → Europe → Asia.
    """
    story_id = parse_item_id(url_or_id)

    def _fetch_progress(current: int, total: int, message: str) -> None:
        if progress_callback and total:
            progress_callback(current / total * 0.85, message)

    if progress_callback:
        progress_callback(0.02, f"Loading thread {story_id}…")

    comments = fetch_top_level_comments(
        story_id,
        delay=delay,
        progress_callback=_fetch_progress,
        prefer_algolia=prefer_algolia,
    )

    if progress_callback:
        progress_callback(0.88, f"Parsing {len(comments)} comments…")

    records: list[dict] = []
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    skipped_india = 0
    skipped_junior = 0

    for comment in comments:
        parsed = parse_candidate_comment(comment)
        if not parsed:
            continue

        if not should_include_candidate(parsed):
            if _is_india_candidate(parsed):
                skipped_india += 1
            else:
                skipped_junior += 1
            continue

        hn_id = parsed.get("_hn_id") or ""
        if hn_id and hn_id in seen_ids:
            continue

        # Deduplicate near-identical posts (same email or same profile+location)
        email = (parsed.get("Email") or "").lower()
        links = (parsed.get("Profile / Resume Link") or "").lower()
        location = parsed.get("Country / Geographic Region") or ""
        fingerprint = email or f"{links}|{location}|{parsed.get('_hn_by', '')}"
        if fingerprint and fingerprint in seen_fingerprints:
            continue

        if hn_id:
            seen_ids.add(hn_id)
        if fingerprint:
            seen_fingerprints.add(fingerprint)

        records.append(parsed)

    records = sort_records_by_region(records)

    if progress_callback:
        progress_callback(
            1.0,
            f"Done — {len(records)} candidates "
            f"(excluded India: {skipped_india}, <{MIN_YEARS_EXPERIENCE} yrs: {skipped_junior})",
        )

    return records


def public_rows(records: list[dict]) -> list[dict]:
    """Strip internal fields for display / export."""
    keys = [
        "Full Name",
        "Email",
        "Country / Geographic Region",
        "Specialization",
        "Profile / Resume Link",
    ]
    return [{k: r.get(k, "") for k in keys} for r in records]
