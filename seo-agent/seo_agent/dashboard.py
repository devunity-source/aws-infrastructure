"""Static SEO dashboard: one self-contained HTML file built from the database.

No server code and no external requests. Data is embedded as JSON and rendered in the
browser, so the page can be served by plain nginx behind a password. Every string from
Search Console (queries are typed by strangers) is escaped when rendered.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timezone
from importlib import resources
from pathlib import Path

from .scoring import slug_of

WEEKS_PAGE = """
SELECT date(date, 'weekday 0', '-6 days') AS week, page,
       SUM(clicks) AS clicks, SUM(impressions) AS impressions,
       CASE WHEN SUM(impressions) > 0 THEN SUM(position * impressions) / SUM(impressions) END AS position
FROM gsc_page_rows GROUP BY week, page ORDER BY week
"""
WEEK_DAYS = """
SELECT date(date, 'weekday 0', '-6 days') AS week, COUNT(DISTINCT date) AS days
FROM api_fetches GROUP BY week
"""


def _totals(con, start: str, end: str) -> dict:
    r = con.execute("SELECT SUM(clicks), SUM(impressions), SUM(position * impressions) "
                    "FROM gsc_page_rows WHERE date BETWEEN ? AND ?", (start, end)).fetchone()
    clicks, imp, pos_w = (r[0] or 0), (r[1] or 0), (r[2] or 0)
    return {"start": start, "end": end, "clicks": clicks, "impressions": imp,
            "ctr": clicks / imp if imp else 0.0, "position": pos_w / imp if imp else None}


def _shift(d: str, days: int) -> str:
    return date.fromordinal(date.fromisoformat(d).toordinal() + days).isoformat()


def build_data(con, cfg: dict, windows: dict, audits: list, posts: dict, handled: dict) -> dict:
    """windows: {28: (import_row, results, summary), 90: ...}, any may be missing."""
    lo_hi = con.execute("SELECT MIN(date), MAX(date), MAX(fetched_at) FROM api_fetches").fetchone()
    first, last, fetched_at = lo_hi if lo_hi else (None, None, None)

    kpis = None
    if last:
        cur = _totals(con, _shift(last, -27), last)
        prev = _totals(con, _shift(last, -55), _shift(last, -28))
        kpis = {"current": cur, "previous": prev}

    # Weekly series, site-wide and per article. A week is Monday to Sunday.
    days_in = {r["week"]: r["days"] for r in con.execute(WEEK_DAYS)}
    site: dict[str, dict] = {}
    per_page: dict[str, dict[str, dict]] = {}
    for r in con.execute(WEEKS_PAGE):
        w = site.setdefault(r["week"], {"week": r["week"], "clicks": 0, "impressions": 0, "_pw": 0.0})
        w["clicks"] += r["clicks"]; w["impressions"] += r["impressions"]
        w["_pw"] += (r["position"] or 0) * r["impressions"]
        s = slug_of(r["page"], cfg)
        if s:
            per_page.setdefault(s, {})[r["week"]] = {
                "week": r["week"], "clicks": r["clicks"], "impressions": r["impressions"],
                "position": r["position"]}
    weeks = []
    for wk in sorted(site):
        w = site[wk]
        weeks.append({"week": wk, "clicks": w["clicks"], "impressions": w["impressions"],
                      "position": w["_pw"] / w["impressions"] if w["impressions"] else None,
                      "partial": days_in.get(wk, 0) < 7})
    week_keys = [w["week"] for w in weeks]

    def page_series(slug: str) -> list[dict]:
        got = per_page.get(slug, {})
        return [got.get(k, {"week": k, "clicks": 0, "impressions": 0, "position": None}) for k in week_keys]

    # Score history per page, across every scored window.
    history: dict[str, list] = {}
    for r in con.execute(
            "SELECT s.page, s.score, i.date_start, i.date_end FROM opportunity_scores s "
            "JOIN imports i ON i.id = s.import_id ORDER BY i.date_end, i.id"):
        s = slug_of(r["page"], cfg)
        if s:
            span = (date.fromisoformat(r["date_end"]) - date.fromisoformat(r["date_start"])).days + 1
            history.setdefault(s, []).append({"end": r["date_end"], "days": span, "score": round(r["score"], 1)})

    def window_payload(days: int):
        if days not in windows:
            return None
        imp, results, summary = windows[days]
        return {"start": imp["date_start"], "end": imp["date_end"], "source": imp["source"],
                "query_mapping": summary["query_mapping"],
                "pages": [{**asdict(r), "slug": slug_of(r.page, cfg)} for r in results],
                "handled": summary.get("handled_urls", {}), "dead": summary.get("dead_urls", []),
                "cannibalisation": summary.get("cannibalisation", []),
                "templated_impressions": summary.get("templated_impressions", 0)}

    # Per-page query lists for the drilldown, over the 90-day window when there is one.
    q_start, q_end = ((windows[90][0]["date_start"], windows[90][0]["date_end"]) if 90 in windows
                      else (first, last))
    queries: dict[str, list] = {}
    if q_start:
        for r in con.execute(
                "SELECT page, query, SUM(clicks) AS clicks, SUM(impressions) AS impressions, "
                "SUM(position * impressions) / SUM(impressions) AS position FROM gsc_rows "
                "WHERE date BETWEEN ? AND ? GROUP BY page, query HAVING SUM(impressions) > 0 "
                "ORDER BY impressions DESC", (q_start, q_end)):
            s = slug_of(r["page"], cfg)
            if s and len(queries.setdefault(s, [])) < 50:
                queries[s].append({"query": r["query"], "clicks": r["clicks"],
                                   "impressions": r["impressions"], "position": r["position"]})

    audit_by = {a.slug: a.to_dict() for a in audits}
    slugs = sorted(set(posts) | set(per_page) | set(audit_by))
    pages = {}
    for s in slugs:
        if s in handled:
            continue
        meta = posts[s].meta if s in posts else {}
        pages[s] = {
            "slug": s, "title": str(meta.get("title", s)), "category": meta.get("category"),
            "url": f"{cfg['site'].rstrip('/')}{cfg['article_prefix']}{s}",
            "has_post": s in posts, "series": page_series(s), "queries": queries.get(s, []),
            "history": history.get(s, []), "audit": audit_by.get(s)}

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "site": cfg["site"], "data_from": first, "data_to": last, "last_fetch": fetched_at,
        "kpis": kpis, "weeks": weeks,
        "windows": {str(d): window_payload(d) for d in (28, 90)},
        "audit": [a.to_dict() for a in audits],
        "pages": pages, "handled": handled,
    }


def _template() -> str:
    return resources.files("seo_agent").joinpath("templates/dashboard.html").read_text(encoding="utf-8")


def render(data: dict) -> str:
    """Fill the template. The app script gets a hash-pinned CSP, and the data block is
    JSON that can't close its own <script> tag."""
    html = _template()
    app_start = html.index("<script id=\"app\">") + len("<script id=\"app\">")
    app_end = html.index("</script>", app_start)
    digest = base64.b64encode(hashlib.sha256(html[app_start:app_end].encode()).digest()).decode()
    payload = json.dumps(data, separators=(",", ":"), default=str)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return (html.replace("__CSP_SCRIPT_HASH__", f"sha256-{digest}")
                .replace("__DATA__", payload))


def write(out_dir: str | Path, html: str, mode: int = 0o640) -> Path:
    """Write index.html atomically, so nginx never serves a half-written file."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out, prefix=".index-", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    os.chmod(tmp, mode)
    target = out / "index.html"
    os.replace(tmp, target)
    return target
