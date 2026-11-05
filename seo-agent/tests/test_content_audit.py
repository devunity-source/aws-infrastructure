"""Article parser, nginx rules, handled URLs in scoring, and the content audit."""
import json
from datetime import date
from pathlib import Path

from seo_agent import config as cfgmod
from seo_agent.audit import audit_posts, render_audit_md
from seo_agent.cli import main
from seo_agent.content import handled_urls, load_posts, parse_post
from seo_agent.scoring import score_pages

CFG = {**cfgmod.load(), "site": "https://digitalapricot.io"}
TODAY = date(2026, 11, 4)

POST_A = """---
title: "The Best X Monitors in 2024"
description: "Short."
pubDate: 2026-01-10
category: monitors
heroImage: "/images/a.png"
products:
  - name: "Acme 27"
    pick: "Best overall"
    asin: "B000000001"
  - name: "Zeta 32"
    pick: "Best value"
---
import ProductCard from '../../components/ProductCard.astro';

Intro with a link to [the Y guide](/blog/best-y-monitors) and [an old post](/blog/retired-post).
See also [the gaming mice](/blog/old-mice) and [about us](/blog/about) and [elsewhere](https://example.org/x).

## How we picked

<ProductCard index={0} {...frontmatter.products[0]} />

### A sub point

## The short version
"""

POST_B = """---
title: "Best Y Monitors"
description: "A long enough description that names the picks and says what the guide answers for readers."
pubDate: 2026-10-20
updatedDate: 2026-11-01
category: monitors
heroImage: "/images/b.png"
heroAlt: "Two monitors"
---
""" + "word " * 700 + """
[back to X](/blog/best-x-monitors) and [x again](/blog/best-x-monitors#picks)

## One

## Two

## Three
"""

NGINX = """
location = /blog/old-mice { return 301 /blog/best-mice; }
location = /blog/retired-post { return 410; }
location = /blog { root /var/www; }
location ^~ /blog/ { try_files $uri =404; }
"""


def write_blog(tmp_path: Path):
    posts = tmp_path / "posts"; posts.mkdir()
    (posts / "best-x-monitors.mdx").write_text(POST_A)
    (posts / "best-y-monitors.md").write_text(POST_B)
    conf = tmp_path / "blog.conf"; conf.write_text(NGINX)
    return posts, conf


# ---------- parser ----------

def test_parse_post_reads_frontmatter_headings_links_and_products(tmp_path):
    posts, _ = write_blog(tmp_path)
    p = parse_post(posts / "best-x-monitors.mdx")
    assert p.slug == "best-x-monitors" and p.meta["category"] == "monitors"
    assert p.get_date("pubDate") == date(2026, 1, 10)
    assert p.headings == [(2, "How we picked"), (3, "A sub point"), (2, "The short version")]
    assert p.internal_links == ["best-y-monitors", "retired-post", "old-mice", "about"]
    assert p.external_links == 1 and len(p.products) == 2
    assert 20 < p.word_count < 60  # prose and headings only: imports and components are not counted


def test_links_with_anchors_are_deduplicated(tmp_path):
    posts, _ = write_blog(tmp_path)
    assert parse_post(posts / "best-y-monitors.md").internal_links == ["best-x-monitors"]


def test_handled_urls_reads_only_exact_return_rules(tmp_path):
    _, conf = write_blog(tmp_path)
    assert handled_urls(conf) == {"old-mice": "redirects to /blog/best-mice (301)",
                                  "retired-post": "retired (410)"}
    assert handled_urls(tmp_path / "missing.conf") == {} and handled_urls(None) == {}


# ---------- scoring skips handled URLs ----------

def test_handled_urls_are_skipped_not_flagged_dead():
    page = lambda s: dict(key=f"https://digitalapricot.io/{s}", clicks=0, ctr=0.0, impressions=300, position=9)
    res, summary = score_pages([page("live"), page("retired-post")], [], CFG, existing_slugs={"live"},
                               handled={"retired-post": "retired (410)"})
    assert [r.page for r in res] == ["https://digitalapricot.io/live"]
    assert summary["handled_urls"] == {"https://digitalapricot.io/retired-post": "retired (410)"}
    assert summary["dead_urls"] == []


# ---------- audit ----------

def _ids(audit):
    return {i.id: i for i in audit.issues}


def test_audit_rules_fire_with_evidence(tmp_path):
    posts, conf = write_blog(tmp_path)
    audits = {a.slug: a for a in audit_posts(load_posts(posts), handled_urls(conf), today=TODAY)}
    x, y = _ids(audits["best-x-monitors"]), _ids(audits["best-y-monitors"])
    assert x["stale_year_in_title"].severity == "high" and "2024" in x["stale_year_in_title"].evidence
    assert "retired (410)" in x["broken_internal_link"].evidence
    assert "301" in x["link_through_redirect"].evidence
    assert {"description_too_short", "hero_alt_missing", "thin_content", "not_updated",
            "product_search_link"} <= set(x)
    assert x["product_search_link"].evidence == "Zeta 32"
    assert "orphan" not in x  # Y links to X
    assert "orphan" not in y and "thin_content" not in y and "few_headings" not in y
    assert "few_headings" in x  # two H2s


def test_audit_joins_search_scores_and_respects_recent_changes(tmp_path):
    posts, conf = write_blog(tmp_path)
    hot = {"score": 82.0, "flags": ["year_in_queries"],
           "metrics": {"impressions": 900, "clicks": 0, "position": 23.0}}
    audits = {a.slug: a for a in audit_posts(load_posts(posts), handled_urls(conf),
                                             {"best-x-monitors": hot, "best-y-monitors": hot}, TODAY)}
    x, y = _ids(audits["best-x-monitors"]), _ids(audits["best-y-monitors"])
    assert x["no_clicks_high_opportunity"].severity == "high"
    assert "snippet_recently_changed" in y and "no_clicks_high_opportunity" not in y  # updated 3 days ago
    assert "ranks_beyond_page_2" in x and "year_queries_no_current_year" in x
    assert audits["best-x-monitors"].opportunity == 82.0
    ordered = audit_posts(load_posts(posts), handled_urls(conf), today=TODAY)
    assert ordered[0].priority >= ordered[1].priority


def test_render_audit_md_lists_every_post(tmp_path):
    posts, conf = write_blog(tmp_path)
    md = render_audit_md(audit_posts(load_posts(posts), handled_urls(conf), today=TODAY), TODAY, None)
    assert "2 posts audited" in md and "## best-x-monitors" in md and "No search data joined" in md


def test_cli_audit_without_and_with_search_data(tmp_path):
    posts, conf = write_blog(tmp_path)
    out = tmp_path / "a.json"
    db = str(tmp_path / "none.sqlite")
    assert main(["--db", db, "audit", "--posts-dir", str(posts), "--nginx", str(conf),
                 "--today", "2026-11-04", "--json", str(out), "--md", str(tmp_path / "a.md")]) == 0
    data = json.loads(out.read_text())
    assert {a["slug"] for a in data} == {"best-x-monitors", "best-y-monitors"}
    assert all(a["opportunity"] is None for a in data)
    assert main(["--db", db, "audit", "--posts-dir", str(tmp_path / "nope")]) == 2
