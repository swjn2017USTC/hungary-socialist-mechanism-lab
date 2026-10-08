"""Fail-closed parsers for the first batch of audited real sources.

Every parser validates the audited structure (title, header names, column
count, unit evidence) BEFORE any numeric is read. Unknown columns, duplicate
headers, renamed titles, wrong unit rows, embedded DTDs and empty payloads
raise :class:`SourceSchemaChanged` naming the source and the drift; selected
core series with missing values, missing months/years or duplicate periods
raise :class:`SourceContentIncomplete`. Neither is ever silently scraped
around: raw bytes may be kept for audit, but no runnable artifact is
published from a drifted payload.

The audited header/title strings below were pinned from the live official
payloads during the P02 source audit (see MATERIAL_ECONOMY_EXPANSION_PLAN.md
"Source audit findings"). If a source changes, ingestion must fail until a
human re-audits and updates the pinned schema - never guess the new layout.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from hsm_lab.contract.schemas import ConfigError, Frequency, ResearchGateError

__all__ = [
    "ParsedSeries",
    "SourceContentIncomplete",
    "SourceSchemaChanged",
    "parse_fed_h15_zip",
    "parse_fred_fedfunds_csv",
    "parse_ksh_agriculture_html",
    "parse_ksh_gdp_csv",
    "parse_ksh_industry_csv",
    "parse_ksh_trade_html",
    "parse_mnb_fx_html",
    "parse_worldbank_pink_sheet_xlsx",
]


class SourceSchemaChanged(ResearchGateError):
    """Structural drift between a live payload and the audited schema."""

    def __init__(self, source_id: str, drift: str) -> None:
        super().__init__(f"source_schema_changed: source {source_id!r}: {drift}")
        self.source_id = source_id
        self.drift = drift


class SourceContentIncomplete(ResearchGateError):
    """Payload parsed, but a selected core series is incomplete or empty."""

    def __init__(self, source_id: str, reason: str) -> None:
        super().__init__(f"source_data_incomplete: source {source_id!r}: {reason}")
        self.source_id = source_id
        self.reason = reason


@dataclass(frozen=True)
class ParsedSeries:
    """One normalized series extracted from a raw payload.

    ``rows`` holds ``(period, value)`` pairs at ``frequency``; periods are
    already normalized repo strings (``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``).
    """

    variable_id: str
    unit: str
    frequency: Frequency
    rows: tuple[tuple[str, float], ...]


# ----------------------------------------------------------------------
# Shared numeric/decoding helpers (KSH tables and MNB pages)
# ----------------------------------------------------------------------

_MISSING_TOKENS = frozenset({"", ".", "..", "...", "…", "-", "–", "—", "x", "X"})
_UTF8_NBSP = " "


def _decode_text(data: bytes, source_id: str) -> str:
    """Decode a text payload; UTF-8 first, then cp1250/ISO-8859-2 (KSH)."""
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SourceSchemaChanged(
        source_id, "payload is not decodable as UTF-8, cp1250 or ISO-8859-2 text"
    )


def _norm_cell(text: str) -> str:
    """Normalize a header cell: NBP/thousands spaces and comma-space vanish."""
    collapsed = re.sub(r"\s+", " ", text.replace(" ", " ")).strip()
    return re.sub(r",\s+", ",", collapsed)


def _parse_number(text: str, source_id: str, context: str) -> float | None:
    """Parse one numeric cell; missing symbols return None, junk is drift."""
    stripped = text.replace(" ", " ").replace("​", " ").strip()
    if stripped in _MISSING_TOKENS:
        return None
    compact = stripped.replace(" ", "").replace("'", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", compact):
        return float(compact)
    if re.fullmatch(r"-?\d+,\d+", compact):
        return float(compact.replace(",", "."))
    raise SourceSchemaChanged(
        source_id, f"unparseable numeric cell {text!r} in {context}"
    )


def _month_range(start_month: str, end_month: str) -> list[str]:
    y0, m0 = int(start_month[:4]), int(start_month[5:7])
    y1, m1 = int(end_month[:4]), int(end_month[5:7])
    if (y1, m1) < (y0, m0):
        raise ConfigError(f"inverted monthly window {start_month}..{end_month}")
    out: list[str] = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _require_complete_years(
    source_id: str, series_id: str, rows: dict[int, float], start_year: int, end_year: int
) -> list[tuple[str, float]]:
    missing = [y for y in range(start_year, end_year + 1) if y not in rows]
    if missing:
        raise SourceContentIncomplete(
            source_id,
            f"core series {series_id!r} is missing year(s) {missing} inside the "
            f"requested window {start_year}-{end_year}; missing years are never imputed",
        )
    if not rows:
        raise SourceContentIncomplete(source_id, f"core series {series_id!r} has no rows")
    return [(str(y), rows[y]) for y in range(start_year, end_year + 1)]


def _require_complete_months(
    source_id: str, series_id: str, rows: dict[str, float], start_month: str, end_month: str
) -> list[tuple[str, float]]:
    wanted = _month_range(start_month, end_month)
    missing = [p for p in wanted if p not in rows]
    if missing:
        raise SourceContentIncomplete(
            source_id,
            f"core series {series_id!r} is missing month(s) {missing[:8]}"
            f"{'...' if len(missing) > 8 else ''} inside the requested window "
            f"{start_month}..{end_month}; quarterly forcing never averages over gaps",
        )
    return [(p, rows[p]) for p in wanted]


# ----------------------------------------------------------------------
# KSH CSV engine (gdp0002 / ipa0002)
# ----------------------------------------------------------------------


def _read_ksh_csv_rows(payload: Path, source_id: str) -> tuple[str, list[str], list[list[str]]]:
    text = _decode_text(payload.read_bytes(), source_id)
    if not text.strip():
        raise SourceContentIncomplete(source_id, "payload is empty")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";", quotechar='"')
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise SourceContentIncomplete(source_id, "payload has no non-empty rows")
    header_idx = next(
        (i for i, row in enumerate(rows) if _norm_cell(row[0]) == "Year"), None
    )
    if header_idx is None:
        raise SourceSchemaChanged(
            source_id,
            "no header row starting with 'Year' found (an HTTP error page, an "
            "empty workbook or a renamed first column all fail here); title block: "
            f"{[' '.join(r[:1]) for r in rows[:3]]}",
        )
    title_block = " ".join(" ".join(row) for row in rows[:header_idx])
    header = [_norm_cell(cell) for cell in rows[header_idx]]
    data_rows = rows[header_idx + 1 :]
    return title_block, header, data_rows


def _check_ksh_csv_header(
    source_id: str, header: list[str], expected: list[str]
) -> None:
    if len(header) != len(expected):
        raise SourceSchemaChanged(
            source_id,
            f"header has {len(header)} columns, the audited table has "
            f"{len(expected)}; header: {header}",
        )
    if len(set(header)) != len(header):
        duplicates = sorted({h for h in header if header.count(h) > 1})
        raise SourceSchemaChanged(source_id, f"duplicate header names {duplicates}")
    for got, want in zip(header, expected, strict=True):
        if got != want:
            raise SourceSchemaChanged(
                source_id, f"header column {want!r} drifted to {got!r} (full header: {header})"
            )


def _check_title(source_id: str, title: str, tokens: tuple[str, ...]) -> None:
    lowered = _norm_cell(title).lower()
    missing = [t for t in tokens if t.lower() not in lowered]
    if missing:
        raise SourceSchemaChanged(
            source_id,
            f"table title no longer contains {missing}; title: {title[:200]!r}",
        )


def _extract_ksh_csv_series(
    source_id: str,
    header: list[str],
    data_rows: list[list[str]],
    series_defs: list[tuple[str, str, str]],
    start_year: int,
    end_year: int,
) -> list[ParsedSeries]:
    column_of = {name: idx for idx, name in enumerate(header)}
    per_series: dict[str, dict[int, float]] = {var: {} for _, var, _ in series_defs}
    for row in data_rows:
        first = row[0].strip() if row else ""
        if not re.fullmatch(r"\d{4}", first):
            continue  # footnote/source rows after the numeric block
        if len(row) != len(header):
            raise SourceSchemaChanged(
                source_id,
                f"year row {first} has {len(row)} cells, header declares "
                f"{len(header)}; year-column chaos is refused",
            )
        year = int(first)
        if not (start_year <= year <= end_year):
            continue  # raw keeps future vintages; processed core is clipped explicitly
        for header_name, var, _unit in series_defs:
            if year in per_series[var]:
                raise SourceSchemaChanged(
                    source_id, f"year {year} appears twice for column {header_name!r}"
                )
            value = _parse_number(
                row[column_of[header_name]], source_id, f"{header_name!r} {year}"
            )
            if value is not None:
                per_series[var][year] = value
    out: list[ParsedSeries] = []
    for _header_name, var, unit in series_defs:
        rows = _require_complete_years(
            source_id, var, per_series[var], start_year, end_year
        )
        out.append(
            ParsedSeries(
                variable_id=var, unit=unit, frequency=Frequency.ANNUAL, rows=tuple(rows)
            )
        )
    return out


def _parse_ksh_csv(
    payload: Path,
    source_id: str,
    title_tokens: tuple[str, ...],
    expected_headers: list[str],
    series_defs: list[tuple[str, str, str]],
    start_year: int,
    end_year: int,
) -> list[ParsedSeries]:
    if start_year > end_year:
        raise ConfigError(f"inverted year window {start_year}-{end_year} for {source_id}")
    title, header, data_rows = _read_ksh_csv_rows(payload, source_id)
    _check_title(source_id, title, title_tokens)
    _check_ksh_csv_header(source_id, header, expected_headers)
    return _extract_ksh_csv_series(
        source_id, header, data_rows, series_defs, start_year, end_year
    )


_GDP_HEADERS = [
    "Year",
    "Gross domestic product (GDP),1960 = 100%",
    "Actual final consumption total,1960 = 100%",
    "Actual final consumption,of which actual final consumption of households,1960 = 100%",
    "Gross capital formation total,1960 = 100%",
    "Gross capital formation,of which fixed capital formation,1960 = 100%",
]
_GDP_SERIES = [
    ("Gross domestic product (GDP),1960 = 100%", "gdp", "index_1960_100"),
    (
        "Actual final consumption,of which actual final consumption of households,1960 = 100%",
        "consumption",
        "index_1960_100",
    ),
    (
        "Gross capital formation,of which fixed capital formation,1960 = 100%",
        "investment",
        "index_1960_100",
    ),
]

_INDUSTRY_HEADERS = [
    "Year",
    "Volume indices of production,1960=100.0%",
    "Electricity,million kWh",
    "Coal,thousand tonnes",
    "Natural gas,million m3",
    "Bauxite thousand tonnes",
    "Crude steel thousand tonnes",
    "Cement thousand tonnes",
    "Buses,pieces",
    "Television sets,thousands",
    "Sulphuric acid,technical thousand tonnes",
    "Mineral or chemical fertilizers thousand tonnes",
    "Plastics in primary form thousand tonnes",
    "Paper and card board thousand tonnes",
    "Cotton fabrics,million m2",
    "Foot-wear,thousand pairs",
    "Sugar,thousand tonnes",
    "Beer,million litres",
]
_INDUSTRY_SERIES = [
    ("Volume indices of production,1960=100.0%", "industrial_output", "index_1960_100"),
    ("Electricity,million kWh", "industrial_electricity", "million_kWh"),
    ("Crude steel thousand tonnes", "industrial_crude_steel", "thousand_tonnes"),
    (
        "Mineral or chemical fertilizers thousand tonnes",
        "industrial_fertilizer",
        "thousand_tonnes",
    ),
    ("Cement thousand tonnes", "industrial_cement", "thousand_tonnes"),
    ("Television sets,thousands", "industrial_television", "thousand_units"),
]


def parse_ksh_gdp_csv(
    payload: Path, *, start_year: int, end_year: int
) -> list[ParsedSeries]:
    """Parse KSH STADAT gdp0002.csv (GDP / household consumption / GFCF)."""
    return _parse_ksh_csv(
        payload,
        "ksh_gdp",
        ("gdp", "capital formation"),
        _GDP_HEADERS,
        _GDP_SERIES,
        start_year,
        end_year,
    )


def parse_ksh_industry_csv(
    payload: Path, *, start_year: int, end_year: int
) -> list[ParsedSeries]:
    """Parse KSH STADAT ipa0002.csv (18-column representative products)."""
    return _parse_ksh_csv(
        payload,
        "ksh_industry",
        ("volume index of industrial production",),
        _INDUSTRY_HEADERS,
        _INDUSTRY_SERIES,
        start_year,
        end_year,
    )


# ----------------------------------------------------------------------
# KSH xstadat HTML engine (h_omf001b / h_qkt001)
# ----------------------------------------------------------------------


class _Cell:
    __slots__ = ("text", "rowspan", "colspan")

    def __init__(self, text: str, rowspan: int, colspan: int) -> None:
        self.text = text
        self.rowspan = rowspan
        self.colspan = colspan


class _Table:
    def __init__(self) -> None:
        self.thead: list[list[_Cell]] = []
        self.tbody: list[list[_Cell]] = []
        self.section: list[list[_Cell]] | None = None
        self.row: list[_Cell] | None = None
        self.cell: list[str] | None = None
        self.cell_span: tuple[int, int] = (1, 1)


def _table_grid(rows: list[list[_Cell]]) -> tuple[dict[tuple[int, int], str], int]:
    """Expand rowspan/colspan into a grid; returns ``(start_cells, n_cols)``.

    ``start_cells[(row, col)]`` holds the text of the cell beginning there.
    """
    starts: dict[tuple[int, int], str] = {}
    occupied: set[tuple[int, int]] = set()
    for r, row in enumerate(rows):
        col = 0
        for cell in row:
            while (r, col) in occupied:
                col += 1
            starts[(r, col)] = cell.text
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    occupied.add((r + dr, col + dc))
    n_cols = max((c + 1) for (_, c) in occupied) if occupied else 0
    return starts, n_cols


class _KshHtmlPage(HTMLParser):
    """Collect h1 text plus every table's thead/tbody cell grid.

    Tables nested inside ``<div id="thead">`` / ``<div id="tbody">`` are
    tagged with that div id (the KSH long-table layout). Text inside
    ``<span class="idx">`` footnote markers never reaches header cells.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.tables: list[tuple[str | None, _Table]] = []
        self._div_stack: list[str | None] = []
        self._table_stack: list[_Table] = []
        self._current: _Table | None = None
        self._h1_depth = 0
        self._idx_span_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div":
            self._div_stack.append(attr.get("id"))
        elif tag == "h1":
            self._h1_depth += 1
        elif tag == "span":
            classes = (attr.get("class") or "").split()
            if "idx" in classes:
                self._idx_span_depth += 1
        elif tag == "table":
            table = _Table()
            div_id = next((d for d in reversed(self._div_stack) if d), None)
            # KSH long tables mark thead/tbody via wrapping div ids and put
            # rows directly inside <table>; explicit elements override below.
            if div_id == "thead":
                table.section = table.thead
            elif div_id == "tbody":
                table.section = table.tbody
            self._table_stack.append(table)
            self._current = table
        elif self._current is not None and tag in ("thead", "tbody"):
            self._current.section = (
                self._current.thead if tag == "thead" else self._current.tbody
            )
        elif self._current is not None and tag == "tr":
            if self._current.section is not None:
                self._current.row = []
        elif self._current is not None and tag in ("th", "td"):
            if self._current.row is not None:
                self._current.cell = []
                try:
                    rowspan = int(attr.get("rowspan") or 1)
                except ValueError:
                    rowspan = 1
                try:
                    colspan = int(attr.get("colspan") or 1)
                except ValueError:
                    colspan = 1
                self._current.cell_span = (max(rowspan, 1), max(colspan, 1))

    def handle_endtag(self, tag: str) -> None:
        if tag == "div":
            if self._div_stack:
                self._div_stack.pop()
        elif tag == "h1":
            self._h1_depth = max(0, self._h1_depth - 1)
        elif tag == "span" and self._idx_span_depth:
            self._idx_span_depth -= 1
        elif tag == "table":
            if self._table_stack:
                table = self._table_stack.pop()
                div_id = next((d for d in reversed(self._div_stack) if d), None)
                self.tables.append((div_id, table))
            self._current = self._table_stack[-1] if self._table_stack else None
        elif tag in ("thead", "tbody"):
            if self._current is not None:
                div_id = next((d for d in reversed(self._div_stack) if d), None)
                if div_id == "thead":
                    self._current.section = self._current.thead
                elif div_id == "tbody":
                    self._current.section = self._current.tbody
                else:
                    self._current.section = None
                self._current.row = None
        elif tag == "tr":
            if self._current is not None and self._current.row is not None:
                if self._current.cell is not None:  # unclosed cell
                    self._close_cell()
                assert self._current.section is not None  # rows only open inside a section
                self._current.section.append(self._current.row)
                self._current.row = None
        elif tag in ("th", "td"):
            self._close_cell()

    def _close_cell(self) -> None:
        current = self._current
        if current is None or current.row is None or current.cell is None:
            return
        rowspan, colspan = current.cell_span
        current.row.append(_Cell(_norm_cell("".join(current.cell)), rowspan, colspan))
        current.cell = None

    def handle_data(self, data: str) -> None:
        if self._idx_span_depth:
            return  # footnote marker text (the 'c' in 'Vegetables^c') is metadata
        if self._h1_depth:
            self.title += data
        elif self._current is not None and self._current.cell is not None:
            self._current.cell.append(data)



def _leaf_names(
    starts: dict[tuple[int, int], str], name_rows: int, n_cols: int
) -> list[str]:
    """Deepest-start text per column over the header rows (unit row excluded)."""
    names: list[str] = []
    for col in range(n_cols):
        candidates = [
            starts[(r, col)] for r in range(name_rows) if (r, col) in starts
        ]
        if not candidates:
            names.append("")
            continue
        leaf = candidates[-1] or (candidates[-2] if len(candidates) > 1 else "")
        names.append(leaf)
    return names


def _parse_ksh_html_table(
    payload: Path,
    source_id: str,
    title_tokens: tuple[str, ...],
    expected_leaf_names: list[str],
    expected_unit_row: str,
    series_defs: list[tuple[int, str, str]],
    start_year: int,
    end_year: int,
) -> list[ParsedSeries]:
    page = _KshHtmlPage()
    try:
        page.feed(_decode_text(payload.read_bytes(), source_id))
    except SourceSchemaChanged:
        raise
    except Exception as exc:  # malformed markup is drift, never a guess
        raise SourceSchemaChanged(source_id, f"unparseable HTML: {exc}") from exc
    _check_title(source_id, page.title, title_tokens)

    thead_tables = [t for div, t in page.tables if div == "thead"]
    tbody_tables = [t for div, t in page.tables if div == "tbody"]
    if len(thead_tables) != 1 or len(tbody_tables) != 1:
        raise SourceSchemaChanged(
            source_id,
            f"expected exactly one table inside div#thead and one inside div#tbody, "
            f"found {len(thead_tables)}/{len(tbody_tables)}; navigation/footnote "
            "tables are not substitutes for the audited long table",
        )
    thead, tbody = thead_tables[0].thead, tbody_tables[0].tbody
    if not thead or not tbody:
        raise SourceSchemaChanged(source_id, "thead/tbody table has no rows")
    if len(thead) < 2:
        raise SourceSchemaChanged(
            source_id,
            f"thead has {len(thead)} rows; the audited layout needs name rows plus "
            "a unit row",
        )

    starts, n_cols = _table_grid(thead)
    if n_cols != len(expected_leaf_names):
        raise SourceSchemaChanged(
            source_id,
            f"thead expands to {n_cols} columns, audited table has "
            f"{len(expected_leaf_names)} (leaf names: {expected_leaf_names})",
        )
    unit_row_cells = [c for row in thead[-1:] for c in row]
    data_cols = n_cols - 1
    if (
        len(unit_row_cells) != 1
        or unit_row_cells[0].rowspan != 1
        or unit_row_cells[0].colspan != data_cols
        or _norm_cell(unit_row_cells[0].text).lower() != expected_unit_row.lower()
    ):
        raise SourceSchemaChanged(
            source_id,
            f"unit row must be a single cell spanning all {data_cols} data columns "
            f"reading {expected_unit_row!r}; got {[c.text for c in unit_row_cells]}",
        )
    names = _leaf_names(starts, len(thead) - 1, n_cols)
    for got, want in zip(names, expected_leaf_names, strict=True):
        if got.strip().lower() != want.strip().lower():
            raise SourceSchemaChanged(
                source_id,
                f"header column {want!r} drifted to {got!r} (leaf names: {names})",
            )

    per_series: dict[str, dict[int, float]] = {var: {} for _, var, _ in series_defs}
    for row in tbody:
        cells = [c for c in row]
        if not cells:
            continue
        first = cells[0].text.strip()
        if not re.fullmatch(r"\d{4}", first):
            raise SourceSchemaChanged(
                source_id, f"tbody row does not start with a year: {[c.text for c in cells][:4]}"
            )
        if len(cells) != n_cols:
            raise SourceSchemaChanged(
                source_id,
                f"tbody year row {first} has {len(cells)} cells, thead declares {n_cols}",
            )
        year = int(first)
        if not (start_year <= year <= end_year):
            continue
        if any(year in per_series[var] for _, var, _ in series_defs):
            raise SourceSchemaChanged(source_id, f"year {year} appears twice in tbody")
        for col, var, _unit in series_defs:
            value = _parse_number(cells[col].text, source_id, f"column {names[col]!r} {year}")
            if value is not None:
                per_series[var][year] = value
    out: list[ParsedSeries] = []
    for _col, var, unit in series_defs:
        rows = _require_complete_years(source_id, var, per_series[var], start_year, end_year)
        out.append(
            ParsedSeries(variable_id=var, unit=unit, frequency=Frequency.ANNUAL, rows=tuple(rows))
        )
    return out


_AGRI_LEAF_NAMES = [
    "Year",
    "Cereals",
    "wheat",
    "maize",
    "Sugarbeet",
    "Oilseeds",
    "Potatoes",
    "Vegetables",
    "Fruits",
    "Grapes",
]
_AGRI_SERIES = [
    (1, "ag_cereals", "thousand_tonnes"),
    (2, "ag_wheat", "thousand_tonnes"),
    (3, "ag_maize", "thousand_tonnes"),
]

_TRADE_LEAF_NAMES = ["Year", "imports", "exports"]
_TRADE_SERIES = [
    (1, "trade_import_volume_index", "index_1960_100"),
    (2, "trade_export_volume_index", "index_1960_100"),
]


def parse_ksh_agriculture_html(
    payload: Path, *, start_year: int, end_year: int
) -> list[ParsedSeries]:
    """Parse KSH xstadat h_omf001b.html (div#thead + div#tbody tables)."""
    return _parse_ksh_html_table(
        payload,
        "ksh_agriculture_b",
        ("major data of agriculture",),
        _AGRI_LEAF_NAMES,
        "thousand tons",
        _AGRI_SERIES,
        start_year,
        end_year,
    )


def parse_ksh_trade_html(
    payload: Path, *, start_year: int, end_year: int
) -> list[ParsedSeries]:
    """Parse KSH xstadat h_qkt001.html (volume indices of external trade)."""
    return _parse_ksh_html_table(
        payload,
        "ksh_trade",
        ("external trade in goods",),
        _TRADE_LEAF_NAMES,
        "1960 = 100%",
        _TRADE_SERIES,
        start_year,
        end_year,
    )


# ----------------------------------------------------------------------
# World Bank Pink Sheet monthly workbook
# ----------------------------------------------------------------------

_WB_SHEET = "Monthly Prices"
_WB_HEADER_ROW_SCAN = 12
_WB_CRUDE_HEADER = "Crude oil, average"
_WB_CRUDE_UNIT = "($/bbl)"
_WB_PERIOD_RE = re.compile(r"^(\d{4})M(0[1-9]|1[0-2])$")


def parse_worldbank_pink_sheet_xlsx(
    payload: Path, *, start_month: str, end_month: str
) -> list[ParsedSeries]:
    """Parse CMO-Historical-Data-Monthly.xlsx 'Monthly Prices' crude oil."""
    import openpyxl  # type: ignore[import-untyped]  # no stubs published for openpyxl 3.x

    try:
        workbook = openpyxl.load_workbook(payload, read_only=True, data_only=True)
    except Exception as exc:
        raise SourceSchemaChanged(
            "worldbank_pink_sheet", f"workbook is not readable XLSX: {exc}"
        ) from exc
    try:
        if _WB_SHEET not in workbook.sheetnames:
            raise SourceSchemaChanged(
                "worldbank_pink_sheet",
                f"sheet {_WB_SHEET!r} missing; sheets: {workbook.sheetnames}",
            )
        sheet = workbook[_WB_SHEET]
        header_cells: list[tuple[int, int]] = []
        unit_cells: dict[int, str] = {}
        periods: dict[str, float] = {}
        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=1, max_row=_WB_HEADER_ROW_SCAN + 1, values_only=True),
            start=1,
        ):
            for col_idx, value in enumerate(row, start=1):
                if isinstance(value, str) and value.strip() == _WB_CRUDE_HEADER:
                    header_cells.append((row_idx, col_idx))
                    unit_cells[col_idx] = "__pending__"
        if not header_cells:
            raise SourceSchemaChanged(
                "worldbank_pink_sheet",
                f"no cell equals {_WB_CRUDE_HEADER!r} in the first {_WB_HEADER_ROW_SCAN} rows",
            )
        if len(header_cells) > 1:
            raise SourceSchemaChanged(
                "worldbank_pink_sheet",
                f"{_WB_CRUDE_HEADER!r} header is not unique: {header_cells}",
            )
        header_row, crude_col = header_cells[0]
        # Unit row sits directly under the commodity header and is validated
        # before any numeric is read.
        for row in sheet.iter_rows(
            min_row=header_row + 1, max_row=header_row + 1, values_only=True
        ):
            unit_value = row[crude_col - 1] if len(row) >= crude_col else None
            if not isinstance(unit_value, str) or unit_value.strip() != _WB_CRUDE_UNIT:
                raise SourceSchemaChanged(
                    "worldbank_pink_sheet",
                    f"unit row under {_WB_CRUDE_HEADER!r} must read {_WB_CRUDE_UNIT!r}, "
                    f"got {unit_value!r}",
                )
        for row in sheet.iter_rows(min_row=header_row + 2, values_only=True):
            period = row[0]
            if not isinstance(period, str) or not _WB_PERIOD_RE.match(period.strip()):
                continue
            normalized = f"{period[:4]}-{period[5:7]}"
            value = row[crude_col - 1] if len(row) >= crude_col else None
            if isinstance(value, (int, float)):
                periods[normalized] = float(value)
            elif value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            else:
                raise SourceSchemaChanged(
                    "worldbank_pink_sheet",
                    f"unparseable crude oil cell {value!r} at period {period!r}",
                )
    finally:
        workbook.close()
    rows = _require_complete_months(
        "worldbank_pink_sheet", "world_oil_price", periods, start_month, end_month
    )
    return [
        ParsedSeries(
            variable_id="world_oil_price",
            unit="USD_per_barrel",
            frequency=Frequency.MONTHLY,
            rows=tuple(rows),
        )
    ]


# ----------------------------------------------------------------------
# Federal Reserve H.15 XML archive
# ----------------------------------------------------------------------

_FED_MEMBER = "H15_data.xml"
_FED_MAX_MEMBER_BYTES = 128 * 1024 * 1024
_FED_HEAD_SCAN = 8192
_FED_SERIES_ATTRS = {
    "SERIES_NAME": "RIFSPFF_N.M",
    "INSTRUMENT": "FF",
    "FREQ": "129",
    "UNIT": "Percent:_Per_Year",
    "UNIT_MULT": "1",
}
_FED_OBS_PERIOD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_fed_h15_zip(
    payload: Path, *, start_month: str, end_month: str
) -> list[ParsedSeries]:
    """Parse FRB_h15_xml.zip member H15_data.xml (RIFSPFF_N.M monthly)."""
    import xml.etree.ElementTree as ET

    try:
        archive = zipfile.ZipFile(payload)
    except zipfile.BadZipFile as exc:
        raise SourceSchemaChanged(
            "federalreserve_h15", f"payload is not a valid ZIP archive: {exc}"
        ) from exc
    with archive:
        members = [n for n in archive.namelist() if n == _FED_MEMBER]
        if len(members) != 1:
            raise SourceSchemaChanged(
                "federalreserve_h15",
                f"archive member {_FED_MEMBER!r} must appear exactly once, "
                f"found {len(members)}; members: {archive.namelist()}",
            )
        info = archive.getinfo(_FED_MEMBER)
        if info.file_size > _FED_MAX_MEMBER_BYTES:
            raise SourceSchemaChanged(
                "federalreserve_h15",
                f"member {_FED_MEMBER!r} is {info.file_size} bytes uncompressed, "
                f"above the {_FED_MAX_MEMBER_BYTES} member cap",
            )
        # Reject DTD/entity declarations before any XML is interpreted.
        with archive.open(_FED_MEMBER) as head:
            head_bytes = head.read(_FED_HEAD_SCAN)
        if b"<!DOCTYPE" in head_bytes or b"<!ENTITY" in head_bytes:
            raise SourceSchemaChanged(
                "federalreserve_h15",
                "XML member declares a DTD/entities; DOCTYPE payloads are refused "
                "before parsing",
            )
        if not head_bytes.lstrip().startswith(b"<?xml"):
            raise SourceSchemaChanged(
                "federalreserve_h15", "XML member does not start with an XML declaration"
            )
        selected_count = 0
        in_selected = False
        current_attrs: dict[str, str] = {}
        periods: dict[str, float] = {}

        def localname(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        for event, elem in ET.iterparse(archive.open(_FED_MEMBER), events=("start", "end")):
            name = localname(elem.tag)
            if event == "start":
                if name == "Series":
                    current_attrs = dict(elem.attrib)
                    if all(current_attrs.get(k) == v for k, v in _FED_SERIES_ATTRS.items()):
                        in_selected = True
                        selected_count += 1
            else:
                if name == "Obs" and in_selected:
                    attrs = elem.attrib
                    period = attrs.get("TIME_PERIOD", "")
                    if not _FED_OBS_PERIOD_RE.match(period):
                        raise SourceSchemaChanged(
                            "federalreserve_h15",
                            f"Obs TIME_PERIOD {period!r} is not an end-of-month "
                            "YYYY-MM-DD date",
                        )
                    if not attrs.get("OBS_STATUS"):
                        raise SourceSchemaChanged(
                            "federalreserve_h15",
                            f"Obs {period!r} has no OBS_STATUS",
                        )
                    raw = attrs.get("OBS_VALUE", "")
                    value = _parse_number(
                        raw, "federalreserve_h15", f"Obs {period!r}"
                    )
                    if value is not None:
                        month = period[:7]
                        if month in periods:
                            raise SourceSchemaChanged(
                                "federalreserve_h15",
                                f"month {month} appears twice in the selected series",
                            )
                        periods[month] = value
                elif name == "Series":
                    in_selected = False
                    elem.clear()  # non-selected series are dropped immediately
        if selected_count != 1:
            raise SourceSchemaChanged(
                "federalreserve_h15",
                f"expected exactly one Series with {_FED_SERIES_ATTRS}, found "
                f"{selected_count}",
            )
    rows = _require_complete_months(
        "federalreserve_h15", "global_usd_rate", periods, start_month, end_month
    )
    return [
        ParsedSeries(
            variable_id="global_usd_rate",
            unit="percent_per_year",
            frequency=Frequency.MONTHLY,
            rows=tuple(rows),
        )
    ]


# ----------------------------------------------------------------------
# MNB official exchange-rate query page
# ----------------------------------------------------------------------

_MNB_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MNB_DATE_RE = re.compile(r"^(\d{1,2}) ([A-Za-z]+) (\d{4})$")
_MNB_SOURCE = "mnb_official_fx"


def _parse_mnb_date(text: str, source_id: str) -> date:
    match = _MNB_DATE_RE.match(text)
    if not match:
        raise SourceSchemaChanged(source_id, f"unparseable quote date {text!r}")
    day, month_name, year = match.groups()
    month = _MNB_MONTHS.get(month_name.lower())
    if month is None:
        raise SourceSchemaChanged(source_id, f"unknown month name in date {text!r}")
    try:
        return date(int(year), month, int(day))
    except ValueError as exc:
        raise SourceSchemaChanged(source_id, f"invalid calendar date {text!r}: {exc}") from exc


def parse_mnb_fx_html(
    payload: Path, *, start_date: str, end_date: str
) -> list[ParsedSeries]:
    """Parse the MNB arfolyam-tablazat USD daily quote table.

    The three-line thead must read exactly USD / US Dollar / 1; the page is
    already normalized to HUF per 1 USD, so values are never divided (or
    multiplied) by 100. Dates without a quote stay absent - a missing date is
    never zero.
    """
    page = _KshHtmlPage()
    try:
        page.feed(_decode_text(payload.read_bytes(), _MNB_SOURCE))
    except SourceSchemaChanged:
        raise
    except Exception as exc:
        raise SourceSchemaChanged(_MNB_SOURCE, f"unparseable HTML: {exc}") from exc
    quotes: dict[str, float] = {}
    matched_table = False
    for _div, table in page.tables:
        thead_texts = [c.text.strip() for row in table.thead for c in row if c.text.strip()]
        if thead_texts != ["USD", "US Dollar", "1"] or len(table.thead) != 3:
            continue
        matched_table = True
        for row in table.tbody:
            nonempty = [c for c in row if c.text.strip()]
            if not nonempty:
                continue
            if len(nonempty) != 2:
                raise SourceSchemaChanged(
                    _MNB_SOURCE,
                    f"quote row must have exactly a date and a value, got "
                    f"{[c.text for c in row]}",
                )
            quote_date = _parse_mnb_date(nonempty[0].text, _MNB_SOURCE)
            value = _parse_number(nonempty[1].text, _MNB_SOURCE, f"quote {quote_date}")
            if value is None:
                raise SourceSchemaChanged(
                    _MNB_SOURCE, f"quote for {quote_date} has a missing marker"
                )
            period = quote_date.isoformat()
            if not (start_date <= period <= end_date):
                continue
            if period in quotes:
                raise SourceSchemaChanged(_MNB_SOURCE, f"date {period} appears twice")
            quotes[period] = value
        break
    if not matched_table:
        raise SourceSchemaChanged(
            _MNB_SOURCE,
            "no table with the audited three-line thead USD / US Dollar / 1; the "
            "currency, unit or page layout drifted",
        )
    if not quotes:
        raise SourceContentIncomplete(
            _MNB_SOURCE,
            f"no USD quotes inside {start_date}..{end_date}; an empty result page is "
            "reported as missing data, never as zeros",
        )
    rows = tuple(sorted(quotes.items()))
    return [
        ParsedSeries(
            variable_id="official_fx",
            unit="HUF_per_USD",
            frequency=Frequency.DATED,
            rows=rows,
        )
    ]


# ----------------------------------------------------------------------
# FRED CSV (rights-gated; parser exercised via synthetic fixtures only)
# ----------------------------------------------------------------------

_FRED_SOURCE = "fred_fedfunds"
_FRED_HEADER = ["observation_date", "FEDFUNDS"]
_FRED_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_fred_fedfunds_csv(
    payload: Path, *, start_month: str, end_month: str
) -> list[ParsedSeries]:
    """Parse an authorized fredgraph.csv FEDFUNDS response (monthly percent).

    This adapter exists so the gated FRED path stays testable end-to-end; the
    rights gate in ingestion.py still blocks any download or cache read while
    fred_fedfunds carries download_allowed != True.
    """
    text = _decode_text(payload.read_bytes(), _FRED_SOURCE)
    if not text.strip():
        raise SourceContentIncomplete(_FRED_SOURCE, "payload is empty")
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    header = [_norm_cell(cell) for cell in rows[0]]
    if header != _FRED_HEADER:
        raise SourceSchemaChanged(
            _FRED_SOURCE, f"header must be {_FRED_HEADER}, got {header}"
        )
    periods: dict[str, float] = {}
    for row in rows[1:]:
        if len(row) != 2:
            raise SourceSchemaChanged(
                _FRED_SOURCE, f"row must have exactly 2 cells, got {row}"
            )
        day = row[0].strip()
        if not _FRED_DATE_RE.match(day):
            raise SourceSchemaChanged(_FRED_SOURCE, f"observation_date {day!r} is not a date")
        month = day[:7]
        value = _parse_number(row[1], _FRED_SOURCE, f"observation {day}")
        if value is not None:
            if month in periods:
                raise SourceSchemaChanged(_FRED_SOURCE, f"month {month} appears twice")
            periods[month] = value
    rows_out = _require_complete_months(
        _FRED_SOURCE, "global_usd_rate", periods, start_month, end_month
    )
    return [
        ParsedSeries(
            variable_id="global_usd_rate",
            unit="percent_per_year",
            frequency=Frequency.MONTHLY,
            rows=tuple(rows_out),
        )
    ]
