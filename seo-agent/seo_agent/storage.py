"""SQLite storage. One file, no server. Imports are idempotent by content hash."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .gsc_csv import GSCExport

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,            -- 'csv' or 'api'
  content_hash TEXT NOT NULL UNIQUE,
  date_start TEXT, date_end TEXT,
  filters TEXT,
  imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gsc_aggregate (
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL,         -- page | query | date | device | country
  key TEXT NOT NULL,
  clicks INTEGER NOT NULL, impressions INTEGER NOT NULL,
  ctr REAL NOT NULL, position REAL NOT NULL,
  PRIMARY KEY (import_id, dimension, key)
);
-- Row-level API data (date x page x query x device x country). Filled by the
-- API ingester; the CSV path cannot populate it.
CREATE TABLE IF NOT EXISTS gsc_rows (
  date TEXT NOT NULL, page TEXT NOT NULL, query TEXT NOT NULL,
  device TEXT NOT NULL, country TEXT NOT NULL,
  clicks INTEGER NOT NULL, impressions INTEGER NOT NULL,
  ctr REAL NOT NULL, position REAL NOT NULL,
  PRIMARY KEY (date, page, query, device, country)
);
CREATE TABLE IF NOT EXISTS opportunity_scores (
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  page TEXT NOT NULL, score REAL NOT NULL,
  components TEXT NOT NULL, reasons TEXT NOT NULL,
  scored_at TEXT NOT NULL,
  PRIMARY KEY (import_id, page)
);
"""

DIMS = {"pages": "page", "queries": "query", "chart": "date",
        "devices": "device", "countries": "country"}


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_export(con: sqlite3.Connection, exp: GSCExport) -> tuple[int, bool]:
    """Returns (import_id, created). Re-importing the same export is a no-op."""
    row = con.execute("SELECT id FROM imports WHERE content_hash=?",
                      (exp.content_hash,)).fetchone()
    if row:
        return row["id"], False
    with con:
        cur = con.execute(
            "INSERT INTO imports(source, content_hash, date_start, date_end, filters, imported_at)"
            " VALUES ('csv',?,?,?,?,?)",
            (exp.content_hash, exp.date_start, exp.date_end, json.dumps(exp.filters), _now()))
        iid = cur.lastrowid
        for attr, dim in DIMS.items():
            con.executemany(
                "INSERT INTO gsc_aggregate VALUES (?,?,?,?,?,?,?)",
                [(iid, dim, r.key, r.clicks, r.impressions, r.ctr, r.position)
                 for r in getattr(exp, attr)])
    return iid, True


def latest_import(con: sqlite3.Connection) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM imports ORDER BY date_end DESC, id DESC LIMIT 1").fetchone()


def aggregate(con, import_id: int, dimension: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM gsc_aggregate WHERE import_id=? AND dimension=? ORDER BY impressions DESC",
        (import_id, dimension)).fetchall()


def save_scores(con, import_id: int, scores: list) -> None:
    with con:
        con.execute("DELETE FROM opportunity_scores WHERE import_id=?", (import_id,))
        con.executemany(
            "INSERT INTO opportunity_scores VALUES (?,?,?,?,?,?)",
            [(import_id, s.page, s.score, json.dumps(s.components), json.dumps(s.reasons), _now())
             for s in scores])
