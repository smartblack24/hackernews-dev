"""Excel export for developer candidate records."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from .cleaning import sanitize_excel_cell

COLUMNS = [
    "Full Name",
    "Email",
    "Country / Geographic Region",
    "Specialization",
    "Profile / Resume Link",
]

SHEET_NAME = "Developers"


def _auto_column_width(ws, min_width: int = 12, max_width: int = 55) -> None:
    for idx, column in enumerate(COLUMNS, start=1):
        letter = get_column_letter(idx)
        max_len = len(column)
        for cell in ws[letter]:
            if cell.value is None:
                continue
            # For multi-line cells, use longest line
            value = str(cell.value)
            line_len = max(len(line) for line in value.splitlines()) if value else 0
            max_len = max(max_len, line_len)
        ws.column_dimensions[letter].width = max(min_width, min(max_width, max_len + 2))


def build_workbook(records: Iterable[dict]) -> Workbook:
    """Create a formatted workbook with exactly five columns."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F3E46")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Border(
        left=Side(style="thin", color="D0D5DD"),
        right=Side(style="thin", color="D0D5DD"),
        top=Side(style="thin", color="D0D5DD"),
        bottom=Side(style="thin", color="D0D5DD"),
    )
    body_alignment = Alignment(vertical="top", wrap_text=True)

    for col_idx, name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin

    row_idx = 2
    for record in records:
        for col_idx, name in enumerate(COLUMNS, start=1):
            raw = record.get(name, "") or ""
            value = sanitize_excel_cell(raw)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = body_alignment
            cell.border = thin

            # Make a single URL clickable when the cell contains exactly one URL
            if name == "Profile / Resume Link" and value:
                lines = [ln.strip() for ln in value.splitlines() if ln.strip()]
                if len(lines) == 1 and lines[0].lower().startswith("http"):
                    cell.hyperlink = lines[0]
                    cell.font = Font(color="0563C1", underline="single")
        row_idx += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{max(1, row_idx - 1)}"
    ws.row_dimensions[1].height = 22
    _auto_column_width(ws)
    return wb


def export_to_xlsx(records: list[dict], output_path: str | Path) -> Path:
    """Write records to an .xlsx file on disk."""
    path = Path(output_path)
    wb = build_workbook(records)
    wb.save(path)
    return path


def export_to_bytes(records: list[dict]) -> bytes:
    """Return workbook bytes for Streamlit download buttons."""
    wb = build_workbook(records)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
