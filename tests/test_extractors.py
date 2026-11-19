"""Unit tests for field extractors using known comment patterns."""

from __future__ import annotations

from hn_scraper.cleaning import clean_html
from hn_scraper.extractors import (
    classify_specialization,
    extract_country_region,
    extract_email,
    extract_full_name,
    extract_labeled_fields,
    extract_profile_links,
    extract_years_of_experience,
    parse_candidate_comment,
)
from hn_scraper.pipeline import should_include_candidate, sort_records_by_region


def test_obfuscated_emails():
    assert extract_email("Email: john [at] gmail [dot] com") == "john@gmail.com"
    assert extract_email("Email: jane at example dot org") == "jane@example.org"
    assert extract_email("Email: ptx2 at-sign ptx2 dot net") == "ptx2@ptx2.net"
    assert extract_email("shetyemanasi18[at]gmail[dot]com") == "shetyemanasi18@gmail.com"
    assert extract_email("plain: serginyo1990@gmail.com") == "serginyo1990@gmail.com"


def test_locations():
    samples = [
        ("Location: San Francisco, CA", "United States / US"),
        ("Location: Austin, TX", "United States / US"),
        ("Location: São Paulo, Brazil", "Brazil / LATAM"),
        ("Location: Buenos Aires", "Argentina / LATAM"),
        ("Location: Bogotá, Colombia", "Colombia / LATAM"),
        ("Location: Toronto, Canada", "Canada / Canada"),
        ("Location: Berlin, Germany", "Germany / Europe"),
        ("Location: Bangalore, India", "India / Asia"),
        ("Location: Hyderabad, India", "India / Asia"),
        ("Location: Ukraine", "Ukraine / Europe"),
        ("Location: Saint Johns, FL (near Jacksonville)", "United States / US"),
        ("Location: Remote", "Unknown"),
    ]
    for text, expected in samples:
        assert extract_country_region(text) == expected, text


def test_specialization_fullstack_requires_explicit():
    tech_only = (
        "Location: US\nTechnologies: React, Node.js, PostgreSQL\n"
        "I build web applications and APIs."
    )
    # May classify Frontend/Backend from keywords, but not Full-stack without claim
    result = classify_specialization(tech_only)
    assert "Full-stack" not in result

    explicit = (
        "Location: US\nTechnologies: React, Node.js\n"
        "Product-minded full-stack engineer with 20 years experience."
    )
    assert "Full-stack" in classify_specialization(explicit)


def test_ai_ml_and_links():
    text = (
        "Location: Hyderabad, India\n"
        "Technologies: Python, PyTorch, Computer Vision, LLMs, RAG\n"
        "Email: umara040@gmail.com\n"
        "LinkedIn: https://www.linkedin.com/in/umar11\n"
        "AI / Computer Vision Engineer with 4.5+ years of experience"
    )
    assert "AI / ML" in classify_specialization(text)
    assert extract_country_region(text) == "India / Asia"
    links = extract_profile_links(text)
    assert "linkedin.com/in/umar11" in links


def test_name_not_from_username():
    item = {
        "id": 1,
        "by": "serginyo90",
        "text": (
            "Location: Saint Johns, FL\nRemote: Yes\n"
            "Technologies: TypeScript, Node.js\n"
            "Email: serginyo1990@gmail.com\n"
            "Senior backend engineer, about 10 years.\n"
            "GitHub: https://github.com/Serginyo90\n"
            "LinkedIn: https://www.linkedin.com/in/cherbadzhy"
        ),
        "type": "comment",
    }
    parsed = parse_candidate_comment(item)
    assert parsed is not None
    # Single-token LinkedIn slug is not treated as a full name
    assert parsed["Full Name"] == ""
    assert parsed["Email"] == "serginyo1990@gmail.com"
    assert parsed["Country / Geographic Region"] == "United States / US"
    assert "Backend" in parsed["Specialization"] or "AI / ML" in parsed["Specialization"]


def test_name_from_linkedin_and_cv():
    text = (
        "Location: Nigeria\nEmail: someone@example.com\n"
        "LinkedIn: https://www.linkedin.com/in/seth-owolabi-05813039a"
    )
    assert extract_full_name(text) == "Seth Owolabi"

    cv_text = (
        "Location: Armenia\n"
        "Résumé/CV: https://wyddy.tech/makeev-daniil-cv-en.pdf\n"
        "Email: x@y.com"
    )
    assert extract_full_name(cv_text) == "Makeev Daniil"


def test_name_from_first_last_email():
    text = "Location: USA\nEmail: jon.north@adiuvat-consulting.com\nBackend engineer"
    assert extract_full_name(text) == "Jon North"


def test_signature_name():
    text = (
        "Location: Ukraine\nEmail: vuchen2023 at gmail.com\n"
        "UX / CX Researcher & QA Tester in Training\n"
        "Volodymyr"
    )
    assert extract_full_name(text) == "Volodymyr"


def test_clean_html_preserves_links():
    raw = 'Résumé: <a href="https://example.com/cv">CV</a><p>Email: a@b.com'
    cleaned = clean_html(raw)
    assert "https://example.com/cv" in cleaned
    assert "a@b.com" in cleaned


def test_hn_bare_p_tags_and_email_boundaries():
    raw = (
        "Location: US<p>Remote: Yes<p>Willing to relocate: No<p>"
        "Email: logandark@logandark.net<p>Self-taught software engineer"
    )
    cleaned = clean_html(raw)
    assert "Location: US\n" in cleaned or cleaned.startswith("Location: US")
    assert "Remote: Yes" in cleaned
    assert extract_email(cleaned) == "logandark@logandark.net"
    assert extract_country_region(cleaned) == "United States / US"


def test_location_ignores_us_mention_inside_timezone_notes():
    text = (
        "Location: Nigeria (UTC+1, same time zone as Central Europe; "
        "partial with US East Coast)\nRemote: Yes\n"
        "Email: someone@example.com"
    )
    assert extract_country_region(text) == "Nigeria / Africa"


def test_labeled_fields():
    text = "Location: Berlin\nEmail: x@y.com\nTechnologies: Go, K8s"
    fields = extract_labeled_fields(text)
    assert fields["location"].startswith("Berlin")
    assert "x@y.com" in fields["email"]


def test_years_of_experience():
    assert extract_years_of_experience("10+ years of experience building APIs") == 10
    assert extract_years_of_experience("Experience: 2 years") == 2
    assert extract_years_of_experience("Looking for remote work") is None


def test_filters_india_and_junior():
    india = {
        "Country / Geographic Region": "India / Asia",
        "_location_raw": "Bangalore, India",
        "_years_experience": "8",
    }
    junior = {
        "Country / Geographic Region": "United States / US",
        "_location_raw": "Austin, TX",
        "_years_experience": "2",
    }
    keep = {
        "Country / Geographic Region": "Canada / Canada",
        "_location_raw": "Toronto",
        "_years_experience": "5",
    }
    unknown_years = {
        "Country / Geographic Region": "Germany / Europe",
        "_location_raw": "Berlin",
        "_years_experience": "",
    }
    assert should_include_candidate(india) is False
    assert should_include_candidate(junior) is False
    assert should_include_candidate(keep) is True
    assert should_include_candidate(unknown_years) is True


def test_canada_sorts_after_us():
    rows = [
        {"Full Name": "B", "Country / Geographic Region": "Brazil / LATAM"},
        {"Full Name": "C", "Country / Geographic Region": "Canada / Canada"},
        {"Full Name": "A", "Country / Geographic Region": "United States / US"},
        {"Full Name": "D", "Country / Geographic Region": "Germany / Europe"},
        {"Full Name": "E", "Country / Geographic Region": "Japan / Asia"},
    ]
    sorted_rows = sort_records_by_region(rows)
    regions = [r["Country / Geographic Region"].split(" / ")[-1] for r in sorted_rows]
    assert regions == ["US", "Canada", "LATAM", "Europe", "Asia"]
