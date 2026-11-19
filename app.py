"""Streamlit UI for the Hacker News developer scraper."""

from __future__ import annotations

import streamlit as st

from hn_scraper.excel_export import export_to_bytes
from hn_scraper.pipeline import extract_developers_from_url, public_rows

DEFAULT_URL = "https://news.ycombinator.com/item?id=50338726"
OUTPUT_NAME = "HN_Developers_November_2026.xlsx"


def main() -> None:
    st.set_page_config(
        page_title="HN Developer Scraper",
        page_icon="📰",
        layout="wide",
    )

    st.title("Hacker News Developer Scraper")
    st.caption(
        "Extracts candidate details from “Who wants to be hired?” threads "
        "via the official Hacker News API. No AI APIs or paid enrichment."
    )

    url = st.text_input(
        "Hacker News thread URL",
        value=DEFAULT_URL,
        help="Paste any HN item URL, e.g. https://news.ycombinator.com/item?id=50338726",
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        fetch_clicked = st.button("Fetch Developers", type="primary", use_container_width=True)

    if "records" not in st.session_state:
        st.session_state.records = []
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""

    if fetch_clicked:
        st.session_state.last_error = ""
        progress = st.progress(0.0)
        status = st.empty()

        def on_progress(value: float, message: str) -> None:
            progress.progress(min(max(value, 0.0), 1.0))
            status.write(message)

        try:
            with st.spinner("Fetching candidates from Hacker News…"):
                records = extract_developers_from_url(url, progress_callback=on_progress)
            st.session_state.records = public_rows(records)
            progress.progress(1.0)
            status.success(f"Extracted {len(st.session_state.records)} candidates.")
        except Exception as exc:  # noqa: BLE001 - surface to UI
            st.session_state.records = []
            st.session_state.last_error = str(exc)
            status.error(f"Failed: {exc}")

    if st.session_state.last_error and not st.session_state.records:
        st.error(st.session_state.last_error)

    records = st.session_state.records
    st.metric("Total candidates", len(records))

    if records:
        st.subheader("Preview")
        st.dataframe(records, use_container_width=True, height=420)

        xlsx_bytes = export_to_bytes(records)
        st.download_button(
            label="Download Excel",
            data=xlsx_bytes,
            file_name=OUTPUT_NAME,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

        with st.expander("Column notes"):
            st.markdown(
                """
- **Full Name** — only when explicitly stated (never from HN username)
- **Email** — includes de-obfuscated forms such as `name [at] domain [dot] com`
- **Country / Geographic Region** — formatted as `Country / Region` (e.g. `Brazil / LATAM`)
- **Specialization** — rule-based from titles and technologies
- **Profile / Resume Link** — LinkedIn, GitHub, résumé, portfolio, personal sites
                """
            )


if __name__ == "__main__":
    main()
