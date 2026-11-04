"""Parse a Google Search Console "Performance on Search" export.

The UI export is a zip (or folder) of separate aggregate tables:
Chart.csv (daily), Pages.csv, Queries.csv, Devices.csv, Countries.csv,
Filters.csv, Search appearance.csv.

Constraints worth knowing (these shape what the scorer can claim):
- Each table is aggregated independently. There is NO query x page join,
  so query-to-page mapping from a CSV is inferred, never observed.
- Queries.csv omits anonymised queries, so its impression total is lower
  than Chart.csv. Pages.csv is aggregated by page, so its total can be
  slightly higher than Chart.csv (by-property aggregation).
- The UI caps each table at 1,000 rows.
- Position is an impression-weighted average.
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Header names vary by UI language/version. Map first column to a role.
FIRST_COL = {
    "top pages": "pages", "page": "pages", "pages": "pages",
    "top queries": "queries", "query": "queries", "queries": "queries",
    "date": "chart",
    "device": "devices",
    "country": "countries",
    "filter": "filters",
    "search appearance": "appearance",
}


class GSCParseError(ValueError):
    pass


def _num(v: str) -> float:
    v = (v or "").strip().replace(",", "")
    if v in ("", "-"):
        return 0.0
    if v.endswith("%"):
        return float(v[:-1]) / 100.0
    return float(v)


@dataclass
class Row:
    key: str
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass
class GSCExport:
    pages: list[Row] = field(default_factory=list)
    queries: list[Row] = field(default_factory=list)
    chart: list[Row] = field(default_factory=list)  # key = YYYY-MM-DD
    devices: list[Row] = field(default_factory=list)
    countries: list[Row] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    content_hash: str = ""

    @property
    def date_start(self) -> str | None:
        return min((r.key for r in self.chart), default=None)

    @property
    def date_end(self) -> str | None:
        return max((r.key for r in self.chart), default=None)

    def totals(self) -> dict:
        src = self.chart or self.pages
        c = sum(r.clicks for r in src)
        i = sum(r.impressions for r in src)
        return {"clicks": c, "impressions": i, "ctr": (c / i) if i else 0.0,
                "pages": len(self.pages), "queries": len(self.queries)}


def _parse_table(text: str, name: str) -> tuple[str, list[list[str]]]:
    text = text.lstrip("﻿")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return "empty", []
    role = FIRST_COL.get(rows[0][0].strip().lower())
    if role is None:
        raise GSCParseError(f"{name}: unrecognised header {rows[0]!r}")
    return role, rows


def _to_rows(rows: list[list[str]], name: str) -> list[Row]:
    header = [h.strip().lower() for h in rows[0]]
    need = ["clicks", "impressions", "ctr", "position"]
    try:
        idx = [header.index(n) for n in need]
    except ValueError as e:
        raise GSCParseError(f"{name}: missing metric column ({e})") from None
    out = []
    for n, r in enumerate(rows[1:], start=2):
        try:
            out.append(Row(" ".join(r[0].split()), int(_num(r[idx[0]])), int(_num(r[idx[1]])),
                           _num(r[idx[2]]), _num(r[idx[3]])))
        except (IndexError, ValueError) as e:
            raise GSCParseError(f"{name} line {n}: {e}") from None
    return out


def _read_sources(path: Path) -> dict[str, str]:
    if path.is_dir():
        return {p.name: p.read_text(encoding="utf-8-sig") for p in path.glob("*.csv")}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            return {Path(n).name: z.read(n).decode("utf-8-sig")
                    for n in z.namelist() if n.lower().endswith(".csv")}
    if path.suffix.lower() == ".csv":
        return {path.name: path.read_text(encoding="utf-8-sig")}
    raise GSCParseError(f"{path}: expected a .zip, a folder or a .csv")


def load_export(path: str | Path) -> GSCExport:
    path = Path(path)
    sources = _read_sources(path)
    if not sources:
        raise GSCParseError(f"{path}: no CSV files found")
    exp = GSCExport()
    h = hashlib.sha256()
    for name in sorted(sources):
        text = sources[name]
        h.update(name.encode()); h.update(text.encode())
        role, rows = _parse_table(text, name)
        if role in ("empty", "appearance"):
            continue
        if role == "filters":
            exp.filters = {r[0].strip(): r[1].strip() for r in rows[1:] if len(r) > 1}
            continue
        setattr(exp, role, _to_rows(rows, name))
    if not exp.pages and not exp.queries:
        raise GSCParseError(f"{path}: no Pages or Queries table found")
    exp.content_hash = h.hexdigest()
    return exp
