"""seo-agent CLI.

  python -m seo_agent import <export.zip|folder>   # idempotent
  python -m seo_agent score [--top N] [--json out.json] [--md out.md] [--posts-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from . import config as config_mod
from .gsc_csv import GSCParseError, load_export
from .scoring import score_pages
from .storage import aggregate, connect, latest_import, save_export, save_scores

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
            L += ["", "Inferred top queries:", ""]
            for q in r.top_queries[:6]:
                t = " (templated)" if q["templated"] else ""
                L.append(f"- `{q['query']}`: {q['impressions']} impr, {q['clicks']} clicks, pos {q['position']:.1f}{t}")
    if summary["cannibalisation"]:
        L += ["", "## Possible cannibalisation (inferred)", ""]
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
    prev = con.execute("SELECT id FROM imports WHERE id<>? AND date_end<? ORDER BY date_end DESC LIMIT 1",
                       (imp["id"], imp["date_end"])).fetchone()
    previous = {r["key"]: dict(r) for r in aggregate(con, prev["id"], "page")} if prev else None
    try:
        slugs = existing_slugs(a.posts_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    results, summary = score_pages(_rows(aggregate(con, imp["id"], "page")),
                                   _rows(aggregate(con, imp["id"], "query")), cfg, previous, slugs)
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
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
