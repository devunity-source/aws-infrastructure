"""seo-agent CLI.

  python -m seo_agent import <export.zip|folder>   # CSV export, idempotent
  python -m seo_agent sites --key key.json          # properties the key can read
  python -m seo_agent fetch --key key.json --site sc-domain:example.com [--days 90]
  python -m seo_agent window [--days 90]            # turn fetched API days into an import
  python -m seo_agent score [--top N] [--json out.json] [--md out.md] [--posts-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as config_mod
from .gsc_api import PAGE_DIMS, ROW_DIMS, Client, GSCAPIError, load_key, session_from_key, to_records
from .gsc_csv import GSCParseError, load_export
from .scoring import score_pages
from .storage import (aggregate, api_date_range, api_sites, build_window_import, connect, fetch_log,
                      latest_import, observed_query_pages, save_api_day, save_export, save_scores)

DEFAULT_DB = os.environ.get("SEO_AGENT_DB", "data/seo_agent.sqlite")
# The blog's posts, when the agent runs inside the aws-infrastructure repo.
REPO_POSTS_DIR = Path(__file__).resolve().parents[2] / "protocloud-reviews" / "src" / "content" / "posts"


def existing_slugs(posts_dir: str | None) -> set[str] | None:
    """Slugs that have a post. None when no posts folder is given or found."""
    d = Path(posts_dir or os.environ.get("SEO_AGENT_POSTS_DIR") or REPO_POSTS_DIR)
    if not d.is_dir():
        if posts_dir:
            raise FileNotFoundError(f"--posts-dir {posts_dir} is not a folder")
        return None
    return {p.stem for p in d.iterdir() if p.suffix in (".md", ".mdx")}


# Search Console finalises data with a lag of a few days, in Pacific Time.
FINAL_LAG_DAYS = 3
# An empty day this recent may just not be final yet, so it is fetched again next run.
RECHECK_EMPTY_DAYS = 10


def make_client(key: str | None) -> Client:
    return Client(session_from_key(load_key(key)))


def pacific_today() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles")).date()
    except Exception:  # no tz database: UTC is at most a day off
        return datetime.now(timezone.utc).date()


def _days(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [(d0 + timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]


def _rows(rs):
    return [dict(key=r["key"], clicks=r["clicks"], impressions=r["impressions"],
                 ctr=r["ctr"], position=r["position"]) for r in rs]


def cmd_import(a) -> int:
    try:
        exp = load_export(a.path)
    except GSCParseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    con = connect(a.db)
    iid, created = save_export(con, exp)
    t = exp.totals()
    print(f"{'imported' if created else 'already imported'} #{iid}: "
          f"{exp.date_start} to {exp.date_end}, {t['clicks']} clicks, "
          f"{t['impressions']:,} impressions, CTR {t['ctr']:.2%}, "
          f"{t['pages']} pages, {t['queries']} queries")
    q_imp = sum(r.impressions for r in exp.queries)
    if exp.queries and q_imp < t["impressions"]:
        print(f"note: Queries.csv covers {q_imp:,} of {t['impressions']:,} impressions "
              f"({q_imp / t['impressions']:.0%}); the rest are anonymised by Google.")
    return 0


def cmd_sites(a) -> int:
    try:
        entries = make_client(a.key).sites()
    except GSCAPIError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not entries:
        print("This key can't read any Search Console property yet. In Search Console, open "
              "Settings, Users and permissions, and add the service account's email.")
        return 1
    for e in entries:
        print(f"{e.get('siteUrl')}  ({e.get('permissionLevel')})")
    return 0


def cmd_fetch(a) -> int:
    site = a.site or os.environ.get("GSC_SITE")
    if not site:
        print("error: pass --site (or set GSC_SITE). Run the `sites` command to see the exact value.",
              file=sys.stderr)
        return 2
    today = pacific_today()
    end = a.end or (today - timedelta(FINAL_LAG_DAYS)).isoformat()
    start = a.start or (date.fromisoformat(end) - timedelta(a.days - 1)).isoformat()
    if start > end:
        print(f"error: start {start} is after end {end}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    con = connect(a.db)
    recheck_from = (today - timedelta(RECHECK_EMPTY_DAYS)).isoformat()
    done = {} if a.refetch else {d for d, n in fetch_log(con, site).items() if n > 0 or d < recheck_from}
    days = [d for d in _days(start, end) if d not in done]
    if not days:
        print(f"nothing to fetch: {start} to {end} is already stored. Use --refetch to fetch it again.")
        return 0
    try:
        client = make_client(a.key)
        n_rows = n_pages = 0
        for d in days:
            rows = to_records(list(client.query(site, d, d, ROW_DIMS)), ROW_DIMS)
            pages = to_records(list(client.query(site, d, d, PAGE_DIMS)), PAGE_DIMS)
            save_api_day(con, site, d, rows, pages)
            n_rows, n_pages = n_rows + len(rows), n_pages + len(pages)
    except GSCAPIError as e:
        print(f"error: {e}", file=sys.stderr)
        print("Days fetched before the error are saved. Rerun to continue.", file=sys.stderr)
        return 2
    print(f"fetched {len(days)} days, {days[0]} to {days[-1]}: "
          f"{n_rows:,} query rows, {n_pages:,} page rows")
    print("next: python -m seo_agent window --days 90")
    return 0


def cmd_window(a) -> int:
    con = connect(a.db)
    lo, hi = api_date_range(con)
    if not hi:
        print("error: no API data yet. Run the `fetch` command first.", file=sys.stderr)
        return 2
    sites = api_sites(con)
    site = a.site or (sites[0] if len(sites) == 1 else None)
    if not site:
        print(f"error: data for several properties is stored ({', '.join(sites)}). Pass --site.",
              file=sys.stderr)
        return 2
    end = a.end or hi
    start = (date.fromisoformat(end) - timedelta(a.days - 1)).isoformat()
    if start < lo:
        print(f"note: the window starts {start} but stored data begins {lo}. "
              f"Fetch more days for a full {a.days}-day window.")
    iid, created, t = build_window_import(con, site, start, end)
    ctr = t["clicks"] / t["impressions"] if t["impressions"] else 0
    print(f"{'built' if created else 'already built'} import #{iid}: {start} to {end}, "
          f"{t['clicks']} clicks, {t['impressions']:,} impressions, CTR {ctr:.2%}, "
          f"{t['pages']} pages, {t['queries']} queries")
    return 0


def render_md(imp, results, summary, top: int) -> str:
    L = [f"# SEO opportunities ({imp['date_start']} to {imp['date_end']})", ""]
    L.append(f"{summary['articles_scored']} articles scored. "
             f"{len(summary['excluded_non_articles'])} non-article URLs excluded. "
             f"{summary['templated_query_count']} templated queries "
             f"({summary['templated_impressions']:,} impressions) treated as low signal.")
    if summary.get("dead_urls"):
        L += ["", f"**{len(summary['dead_urls'])} scored URLs have no post in the blog** (flag `dead_url`). "
                  "Restore, redirect or retire them first."]
    L += ["", "| # | Article | Score | Impr. | Clicks | CTR | Pos. | Flags |",
          "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results[:top], 1):
        m = r.metrics
        slug = r.page.split("/blog/")[-1]
        L.append(f"| {i} | {slug} | **{r.score:.0f}** | {m['impressions']:,} | {m['clicks']} | "
                 f"{m['ctr']:.2%} | {m['position']:.1f} | {', '.join(sorted(set(r.flags))) or ''} |")
    for i, r in enumerate(results[:top], 1):
        L += ["", f"## {i}. {r.page} ({r.score:.0f}/100)", ""]
        L += [f"- {x}" for x in dict.fromkeys(r.reasons)]
        L.append("- Components: " + ", ".join(f"{k} {v:.2f}" for k, v in r.components.items()))
        if r.top_queries:
            L += ["", f"{summary['query_mapping'].capitalize()} top queries:", ""]
            for q in r.top_queries[:6]:
                t = " (templated)" if q["templated"] else ""
                L.append(f"- `{q['query']}`: {q['impressions']} impr, {q['clicks']} clicks, pos {q['position']:.1f}{t}")
    if summary["cannibalisation"]:
        L += ["", f"## Possible cannibalisation ({summary['query_mapping']})", ""]
        for c in summary["cannibalisation"][:8]:
            L.append(f"- {' vs '.join(c['pages'])}: {c['shared_impressions']} impr. "
                     f"e.g. {', '.join(repr(x) for x in c['examples'][:3])}")
    return "\n".join(L) + "\n"


def cmd_score(a) -> int:
    cfg = config_mod.load(a.config)
    con = connect(a.db)
    imp = latest_import(con)
    if not imp:
        print("error: nothing imported yet. Run: python -m seo_agent import <export.zip>", file=sys.stderr)
        return 2
    # Compare like with like: same source and same window length, ending earlier.
    prev = con.execute(
        "SELECT id FROM imports WHERE id<>? AND date_end<? AND source=? "
        "AND julianday(date_end) - julianday(date_start) = julianday(?) - julianday(?) "
        "ORDER BY date_end DESC LIMIT 1",
        (imp["id"], imp["date_end"], imp["source"], imp["date_end"], imp["date_start"])).fetchone()
    previous = {r["key"]: dict(r) for r in aggregate(con, prev["id"], "page")} if prev else None
    try:
        slugs = existing_slugs(a.posts_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    observed = (observed_query_pages(con, imp["date_start"], imp["date_end"])
                if imp["source"] == "api" else None)
    results, summary = score_pages(_rows(aggregate(con, imp["id"], "page")),
                                   _rows(aggregate(con, imp["id"], "query")), cfg, previous, slugs,
                                   observed)
    for r in results:
        r.flags = sorted(set(r.flags))
    save_scores(con, imp["id"], results)
    md = render_md(imp, results, summary, a.top)
    for f in (a.md, a.json):
        if f:
            os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
    if a.md:
        open(a.md, "w").write(md)
    if a.json:
        json.dump({"import": dict(imp), "summary": summary,
                   "pages": [asdict(r) for r in results]}, open(a.json, "w"), indent=2)
    print(md if not a.md else f"wrote {a.md}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="seo-agent")
    ap.add_argument("--db", default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import"); p.add_argument("path"); p.set_defaults(fn=cmd_import)
    p = sub.add_parser("score")
    p.add_argument("--config"); p.add_argument("--top", type=int, default=10)
    p.add_argument("--json"); p.add_argument("--md")
    p.add_argument("--posts-dir", help="blog posts folder, for the dead_url check. "
                   "Defaults to protocloud-reviews/src/content/posts in this repo.")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("sites", help="list Search Console properties the key can read")
    p.add_argument("--key", help="service account key file (or set GSC_SERVICE_ACCOUNT_JSON)")
    p.set_defaults(fn=cmd_sites)
    p = sub.add_parser("fetch", help="fetch Search Console API data, one day at a time")
    p.add_argument("--key"); p.add_argument("--site", help="e.g. sc-domain:example.com")
    p.add_argument("--days", type=int, default=90); p.add_argument("--start"); p.add_argument("--end")
    p.add_argument("--refetch", action="store_true", help="fetch days again even if stored")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("window", help="aggregate fetched API days into an import for `score`")
    p.add_argument("--days", type=int, default=90); p.add_argument("--end"); p.add_argument("--site")
    p.set_defaults(fn=cmd_window)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
