"""CLI: scrape a HN hiring thread and write Excel output."""

from __future__ import annotations

import argparse
import sys

from hn_scraper.excel_export import export_to_xlsx
from hn_scraper.pipeline import extract_developers_from_url, public_rows

DEFAULT_URL = "https://news.ycombinator.com/item?id=50338726"
DEFAULT_OUT = "HN_Developers_November_2026.xlsx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract HN 'Who wants to be hired?' candidates to Excel."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Hacker News thread URL")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output .xlsx path")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.12,
        help="Delay between Firebase API requests in seconds (default: 0.12)",
    )
    parser.add_argument(
        "--prefer-algolia",
        action="store_true",
        help="Use Algolia HN API first (faster; still free HN data mirror)",
    )
    args = parser.parse_args(argv)

    def on_progress(value: float, message: str) -> None:
        pct = int(value * 100)
        print(f"[{pct:3d}%] {message}", flush=True)

    try:
        records = extract_developers_from_url(
            args.url,
            delay=args.delay,
            progress_callback=on_progress,
            prefer_algolia=args.prefer_algolia,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    rows = public_rows(records)
    path = export_to_xlsx(rows, args.out)
    print(f"Wrote {len(rows)} candidates to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
