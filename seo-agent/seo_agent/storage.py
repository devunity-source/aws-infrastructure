"""SQLite storage. One file, no server. Imports are idempotent by content hash."""
from __future__ import annotations

import hashlib
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
-- Complete page totals from the API, grouped by date and page only, so anonymised traffic
-- is included. device and country are stored as '' (kept in the key for older databases).
CREATE TABLE IF NOT EXISTS gsc_page_rows (
  date TEXT NOT NULL, page TEXT NOT NULL,
  device TEXT NOT NULL, country TEXT NOT NULL,
  clicks INTEGER NOT NULL, impressions INTEGER NOT NULL,
  ctr REAL NOT NULL, position REAL NOT NULL,
  PRIMARY KEY (date, page, device, country)
);
-- One row per fetched day, so fetches are incremental. A day with no data is still logged.
CREATE TABLE IF NOT EXISTS api_fetches (
  site TEXT NOT NULL, date TEXT NOT NULL,
  rows INTEGER NOT NULL, page_rows INTEGER NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (site, date)
);
-- GA4 affiliate_click events per property, day, page and product. product and asin are '' when
-- GA4 has no custom dimensions for them, or the click predates them. Several properties can be
-- stored (the blog moved to its own GA4 property), and each fetch only replaces its own rows.
CREATE TABLE IF NOT EXISTS ga4_clicks (
  property TEXT NOT NULL,
  date TEXT NOT NULL, page_path TEXT NOT NULL,
  product TEXT NOT NULL, asin TEXT NOT NULL,
  clicks INTEGER NOT NULL,
  PRIMARY KEY (property, date, page_path, product, asin)
);
CREATE TABLE IF NOT EXISTS ga4_fetches (
  id INTEGER PRIMARY KEY,
  property TEXT NOT NULL, date_start TEXT NOT NULL, date_end TEXT NOT NULL,
  rows INTEGER NOT NULL, by_product INTEGER NOT NULL,
  fetched_at TEXT NOT NULL
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


def connect(path: str | Path, legacy_urls: dict | None = None) -> sqlite3.Connection:
    """Open the database. canon(page) is available in SQL: it rewrites a moved article's old
    URL to its new one (config legacy_urls), so old and new URLs group as one page."""
    from .config import DEFAULTS
    legacy = list((DEFAULTS["legacy_urls"] if legacy_urls is None else legacy_urls).items())

    def canon(page):
        if page is None:
            return None
        for old, new in legacy:
            if page.startswith(old):
                page = new + page[len(old):]
                return page[:-5] if page.endswith(".html") else page
        return page

    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.create_function("canon", 1, canon, deterministic=True)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    _migrate_ga4_clicks(con)
    return con


def _migrate_ga4_clicks(con) -> None:
    """Databases from v0.5 have ga4_clicks without a property column. Their rows all came from
    one property, the one in ga4_fetches, so they are copied across with it."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(ga4_clicks)")]
    if "property" in cols:
        return
    row = con.execute("SELECT property FROM ga4_fetches ORDER BY id DESC LIMIT 1").fetchone()
    prop = row[0] if row else ""
    with con:
        con.execute("ALTER TABLE ga4_clicks RENAME TO ga4_clicks_v05")
        con.executescript(SCHEMA)  # creates the new ga4_clicks
        con.execute("INSERT INTO ga4_clicks SELECT ?, date, page_path, product, asin, clicks FROM ga4_clicks_v05",
                    (prop,))
        con.execute("DROP TABLE ga4_clicks_v05")


def site_page_filter(site: str) -> tuple[str, list[str]]:
    """SQL condition and params matching the page URLs a Search Console property covers:
    a URL-prefix property ('https://x.com/') or a domain property ('sc-domain:x.com')."""
    if site.startswith("sc-domain:"):
        d = site[len("sc-domain:"):]
        pats = [f"http://{d}/%", f"https://{d}/%", f"http://%.{d}/%", f"https://%.{d}/%"]
    else:
        pats = [site if site.endswith("/") else site + "/"]
        pats = [pats[0] + "%"]
    return "(" + " OR ".join(["page LIKE ?"] * len(pats)) + ")", pats


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


def latest_import(con: sqlite3.Connection, days: int | None = None) -> sqlite3.Row | None:
    """Most recent import. With days, only imports covering exactly that many days count,
    so a 28-day and a 90-day window ending the same day can't be mixed up."""
    if days:
        return con.execute(
            "SELECT * FROM imports WHERE julianday(date_end) - julianday(date_start) = ? "
            "ORDER BY date_end DESC, id DESC LIMIT 1", (days - 1,)).fetchone()
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


# ---------- API data ----------

def save_api_day(con, site: str, day: str, rows: list[dict], page_rows: list[dict]) -> None:
    """Replace one day's API data for this property. Rerunning a day is safe, and other
    properties' rows for the same day are left alone."""
    cond, pats = site_page_filter(site)
    with con:
        con.execute(f"DELETE FROM gsc_rows WHERE date=? AND {cond}", (day, *pats))
        con.execute(f"DELETE FROM gsc_page_rows WHERE date=? AND {cond}", (day, *pats))
        con.executemany(
            "INSERT INTO gsc_rows VALUES (?,?,?,?,?,?,?,?,?)",
            [(day, r["page"], r["query"], r["device"], r["country"],
              r["clicks"], r["impressions"], r["ctr"], r["position"]) for r in rows])
        con.executemany(
            "INSERT INTO gsc_page_rows VALUES (?,?,?,?,?,?,?,?)",
            [(day, r["page"], r.get("device", ""), r.get("country", ""),
              r["clicks"], r["impressions"], r["ctr"], r["position"]) for r in page_rows])
        con.execute("INSERT OR REPLACE INTO api_fetches VALUES (?,?,?,?,?)",
                    (site, day, len(rows), len(page_rows), _now()))


def save_ga4_range(con, prop: str, start: str, end: str, rows: list[dict], by_product: bool) -> None:
    """Replace this property's stored clicks in [start, end]. GA4 keeps processing recent days,
    so each run fetches the whole range again. Other properties' rows are left alone."""
    totals: dict[tuple, int] = {}
    for r in rows:
        k = (r["date"], r["page_path"], r["product"], r["asin"])
        totals[k] = totals.get(k, 0) + r["clicks"]
    with con:
        con.execute("DELETE FROM ga4_clicks WHERE property=? AND date BETWEEN ? AND ?", (prop, start, end))
        con.executemany("INSERT INTO ga4_clicks VALUES (?,?,?,?,?,?)", [(prop, *k, n) for k, n in totals.items()])
        con.execute("INSERT INTO ga4_fetches (property, date_start, date_end, rows, by_product, fetched_at) "
                    "VALUES (?,?,?,?,?,?)", (prop, start, end, len(rows), int(by_product), _now()))


def fetch_log(con, site: str) -> dict[str, int]:
    """date -> page rows stored for it, for every day already fetched."""
    return {r["date"]: r["page_rows"] for r in
            con.execute("SELECT date, page_rows FROM api_fetches WHERE site=?", (site,))}


def api_sites(con) -> list[str]:
    return [r["site"] for r in con.execute("SELECT DISTINCT site FROM api_fetches ORDER BY site")]


def api_date_range(con) -> tuple[str | None, str | None]:
    r = con.execute("SELECT MIN(date) AS lo, MAX(date) AS hi FROM api_fetches").fetchone()
    return r["lo"], r["hi"]


# SUM(position * impressions) / SUM(impressions) is the impression-weighted average
# position, the same way Search Console reports it.
_AGG = ("SUM(clicks) AS clicks, SUM(impressions) AS impressions, "
        "CASE WHEN SUM(impressions) > 0 THEN 1.0 * SUM(clicks) / SUM(impressions) ELSE 0 END AS ctr, "
        "CASE WHEN SUM(impressions) > 0 THEN SUM(position * impressions) / SUM(impressions) ELSE 0 END AS position")


def _window_aggregates(con, start: str, end: str) -> dict[str, list[tuple]]:
    q = lambda table, key: [tuple(r) for r in con.execute(
        f"SELECT {key} AS key, {_AGG} FROM {table} WHERE date BETWEEN ? AND ? "
        f"GROUP BY {key} HAVING SUM(impressions) > 0 ORDER BY key", (start, end))]
    # No device or country totals: complete ones would need the page fetch split by
    # them, which makes Google drop rows (see gsc_api.PAGE_DIMS).
    return {"page": q("gsc_page_rows", "canon(page)"), "query": q("gsc_rows", "query"),
            "date": q("gsc_page_rows", "date")}


def build_window_import(con, site: str, start: str, end: str) -> tuple[int, bool, dict]:
    """Aggregate stored API rows for [start, end] into an import the scorer reads.
    Same data gives the same content hash, so rebuilding a window is a no-op."""
    aggs = _window_aggregates(con, start, end)
    h = hashlib.sha256(json.dumps({"site": site, "start": start, "end": end, "aggs": aggs},
                                  sort_keys=True).encode()).hexdigest()
    pages = aggs["page"]
    totals = {"clicks": sum(r[1] for r in pages), "impressions": sum(r[2] for r in pages),
              "pages": len(pages), "queries": len(aggs["query"])}
    row = con.execute("SELECT id FROM imports WHERE content_hash=?", (h,)).fetchone()
    if row:
        return row["id"], False, totals
    with con:
        cur = con.execute(
            "INSERT INTO imports(source, content_hash, date_start, date_end, filters, imported_at)"
            " VALUES ('api',?,?,?,?,?)",
            (h, start, end, json.dumps({"site": site}), _now()))
        iid = cur.lastrowid
        for dim, rows in aggs.items():
            con.executemany("INSERT INTO gsc_aggregate VALUES (?,?,?,?,?,?,?)",
                            [(iid, dim, *r) for r in rows])
    return iid, True, totals


def observed_query_pages(con, start: str, end: str) -> dict[str, list[dict]]:
    """page -> its queries, observed from the API join (not inferred from wording)."""
    out: dict[str, list[dict]] = {}
    for r in con.execute(
            f"SELECT canon(page) AS page, query AS key, {_AGG} FROM gsc_rows WHERE date BETWEEN ? AND ? "
            "GROUP BY canon(page), query HAVING SUM(impressions) > 0", (start, end)):
        out.setdefault(r["page"], []).append(
            dict(key=r["key"], clicks=r["clicks"], impressions=r["impressions"],
                 ctr=r["ctr"], position=r["position"]))
    return out
