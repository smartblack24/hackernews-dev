"""Rule-based field extractors for HN hiring comments."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import pycountry

from .cleaning import normalize_whitespace

# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    "location": ("location", "based in", "based", "loc"),
    "email": ("email", "e-mail", "mail", "contact"),
    "resume": (
        "résumé/cv",
        "resume/cv",
        "résumé",
        "resume",
        "cv",
        "portfolio",
        "website",
        "site",
        "linkedin",
        "github",
        "profile",
    ),
    "technologies": (
        "technologies",
        "tech stack",
        "stack",
        "skills",
        "tech",
        "languages",
    ),
    "name": ("name", "full name", "i am", "i'm"),
}


def _field_pattern(aliases: tuple[str, ...]) -> re.Pattern[str]:
    joined = "|".join(re.escape(a) for a in aliases)
    return re.compile(
        rf"(?im)^\s*(?:[-*•]\s*)?(?:{joined})\s*[:\-–—]\s*(.+)$"
    )


_LOCATION_RE = _field_pattern(FIELD_ALIASES["location"])
_EMAIL_FIELD_RE = _field_pattern(FIELD_ALIASES["email"])
_RESUME_FIELD_RE = _field_pattern(FIELD_ALIASES["resume"])
_TECH_FIELD_RE = _field_pattern(FIELD_ALIASES["technologies"])
_NAME_FIELD_RE = _field_pattern(FIELD_ALIASES["name"])

# Inline "Location: X Remote: Y" style (no newlines)
_INLINE_LOCATION_RE = re.compile(
    r"(?i)\blocation\s*[:\-–—]\s*(.+?)(?=\s(?:remote|willing|technologies|tech|email|résumé|resume|cv)\s*[:\-–—]|$)"
)


def extract_labeled_fields(text: str) -> dict[str, str]:
    """Pull common labeled fields from a hiring comment."""
    fields: dict[str, str] = {}

    for key, pattern in (
        ("location", _LOCATION_RE),
        ("email", _EMAIL_FIELD_RE),
        ("resume", _RESUME_FIELD_RE),
        ("technologies", _TECH_FIELD_RE),
        ("name", _NAME_FIELD_RE),
    ):
        match = pattern.search(text)
        if match:
            fields[key] = match.group(1).strip()

    if "location" not in fields:
        match = _INLINE_LOCATION_RE.search(text)
        if match:
            fields["location"] = match.group(1).strip()

    return fields


# ---------------------------------------------------------------------------
# Full name
# ---------------------------------------------------------------------------

_NAME_STOPWORDS = {
    "remote",
    "yes",
    "no",
    "open",
    "looking",
    "engineer",
    "developer",
    "software",
    "senior",
    "junior",
    "full",
    "stack",
    "frontend",
    "backend",
    "location",
    "email",
    "resume",
    "linkedin",
    "github",
    "portfolio",
    "available",
    "seeking",
    "hiring",
    "contact",
    "technologies",
    "willing",
    "relocate",
    "product",
    "minded",
    "systems",
    "staff",
    "lead",
    "happy",
    "fine",
    "very",
    "interested",
    "not",
    "fit",
    "most",
    "any",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "based",
    "currently",
    "previously",
    "building",
    "working",
    "experienced",
    "professional",
    "contract",
    "freelance",
    "consultant",
    "founder",
    "cofounder",
    "student",
    "graduate",
}

_NAME_LEADING_NOISE = {
    "a",
    "an",
    "the",
    "also",
    "still",
    "just",
    "currently",
    "primarily",
    "mainly",
    "originally",
}

_COMPANY_HINTS = {
    "inc",
    "llc",
    "ltd",
    "corp",
    "gmbh",
    "technologies",
    "solutions",
    "systems",
    "labs",
    "studio",
    "agency",
}

# Require at least first + last for intro statements to avoid "I'm a developer"
_INTRO_NAME_PATTERNS = [
    re.compile(
        r"(?i)\b(?:hi|hello|hey)[,!]?\s+"
        r"(?:i(?:'|’)?m|i am|my name is)\s+"
        r"([A-ZÀ-ÖØ-Þ][\w'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){1,3})\b"
    ),
    re.compile(
        r"(?i)\bmy name is\s+"
        r"([A-ZÀ-ÖØ-Þ][\w'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){1,3})\b"
    ),
    re.compile(
        r"(?i)\b(?:i(?:'|’)?m|i am)\s+"
        r"([A-ZÀ-ÖØ-Þ][\w'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){1,3})\b"
        r"(?:\s*[,.\-]|\s+(?:and|a|an|from|based|looking|seeking|available)\b)"
    ),
    re.compile(
        r"(?i)\b(?:regards|cheers|best|thanks|thank you)[,!]?\s*\n+\s*"
        r"([A-ZÀ-ÖØ-Þ][\w'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){0,2})\s*$"
    ),
    # Multi-word name on its own line
    re.compile(
        r"(?im)^\s*([A-ZÀ-ÖØ-Þ][\w'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){1,2})\s*$"
    ),
    # Single-token signature on the final line (e.g. "Volodymyr")
    re.compile(
        r"(?im)(?:^|\n)\s*([A-ZÀ-ÖØ-Þ][\w'’\-]{2,30})\s*$"
    ),
]

_LINKEDIN_SLUG_RE = re.compile(
    r"(?i)linkedin\.com/in/([a-z0-9\-_%]+)"
)

_CV_FILENAME_RE = re.compile(
    r"(?i)(?:/|^|%2F)([A-Za-z][A-Za-z\-_]{2,60})-(?:cv|resume|curriculumvitae|curriculum)(?:-[A-Za-z]{2})?\.(?:pdf|docx?)\b"
)

_CV_FILENAME_ALT_RE = re.compile(
    r"(?i)(?:/|^|%2F)([A-Z][a-z]+(?:-[A-Z][a-z]+){1,3})(?:-cv|-resume)?\.(?:pdf|docx?)\b"
)

_EMAIL_NAME_RE = re.compile(
    r"(?i)\b([a-z]{2,20})\.([a-z]{2,20})@(?:[a-z0-9\-]+\.)+[a-z]{2,10}\b"
)


def _title_case_name_part(part: str) -> str:
    part = part.strip("-_ ")
    if not part:
        return ""
    if "-" in part:
        return "-".join(_title_case_name_part(p) for p in part.split("-") if p)
    if part.lower() in {"mc", "mac"}:
        return part[:1].upper() + part[1:].lower()
    return part[:1].upper() + part[1:].lower()


def _looks_like_person_name(candidate: str, *, allow_single: bool = False) -> bool:
    name = normalize_whitespace(candidate)
    if not name or len(name) < 2 or len(name) > 60:
        return False
    if "@" in name or "http" in name.lower() or "/" in name:
        return False
    parts = re.split(r"\s+", name)
    if len(parts) > 4:
        return False
    if len(parts) == 1 and not allow_single:
        return False
    lowered = {p.lower().strip(".,") for p in parts}
    if lowered & _NAME_STOPWORDS:
        return False
    if lowered & _COMPANY_HINTS:
        return False
    if lowered & _NAME_LEADING_NOISE:
        return False
    # Reject all-caps tech-y tokens and pure usernames with digits
    if any(re.search(r"\d", p) for p in parts):
        return False
    if any(p.isupper() and len(p) > 3 for p in parts):
        return False
    # Prefer Title Case / capitalized tokens
    if not all(p[:1].isupper() for p in parts if p):
        return False
    # Reject tiny fragments
    if any(len(p) < 2 for p in parts):
        return False
    return True


def _name_from_linkedin_slug(slug: str) -> str:
    """Derive a display name from a voluntarily published LinkedIn profile slug."""
    from urllib.parse import unquote

    slug = unquote(slug or "").strip().strip("/")
    if not slug:
        return ""
    parts = [p for p in re.split(r"-+", slug) if p]
    # Drop LinkedIn trailing id segments (e.g. 6255b9309, 48a474154)
    while parts and re.search(r"\d", parts[-1]):
        parts.pop()
    # Drop leftover 1–2 char crumbs and trailing brand/noise tokens
    noise_tails = {
        "co",
        "com",
        "io",
        "ai",
        "dev",
        "web",
        "app",
        "apps",
        "tech",
        "labs",
        "hq",
        "inc",
        "llc",
        "official",
        "profile",
        "linkedin",
        "company",
        "about",
        "resume",
        "cv",
        "fancyai",
        "redshoeweb",
    }
    while parts and parts[-1].lower() in noise_tails:
        parts.pop()
    parts = [p for p in parts if len(p) > 2 and p.lower() not in noise_tails]
    if len(parts) < 2:
        return ""
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z'’\-]{1,30}", p) for p in parts):
        return ""
    # Avoid slug words that are clearly not name tokens
    blocked = {"profile", "linkedin", "company", "about", "resume", "cv"}
    if any(p.lower() in blocked for p in parts):
        return ""
    # Prefer first + last; keep up to 3 tokens for compound names
    name = " ".join(_title_case_name_part(p) for p in parts[:3])
    return name if _looks_like_person_name(name) else ""


def _name_from_cv_urls(text: str) -> str:
    for pattern in (_CV_FILENAME_RE, _CV_FILENAME_ALT_RE):
        for match in pattern.finditer(text):
            raw = match.group(1).replace("_", "-")
            parts = [p for p in re.split(r"-+", raw) if p and len(p) > 1]
            # Filenames like makeev-daniil-cv → reorder if last looks like given name?
            # Keep filename order as published.
            if len(parts) >= 2 and all(re.fullmatch(r"[A-Za-z][A-Za-z'’\-]{1,30}", p) for p in parts):
                name = " ".join(_title_case_name_part(p) for p in parts[:4])
                if _looks_like_person_name(name):
                    return name
    return ""


def _name_from_email_local(text: str, fields: dict[str, str] | None = None) -> str:
    """Use first.last@email style only — never HN usernames."""
    blobs = []
    if fields and fields.get("email"):
        blobs.append(fields["email"])
    blobs.append(text)
    for blob in blobs:
        match = _EMAIL_NAME_RE.search(blob)
        if not match:
            continue
        first, last = match.group(1), match.group(2)
        if first.lower() in _NAME_STOPWORDS or last.lower() in _NAME_STOPWORDS:
            continue
        if first.lower() in _NAME_LEADING_NOISE:
            continue
        name = f"{_title_case_name_part(first)} {_title_case_name_part(last)}"
        if _looks_like_person_name(name):
            return name
    return ""


def extract_full_name(text: str, fields: dict[str, str] | None = None) -> str:
    """
    Extract a real name from explicit text or voluntarily published profile clues.

    Never invent from HN usernames. Prefer explicit statements, then LinkedIn /
    résumé filenames, then first.last email locals.
    """
    fields = fields or extract_labeled_fields(text)

    if fields.get("name"):
        raw = fields["name"]
        raw = re.split(r"[|/;,\n]", raw)[0].strip()
        # Strip leading "I am" noise if the labeled value included it
        raw = re.sub(r"(?i)^(i(?:'|’)?m|i am|my name is)\s+", "", raw).strip()
        if _looks_like_person_name(raw, allow_single=True):
            return raw

    for pattern in _INTRO_NAME_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1).strip(" .,!-")
            # Drop leading articles mistakenly captured
            parts = candidate.split()
            while parts and parts[0].lower() in _NAME_LEADING_NOISE:
                parts.pop(0)
            candidate = " ".join(parts)
            allow_single = pattern is _INTRO_NAME_PATTERNS[-1]
            if not _looks_like_person_name(candidate, allow_single=allow_single):
                continue
            if " " not in candidate:
                trailing = text[match.start() :].strip()
                if trailing != candidate:
                    continue
            return candidate

    for match in _LINKEDIN_SLUG_RE.finditer(text):
        name = _name_from_linkedin_slug(match.group(1))
        if name:
            return name

    cv_name = _name_from_cv_urls(text)
    if cv_name:
        return cv_name

    email_name = _name_from_email_local(text, fields)
    if email_name:
        return email_name

    return ""


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

# TLD capped so glued prose like "netSelf-taught" is not absorbed into the email.
_STANDARD_EMAIL_RE = re.compile(
    r"(?i)\b([a-z0-9._%+\-]+@(?:[a-z0-9\-]+\.)+[a-z]{2,10})(?![a-z0-9%+\-])"
)

_FALSE_EMAIL_HOSTS = {
    "github.com",
    "gitlab.com",
    "linkedin.com",
    "example.com",
    "domain.com",
    "email.com",
}

_OBFUSCATED_EMAIL_PATTERNS = [
    # john [at] gmail [dot] com / john(at)gmail(dot)com / john at gmail dot com
    re.compile(
        r"(?i)\b([a-z0-9._%+\-]+)\s*(?:\[|\(|\{)?\s*(?:@|at|AT)\s*(?:\]|\)|\})?\s*"
        r"([a-z0-9.\-]+)\s*(?:\[|\(|\{)?\s*(?:\.|dot|DOT)\s*(?:\]|\)|\})?\s*"
        r"([a-z]{2,})\b"
    ),
    # john at-sign domain dot tld
    re.compile(
        r"(?i)\b([a-z0-9._%+\-]+)\s+at-?sign\s+([a-z0-9.\-]+)\s+dot\s+([a-z]{2,})\b"
    ),
    # john＠gmail．com (fullwidth)
    re.compile(
        r"(?i)\b([a-z0-9._%+\-]+)＠([a-z0-9.\-]+)．([a-z]{2,})\b"
    ),
]


def _normalize_email_parts(local: str, domain: str, tld: str) -> str:
    local = local.strip().lower().strip(".")
    domain = domain.strip().lower().strip(".")
    tld = tld.strip().lower().strip(".")
    email = f"{local}@{domain}.{tld}"
    if _STANDARD_EMAIL_RE.fullmatch(email):
        return email
    return ""


def _is_plausible_email(email: str) -> bool:
    email = email.lower().strip()
    if not email or "@" not in email:
        return False
    if email.endswith((".png", ".jpg", ".gif", ".js", ".css", ".html")):
        return False
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if domain in _FALSE_EMAIL_HOSTS:
        return False
    # Reject emails whose "TLD" looks like glued English words
    tld = domain.rsplit(".", 1)[-1]
    if tld in {
        "self",
        "senior",
        "software",
        "forward",
        "book",
        "junior",
        "i",
        "im",
        "mobile",
        "years",
        "cybersecurity",
        "commit",
        "four",
    }:
        return False
    if len(tld) > 10:
        return False
    return True


def extract_email(text: str, fields: dict[str, str] | None = None) -> str:
    """Extract and normalize voluntarily published email addresses."""
    fields = fields or extract_labeled_fields(text)
    candidates: list[str] = []

    search_blobs = [text]
    if fields.get("email"):
        search_blobs.insert(0, fields["email"])

    for blob in search_blobs:
        for match in _STANDARD_EMAIL_RE.finditer(blob):
            candidates.append(match.group(1).lower())

        for pattern in _OBFUSCATED_EMAIL_PATTERNS:
            for match in pattern.finditer(blob):
                email = _normalize_email_parts(*match.groups())
                if email:
                    candidates.append(email)

    seen: set[str] = set()
    for email in candidates:
        if email in seen:
            continue
        seen.add(email)
        if _is_plausible_email(email):
            return email
    return ""


# ---------------------------------------------------------------------------
# Country / region
# ---------------------------------------------------------------------------

REGION_MAP = {
    # North America
    "united states": "US",
    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "america": "US",
    "canada": "Canada",
    "mexico": "LATAM",
    # LATAM
    "brazil": "LATAM",
    "argentina": "LATAM",
    "colombia": "LATAM",
    "chile": "LATAM",
    "peru": "LATAM",
    "uruguay": "LATAM",
    "paraguay": "LATAM",
    "bolivia": "LATAM",
    "ecuador": "LATAM",
    "venezuela": "LATAM",
    "costa rica": "LATAM",
    "panama": "LATAM",
    "guatemala": "LATAM",
    "honduras": "LATAM",
    "el salvador": "LATAM",
    "nicaragua": "LATAM",
    "cuba": "LATAM",
    "dominican republic": "LATAM",
    "puerto rico": "LATAM",
    # Europe
    "united kingdom": "Europe",
    "uk": "Europe",
    "england": "Europe",
    "scotland": "Europe",
    "wales": "Europe",
    "ireland": "Europe",
    "germany": "Europe",
    "france": "Europe",
    "spain": "Europe",
    "portugal": "Europe",
    "italy": "Europe",
    "netherlands": "Europe",
    "belgium": "Europe",
    "switzerland": "Europe",
    "austria": "Europe",
    "sweden": "Europe",
    "norway": "Europe",
    "denmark": "Europe",
    "finland": "Europe",
    "poland": "Europe",
    "czech republic": "Europe",
    "czechia": "Europe",
    "romania": "Europe",
    "hungary": "Europe",
    "greece": "Europe",
    "ukraine": "Europe",
    "russia": "Europe",
    "turkey": "Europe",
    "portugal": "Europe",
    "croatia": "Europe",
    "serbia": "Europe",
    "bulgaria": "Europe",
    "slovakia": "Europe",
    "slovenia": "Europe",
    "estonia": "Europe",
    "latvia": "Europe",
    "lithuania": "Europe",
    "iceland": "Europe",
    "luxembourg": "Europe",
    "malta": "Europe",
    "cyprus": "Europe",
    "bosnia and herzegovina": "Europe",
    "north macedonia": "Europe",
    "albania": "Europe",
    "moldova": "Europe",
    "belarus": "Europe",
    "georgia": "Europe",
    "armenia": "Europe",
    "azerbaijan": "Europe",
    # Asia
    "india": "Asia",
    "china": "Asia",
    "japan": "Asia",
    "south korea": "Asia",
    "korea": "Asia",
    "singapore": "Asia",
    "indonesia": "Asia",
    "malaysia": "Asia",
    "thailand": "Asia",
    "vietnam": "Asia",
    "philippines": "Asia",
    "taiwan": "Asia",
    "hong kong": "Asia",
    "pakistan": "Asia",
    "bangladesh": "Asia",
    "sri lanka": "Asia",
    "nepal": "Asia",
    "israel": "Asia",
    "uae": "Asia",
    "united arab emirates": "Asia",
    "saudi arabia": "Asia",
    "qatar": "Asia",
    "kuwait": "Asia",
    "bahrain": "Asia",
    "jordan": "Asia",
    "lebanon": "Asia",
    "iran": "Asia",
    "iraq": "Asia",
    "kazakhstan": "Asia",
    "uzbekistan": "Asia",
    "cambodia": "Asia",
    "myanmar": "Asia",
    "mongolia": "Asia",
    # Africa
    "nigeria": "Africa",
    "south africa": "Africa",
    "egypt": "Africa",
    "kenya": "Africa",
    "ghana": "Africa",
    "morocco": "Africa",
    "tunisia": "Africa",
    "ethiopia": "Africa",
    "uganda": "Africa",
    "tanzania": "Africa",
    "algeria": "Africa",
    "rwanda": "Africa",
    "senegal": "Africa",
    "ivory coast": "Africa",
    "cameroon": "Africa",
    # Oceania
    "australia": "Oceania",
    "new zealand": "Oceania",
    "fiji": "Oceania",
}

US_STATE_NAMES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

US_STATE_ABBR = set(US_STATE_NAMES.values()) | {"DC"}

CITY_TO_COUNTRY = {
    # US cities
    "san francisco": ("United States", "US"),
    "sf": ("United States", "US"),
    "bay area": ("United States", "US"),
    "silicon valley": ("United States", "US"),
    "los angeles": ("United States", "US"),
    "la": ("United States", "US"),
    "new york": ("United States", "US"),
    "nyc": ("United States", "US"),
    "brooklyn": ("United States", "US"),
    "manhattan": ("United States", "US"),
    "seattle": ("United States", "US"),
    "austin": ("United States", "US"),
    "dallas": ("United States", "US"),
    "houston": ("United States", "US"),
    "chicago": ("United States", "US"),
    "boston": ("United States", "US"),
    "denver": ("United States", "US"),
    "miami": ("United States", "US"),
    "atlanta": ("United States", "US"),
    "portland": ("United States", "US"),
    "philadelphia": ("United States", "US"),
    "phoenix": ("United States", "US"),
    "san diego": ("United States", "US"),
    "san jose": ("United States", "US"),
    "washington dc": ("United States", "US"),
    "washington d.c.": ("United States", "US"),
    "raleigh": ("United States", "US"),
    "durham": ("United States", "US"),
    "charlotte": ("United States", "US"),
    "nashville": ("United States", "US"),
    "minneapolis": ("United States", "US"),
    "detroit": ("United States", "US"),
    "pittsburgh": ("United States", "US"),
    "salt lake city": ("United States", "US"),
    "jacksonville": ("United States", "US"),
    "tampa": ("United States", "US"),
    "orlando": ("United States", "US"),
    "boulder": ("United States", "US"),
    "remote us": ("United States", "US"),
    "usa remote": ("United States", "US"),
    "us remote": ("United States", "US"),
    # Canada
    "toronto": ("Canada", "Canada"),
    "vancouver": ("Canada", "Canada"),
    "montreal": ("Canada", "Canada"),
    "montréal": ("Canada", "Canada"),
    "ottawa": ("Canada", "Canada"),
    "calgary": ("Canada", "Canada"),
    "edmonton": ("Canada", "Canada"),
    "waterloo": ("Canada", "Canada"),
    # LATAM
    "são paulo": ("Brazil", "LATAM"),
    "sao paulo": ("Brazil", "LATAM"),
    "rio de janeiro": ("Brazil", "LATAM"),
    "brasilia": ("Brazil", "LATAM"),
    "curitiba": ("Brazil", "LATAM"),
    "belo horizonte": ("Brazil", "LATAM"),
    "buenos aires": ("Argentina", "LATAM"),
    "córdoba": ("Argentina", "LATAM"),
    "cordoba": ("Argentina", "LATAM"),
    "bogotá": ("Colombia", "LATAM"),
    "bogota": ("Colombia", "LATAM"),
    "medellín": ("Colombia", "LATAM"),
    "medellin": ("Colombia", "LATAM"),
    "santiago": ("Chile", "LATAM"),
    "lima": ("Peru", "LATAM"),
    "montevideo": ("Uruguay", "LATAM"),
    "mexico city": ("Mexico", "LATAM"),
    "ciudad de méxico": ("Mexico", "LATAM"),
    "cdmx": ("Mexico", "LATAM"),
    "guadalajara": ("Mexico", "LATAM"),
    "monterrey": ("Mexico", "LATAM"),
    # Europe
    "london": ("United Kingdom", "Europe"),
    "manchester": ("United Kingdom", "Europe"),
    "edinburgh": ("United Kingdom", "Europe"),
    "berlin": ("Germany", "Europe"),
    "munich": ("Germany", "Europe"),
    "münchen": ("Germany", "Europe"),
    "hamburg": ("Germany", "Europe"),
    "frankfurt": ("Germany", "Europe"),
    "paris": ("France", "Europe"),
    "lyon": ("France", "Europe"),
    "amsterdam": ("Netherlands", "Europe"),
    "rotterdam": ("Netherlands", "Europe"),
    "madrid": ("Spain", "Europe"),
    "barcelona": ("Spain", "Europe"),
    "lisbon": ("Portugal", "Europe"),
    "lisboa": ("Portugal", "Europe"),
    "porto": ("Portugal", "Europe"),
    "rome": ("Italy", "Europe"),
    "milan": ("Italy", "Europe"),
    "milano": ("Italy", "Europe"),
    "stockholm": ("Sweden", "Europe"),
    "oslo": ("Norway", "Europe"),
    "copenhagen": ("Denmark", "Europe"),
    "helsinki": ("Finland", "Europe"),
    "warsaw": ("Poland", "Europe"),
    "krakow": ("Poland", "Europe"),
    "kraków": ("Poland", "Europe"),
    "prague": ("Czech Republic", "Europe"),
    "vienna": ("Austria", "Europe"),
    "zurich": ("Switzerland", "Europe"),
    "zürich": ("Switzerland", "Europe"),
    "geneva": ("Switzerland", "Europe"),
    "dublin": ("Ireland", "Europe"),
    "brussels": ("Belgium", "Europe"),
    "budapest": ("Hungary", "Europe"),
    "bucharest": ("Romania", "Europe"),
    "athens": ("Greece", "Europe"),
    "kyiv": ("Ukraine", "Europe"),
    "kiev": ("Ukraine", "Europe"),
    "istanbul": ("Turkey", "Europe"),
    "moscow": ("Russia", "Europe"),
    # Asia
    "bangalore": ("India", "Asia"),
    "bengaluru": ("India", "Asia"),
    "hyderabad": ("India", "Asia"),
    "mumbai": ("India", "Asia"),
    "delhi": ("India", "Asia"),
    "new delhi": ("India", "Asia"),
    "chennai": ("India", "Asia"),
    "pune": ("India", "Asia"),
    "kolkata": ("India", "Asia"),
    "gurgaon": ("India", "Asia"),
    "gurugram": ("India", "Asia"),
    "noida": ("India", "Asia"),
    "singapore": ("Singapore", "Asia"),
    "tokyo": ("Japan", "Asia"),
    "osaka": ("Japan", "Asia"),
    "seoul": ("South Korea", "Asia"),
    "beijing": ("China", "Asia"),
    "shanghai": ("China", "Asia"),
    "shenzhen": ("China", "Asia"),
    "hong kong": ("Hong Kong", "Asia"),
    "taipei": ("Taiwan", "Asia"),
    "bangkok": ("Thailand", "Asia"),
    "jakarta": ("Indonesia", "Asia"),
    "manila": ("Philippines", "Asia"),
    "kuala lumpur": ("Malaysia", "Asia"),
    "ho chi minh": ("Vietnam", "Asia"),
    "hanoi": ("Vietnam", "Asia"),
    "dubai": ("United Arab Emirates", "Asia"),
    "abu dhabi": ("United Arab Emirates", "Asia"),
    "tel aviv": ("Israel", "Asia"),
    "karachi": ("Pakistan", "Asia"),
    "lahore": ("Pakistan", "Asia"),
    "dhaka": ("Bangladesh", "Asia"),
    # Oceania
    "sydney": ("Australia", "Oceania"),
    "melbourne": ("Australia", "Oceania"),
    "brisbane": ("Australia", "Oceania"),
    "perth": ("Australia", "Oceania"),
    "auckland": ("New Zealand", "Oceania"),
    "wellington": ("New Zealand", "Oceania"),
    # Africa
    "lagos": ("Nigeria", "Africa"),
    "nairobi": ("Kenya", "Africa"),
    "cape town": ("South Africa", "Africa"),
    "johannesburg": ("South Africa", "Africa"),
    "cairo": ("Egypt", "Africa"),
    "accra": ("Ghana", "Africa"),
    "casablanca": ("Morocco", "Africa"),
}

_COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "south korea": "South Korea",
    "korea": "South Korea",
    "republic of korea": "South Korea",
    "czechia": "Czech Republic",
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "brasil": "Brazil",
    "méxico": "Mexico",
    "viet nam": "Vietnam",
    "russian federation": "Russia",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
}


def _region_for_country(country: str) -> str:
    key = country.lower().strip()
    if key in REGION_MAP:
        return REGION_MAP[key]
    # Canada special-case already mapped; US already mapped
    if key == "united states":
        return "US"
    if key == "canada":
        return "Canada"
    # Try alias then map
    canonical = _COUNTRY_ALIASES.get(key, country)
    return REGION_MAP.get(canonical.lower(), "Other / Unknown")


def _pycountry_lookup(token: str) -> str | None:
    token = token.strip()
    if not token or len(token) < 2:
        return None
    try:
        country = pycountry.countries.lookup(token)
        return country.name
    except LookupError:
        pass
    # Fuzzy only for longer tokens to avoid false positives
    if len(token) >= 4:
        try:
            results = pycountry.countries.search_fuzzy(token)
            if results:
                return results[0].name
        except LookupError:
            pass
    return None


def _clean_location_raw(raw: str) -> str:
    text = normalize_whitespace(raw)
    # Drop trailing remote/willing clauses if still attached
    text = re.split(
        r"(?i)\b(?:remote|willing to relocate|timezone|availability)\b\s*:",
        text,
        maxsplit=1,
    )[0]
    # Prefer the primary place before parenthetical timezone / notes
    # e.g. "Nigeria (UTC+1, ... partial with US East Coast)" -> "Nigeria"
    text = re.split(r"\s*\(", text, maxsplit=1)[0]
    text = re.sub(r"(?i)\b(?:fully\s+)?remote(?:\s+only)?\b", " ", text)
    text = re.sub(r"(?i)\bopen to (?:remote|relocation)\b", " ", text)
    text = re.sub(r"[|()]+", " ", text)
    text = normalize_whitespace(text)
    return text.strip(" ,;-/")


def extract_country_region(text: str, fields: dict[str, str] | None = None) -> str:
    """
    Return 'Country / Region' or 'Unknown' when ambiguous.

    Never guesses from weak signals.
    """
    fields = fields or extract_labeled_fields(text)
    raw = fields.get("location") or ""
    if not raw:
        # Fallback: first line mentioning Location inline already handled
        match = re.search(r"(?i)\blocation\s*[:\-–—]\s*([^\n]+)", text)
        raw = match.group(1) if match else ""

    cleaned = _clean_location_raw(raw)
    if not cleaned:
        return "Unknown"

    lower = cleaned.lower()

    # Explicit continent-only / remote-only without country
    if lower in {"remote", "worldwide", "global", "anywhere", "earth", "eu", "europe", "asia", "latam", "emea"}:
        if lower in {"eu", "europe"}:
            return "Unknown"  # continent alone without country
        return "Unknown"

    # US state abbreviation patterns: "Austin, TX" / "CA, USA" / "FL"
    state_match = re.search(
        r"(?i)\b([A-Za-z .'-]+?),\s*([A-Z]{2})\b(?:\s*,?\s*(?:USA|US|U\.S\.A\.|United States))?",
        cleaned,
    )
    if state_match and state_match.group(2).upper() in US_STATE_ABBR:
        return "United States / US"

    # "... FL (near Jacksonville)" already covered if FL present
    for abbr in US_STATE_ABBR:
        if re.search(rf"(?i)(?:^|[\s,/]){abbr}(?:[\s,/\)]|$)", cleaned):
            # Avoid matching short words inside other words; abbr already bounded
            if abbr in {"OR", "IN", "ME", "OK", "HI", "ID"}:
                # Require comma/context for ambiguous state codes
                if not re.search(rf"(?i),\s*{abbr}\b|\b{abbr}\s*,|\({abbr}\)", cleaned):
                    # Still allow "Location: OR" style
                    if lower.strip() != abbr.lower() and not re.search(
                        rf"(?i)\b(?:oregon|indiana|maine|oklahoma|hawaii|idaho)\b", lower
                    ):
                        continue
            return "United States / US"

    for state_name, _abbr in US_STATE_NAMES.items():
        if re.search(rf"(?i)\b{re.escape(state_name)}\b", lower):
            return "United States / US"

    # City lookup (longest keys first)
    for city in sorted(CITY_TO_COUNTRY.keys(), key=len, reverse=True):
        if re.search(rf"(?i)\b{re.escape(city)}\b", lower):
            country, region = CITY_TO_COUNTRY[city]
            return f"{country} / {region}"

    # Country aliases / direct names
    for alias, country in sorted(_COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"(?i)\b{re.escape(alias)}\b", lower):
            region = _region_for_country(country)
            return f"{country} / {region}"

    for country_name, region in sorted(REGION_MAP.items(), key=lambda x: -len(x[0])):
        if country_name in {"us", "uk", "uae"}:
            continue  # handled via aliases with word boundaries carefully
        if re.search(rf"(?i)\b{re.escape(country_name)}\b", lower):
            canonical = _COUNTRY_ALIASES.get(country_name, country_name.title())
            if country_name == "united states":
                canonical = "United States"
            elif country_name == "united kingdom":
                canonical = "United Kingdom"
            elif country_name == "united arab emirates":
                canonical = "United Arab Emirates"
            elif country_name == "south korea":
                canonical = "South Korea"
            elif country_name == "south africa":
                canonical = "South Africa"
            elif country_name == "new zealand":
                canonical = "New Zealand"
            elif country_name == "czech republic":
                canonical = "Czech Republic"
            elif country_name == "hong kong":
                canonical = "Hong Kong"
            elif country_name == "saudi arabia":
                canonical = "Saudi Arabia"
            elif country_name == "sri lanka":
                canonical = "Sri Lanka"
            elif country_name == "costa rica":
                canonical = "Costa Rica"
            elif country_name == "el salvador":
                canonical = "El Salvador"
            elif country_name == "dominican republic":
                canonical = "Dominican Republic"
            elif country_name == "puerto rico":
                canonical = "Puerto Rico"
            else:
                canonical = country_name.title() if country_name.islower() else country_name
            return f"{canonical} / {region}"

    # pycountry on comma-separated segments (rightmost often country)
    parts = [p.strip() for p in re.split(r"[,/|]", cleaned) if p.strip()]
    for part in reversed(parts):
        # Skip remote-ish tokens
        if re.search(r"(?i)^(remote|hybrid|onsite|on-site|anywhere)$", part):
            continue
        found = _pycountry_lookup(part)
        if found:
            region = _region_for_country(found)
            # Normalize common official names
            if found == "United States of America":
                found = "United States"
            if found == "Russian Federation":
                found = "Russia"
            if found == "Korea, Republic of":
                found = "South Korea"
            if found == "Viet Nam":
                found = "Vietnam"
            if found == "Czechia":
                found = "Czech Republic"
            return f"{found} / {region}"

    # Single token that is a known country via pycountry
    found = _pycountry_lookup(cleaned)
    if found:
        if found == "United States of America":
            found = "United States"
        region = _region_for_country(found)
        return f"{found} / {region}"

    return "Unknown"


# ---------------------------------------------------------------------------
# Specialization
# ---------------------------------------------------------------------------

SPECIALIZATION_ORDER = [
    "Frontend",
    "Backend",
    "Full-stack",
    "DevOps / SRE",
    "Cloud / Infrastructure",
    "AI / ML",
    "Data Engineering",
    "Data Science / Analytics",
    "Mobile",
    "Security",
    "QA / Automation",
    "Embedded / Systems",
    "Other / Unknown",
]

_EXPLICIT_TITLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:full[\s\-]?stack)\b"), "Full-stack"),
    (re.compile(r"(?i)\b(?:front[\s\-]?end)\b"), "Frontend"),
    (re.compile(r"(?i)\b(?:back[\s\-]?end)\b"), "Backend"),
    (re.compile(r"(?i)\b(?:devops|sre|site reliability)\b"), "DevOps / SRE"),
    (re.compile(r"(?i)\b(?:cloud(?:\s+engineer|\s+architect)?|infrastructure engineer)\b"), "Cloud / Infrastructure"),
    (re.compile(r"(?i)\b(?:machine learning|ml engineer|ai engineer|deep learning|computer vision|nlp|llm)\b"), "AI / ML"),
    (re.compile(r"(?i)\b(?:data engineer(?:ing)?)\b"), "Data Engineering"),
    (re.compile(r"(?i)\b(?:data scient(?:ist|ce)|analytics engineer|bi engineer)\b"), "Data Science / Analytics"),
    (re.compile(r"(?i)\b(?:mobile(?:\s+engineer|\s+developer)?|ios|android|react native|flutter)\b"), "Mobile"),
    (re.compile(r"(?i)\b(?:security engineer|appsec|infosec|cybersecurity)\b"), "Security"),
    (re.compile(r"(?i)\b(?:qa(?:\s+engineer)?|test(?:ing)? engineer|sdet|automation engineer)\b"), "QA / Automation"),
    (re.compile(r"(?i)\b(?:embedded|firmware|systems? engineer|kernel)\b"), "Embedded / Systems"),
    (re.compile(r"(?i)\b(?:ui/?ux|ux/?ui|product designer|ux researcher)\b"), "Other / Unknown"),
]

_KEYWORD_SETS: dict[str, tuple[str, ...]] = {
    "Frontend": (
        "react",
        "next.js",
        "nextjs",
        "vue",
        "angular",
        "svelte",
        "css",
        "html",
        "tailwind",
        "webpack",
        "vite",
        "ui engineering",
        "frontend",
        "front-end",
    ),
    "Backend": (
        "spring boot",
        "django",
        "flask",
        "fastapi",
        "rails",
        "laravel",
        "nestjs",
        "express",
        "graphql",
        "grpc",
        "microservices",
        "api development",
        "backend",
        "back-end",
    ),
    "DevOps / SRE": (
        "kubernetes",
        "k8s",
        "terraform",
        "ansible",
        "ci/cd",
        "jenkins",
        "prometheus",
        "grafana",
        "helm",
        "devops",
        "sre",
    ),
    "Cloud / Infrastructure": (
        "aws",
        "gcp",
        "azure",
        "cloudformation",
        "pulumi",
        "infrastructure as code",
        "cloud architect",
    ),
    "AI / ML": (
        "pytorch",
        "tensorflow",
        "scikit-learn",
        "huggingface",
        "langgraph",
        "langchain",
        "llm",
        "nlp",
        "computer vision",
        "deep learning",
        "machine learning",
        "mlops",
        "rag",
    ),
    "Data Engineering": (
        "spark",
        "airflow",
        "dbt",
        "kafka",
        "etl",
        "data pipeline",
        "data pipelines",
        "snowflake",
        "databricks",
        "flink",
    ),
    "Data Science / Analytics": (
        "data science",
        "pandas",
        "numpy",
        "tableau",
        "power bi",
        "statistics",
        "a/b testing",
        "analytics",
    ),
    "Mobile": (
        "swift",
        "kotlin",
        "react native",
        "flutter",
        "ios",
        "android",
        "swiftui",
    ),
    "Security": (
        "penetration",
        "appsec",
        "owasp",
        "security",
        "cryptography",
        "siem",
    ),
    "QA / Automation": (
        "selenium",
        "cypress",
        "playwright",
        "pytest",
        "test automation",
        "qa",
    ),
    "Embedded / Systems": (
        "embedded",
        "firmware",
        "rtos",
        "fpga",
        "bare metal",
        "c/c++",
        "kernel",
        "rust embedded",
    ),
}


def classify_specialization(text: str, fields: dict[str, str] | None = None) -> str:
    """
    Classify specialization conservatively.

    Prefer explicit titles/descriptions. Do not mark Full-stack just because
    both frontend and backend technologies appear in a skills list.
    """
    fields = fields or extract_labeled_fields(text)
    tech = fields.get("technologies", "")
    # Prefer prose outside the technologies field for role intent
    prose = text
    if tech:
        prose = text.replace(tech, " ")

    found: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        if label not in seen and label != "Other / Unknown":
            seen.add(label)
            found.append(label)

    # Explicit role statements in prose (not the raw tech laundry list)
    role_window = prose[:1200] + "\n" + prose[-800:]
    for pattern, label in _EXPLICIT_TITLE_PATTERNS:
        if pattern.search(role_window):
            add(label)

    # Strong full-stack statements
    if re.search(
        r"(?i)\b(?:full[\s\-]?stack|end[\s\-]?to[\s\-]?end(?:\s+development)?)\b",
        role_window,
    ):
        add("Full-stack")

    # Keyword evidence: weigh technologies field + role prose, but require
    # stronger signals for noisy domains (AI/ML is often casual LLM mention).
    search_blob = f"{tech}\n{role_window}".lower()
    keyword_hits: dict[str, int] = {}
    for label, keywords in _KEYWORD_SETS.items():
        score = 0
        for kw in keywords:
            if kw in search_blob:
                score += 1
        if score:
            keyword_hits[label] = score

    strong_single = {
        "Data Engineering",
        "Mobile",
        "Security",
        "Embedded / Systems",
        "DevOps / SRE",
        "QA / Automation",
    }
    for label, score in sorted(keyword_hits.items(), key=lambda x: -x[1]):
        if label == "Full-stack":
            continue
        if label == "AI / ML":
            # Require clearer ML signal than a passing "LLM"/"Claude" mention
            if score >= 2 or re.search(
                r"(?i)\b(?:machine learning|ml engineer|ai engineer|deep learning|"
                r"computer vision|nlp engineer|data scientist)\b",
                role_window,
            ):
                add(label)
            continue
        if score >= 2 or (score >= 1 and label in strong_single):
            add(label)

    # If both Frontend and Backend keywords exist WITHOUT full-stack claim,
    # keep both rather than collapsing to Full-stack (per requirements).
    # However if user explicitly said Frontend SWE or Full-stack, titles win.

    if not found:
        # Weak single-keyword fallback for clear domains
        for label in (
            "AI / ML",
            "Data Engineering",
            "DevOps / SRE",
            "Mobile",
            "Security",
            "Embedded / Systems",
            "Frontend",
            "Backend",
            "QA / Automation",
            "Data Science / Analytics",
            "Cloud / Infrastructure",
        ):
            if keyword_hits.get(label, 0) >= 1:
                add(label)
                break

    if not found:
        return "Unknown"

    # Stable preferred ordering
    ordered = [s for s in SPECIALIZATION_ORDER if s in seen]
    # Cap to a few most relevant
    return ", ".join(ordered[:4])


# ---------------------------------------------------------------------------
# Profile / resume links
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"(?i)\bhttps?://[^\s<>\"']+|(?:www\.)[^\s<>\"']+"
)

_DRIVE_RE = re.compile(
    r"(?i)https?://(?:drive|docs)\.google\.com/[^\s<>\"']+"
)


def _normalize_url(url: str) -> str:
    url = url.rstrip(").,;]>'\"")
    if url.lower().startswith("www."):
        url = "https://" + url
    return url


def _link_priority(url: str) -> int:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    full = url.lower()
    if "linkedin.com" in host:
        return 1
    if "github.com" in host:
        return 2
    if any(x in full for x in ("resume", "résumé", "cv", "curriculum")):
        return 3
    if "drive.google.com" in host or "docs.google.com" in host:
        return 3
    if any(x in full for x in ("portfolio", "behance", "dribbble")):
        return 4
    if host and not any(
        bad in host
        for bad in (
            "ycombinator.com",
            "news.ycombinator",
            "wantstobehired.com",
            "imgur.com",
            "twitter.com",
            "x.com",
            "medium.com",
        )
    ):
        # Personal / other professional site
        if "github.io" in host:
            return 4
        return 5
    return 99


def extract_profile_links(text: str, fields: dict[str, str] | None = None) -> str:
    """
    Extract professional links with preferred priority.

    Multiple links are joined with newlines.
    """
    fields = fields or extract_labeled_fields(text)
    urls: list[str] = []

    blobs = [text]
    if fields.get("resume"):
        blobs.insert(0, fields["resume"])

    for blob in blobs:
        for match in _URL_RE.finditer(blob):
            url = _normalize_url(match.group(0))
            if url.lower().startswith("http"):
                urls.append(url)

    # Deduplicate preserving best order
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        # Skip HN and tracking noise
        if _link_priority(url) >= 99:
            continue
        seen.add(key)
        unique.append(url)

    unique.sort(key=_link_priority)

    # Keep LinkedIn, GitHub, resume/CV, portfolio, personal — drop low-value extras
    filtered = [u for u in unique if _link_priority(u) <= 5]
    # Limit to a reasonable number while keeping all major profile types
    return "\n".join(filtered[:6])


# ---------------------------------------------------------------------------
# Years of experience
# ---------------------------------------------------------------------------

_EXPERIENCE_PATTERNS = [
    re.compile(
        r"(?i)\b(\d{1,2})\s*\+?\s*years?\s+(?:of\s+)?(?:experience|exp\.?|professional experience)\b"
    ),
    re.compile(
        r"(?i)\b(?:experience|exp\.?)\s*[:\-–—]\s*(\d{1,2})\s*\+?\s*years?\b"
    ),
    re.compile(
        r"(?i)\b(\d{1,2})\s*\+?\s*yrs?(?:\s+of\s+(?:experience|exp\.?))?\b"
    ),
    re.compile(
        r"(?i)\bwith\s+(\d{1,2})\s*\+?\s*years?\s+(?:of\s+)?(?:experience|exp\.?)?\b"
    ),
    re.compile(
        r"(?i)\b(\d{1,2})\s*\+?\s*years?\s+(?:as|in|building|writing|working|shipping)\b"
    ),
    re.compile(
        r"(?i)\bover\s+(\d{1,2})\s*years?\s+(?:of\s+)?(?:experience|exp\.?)?\b"
    ),
]


def extract_years_of_experience(text: str) -> int | None:
    """
    Return stated years of experience when clearly present.

    Returns None when unknown / ambiguous. Caps to a realistic range (0–45).
    """
    if not text:
        return None

    candidates: list[int] = []
    for pattern in _EXPERIENCE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                years = int(match.group(1))
            except ValueError:
                continue
            if 0 <= years <= 45:
                candidates.append(years)

    if not candidates:
        return None

    # Prefer the largest plausible stated tenure (people often mention multiple)
    return max(candidates)


# ---------------------------------------------------------------------------
# Candidate parse entrypoint
# ---------------------------------------------------------------------------

def parse_candidate_comment(item: dict) -> dict[str, str] | None:
    """Parse a top-level HN comment into the five Excel fields."""
    from .cleaning import clean_html

    if not item or item.get("deleted") or item.get("dead"):
        return None
    raw_html = item.get("text")
    if not raw_html:
        return None

    text = clean_html(raw_html)
    if not text or len(text) < 20:
        return None

    # Skip obvious non-candidate discussion
    lower = text.lower()
    if lower.startswith(("flagged", "dead")):
        return None

    fields = extract_labeled_fields(text)

    # Heuristic: hiring threads usually have Location or Email or Resume markers,
    # or substantial self-description. Pure replies without those are skipped.
    has_structure = any(k in fields for k in ("location", "email", "resume", "technologies"))
    has_self_pitch = bool(
        re.search(
            r"(?i)\b(looking for|seeking|available|engineer|developer|years? of experience)\b",
            text,
        )
    )
    if not has_structure and not has_self_pitch:
        return None

    years = extract_years_of_experience(text)

    return {
        "Full Name": extract_full_name(text, fields),
        "Email": extract_email(text, fields),
        "Country / Geographic Region": extract_country_region(text, fields),
        "Specialization": classify_specialization(text, fields),
        "Profile / Resume Link": extract_profile_links(text, fields),
        "_hn_id": str(item.get("id", "")),
        "_hn_by": str(item.get("by", "")),
        "_years_experience": "" if years is None else str(years),
        "_location_raw": (fields.get("location") or "")[:200],
    }
