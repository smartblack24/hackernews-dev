# Hacker News Developer Scraper

Extracts developer information from Hacker News **“Who wants to be hired?”** threads using the official Hacker News API, then exports results to Excel (`.xlsx`).

No Claude, OpenAI, or other AI/paid enrichment APIs are used — only rule-based parsing (regex, keyword matching, `pycountry`).

## Features

- Accepts any Hacker News thread URL
- Fetches top-level candidate comments (skips deleted / empty / off-topic)
- Extracts five fields:
  - Full Name
  - Email (including obfuscated forms)
  - Country / Geographic Region
  - Specialization
  - Profile / Resume Link
- Streamlit web UI with progress, preview, and Excel download
- CLI export script for batch runs

## Requirements

- Python 3.11+
- Network access to `https://hacker-news.firebaseio.com`

## Setup

```bash
cd ycombinator
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run the Streamlit interface

```bash
streamlit run app.py
```

1. Confirm or paste a HN thread URL (default: November 2026 hiring thread).
2. Click **Fetch Developers**.
3. Review the preview table.
4. Click **Download Excel** to save `HN_Developers_November_2026.xlsx`.

## CLI export

```bash
python run_export.py --url "https://news.ycombinator.com/item?id=50338726" --out HN_Developers_November_2026.xlsx
```

Optional: `--delay 0.15` to slow API pacing.

## Excel format

- Worksheet name: `Developers`
- Exactly five columns
- Bold headers, frozen first row, auto-filter enabled
- Wrapped text for multi-value specialization / links
- Auto-adjusted column widths

Filter in Excel by country, region text, or specialization.

## Project layout

```
ycombinator/
├── app.py                 # Streamlit UI
├── run_export.py          # CLI exporter
├── requirements.txt
├── README.md
└── hn_scraper/
    ├── api.py             # HN API client
    ├── cleaning.py        # HTML cleanup / Excel sanitization
    ├── extractors.py      # Name, email, location, specialization, links
    ├── excel_export.py    # openpyxl workbook builder
    └── pipeline.py        # End-to-end orchestration
```

## Notes on accuracy

- Names and emails are never invented; blanks stay blank.
- HN usernames are not treated as real names.
- Ambiguous locations become `Unknown`.
- Full-stack is only assigned when explicitly stated (not merely from mixed tech lists).
- Contact data is limited to what candidates publish in the thread.

## API notes

The scraper prefers the official Firebase HN API (`hacker-news.firebaseio.com`). If that endpoint is unreachable (timeouts / network issues), it automatically falls back to the free Algolia HN mirror (`hn.algolia.com`), which returns the same public thread data in one request. No paid APIs or AI services are used.

```bash
# Optional: skip Firebase and use Algolia first (faster)
python run_export.py --prefer-algolia
```
