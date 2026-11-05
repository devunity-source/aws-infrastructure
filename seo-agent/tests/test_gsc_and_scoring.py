import json
import shutil
import zipfile
from pathlib import Path

import pytest

from seo_agent import config as cfgmod
from seo_agent.cli import main
from seo_agent.gsc_csv import GSCParseError, load_export
from seo_agent.scoring import (assign_queries, expected_ctr, score_pages, slug_of,
                               template_families)
from seo_agent.storage import connect, save_export

FIX = Path(__file__).parent / "fixtures" / "gsc_export"
CFG = {**cfgmod.load(), "site": "https://digitalapricot.io"}


def rows(exp_rows):
    return [dict(key=r.key, clicks=r.clicks, impressions=r.impressions, ctr=r.ctr,
                 position=r.position) for r in exp_rows]


# ---------- CSV parsing ----------

def test_parses_all_tables_with_bom_and_percentages():
    exp = load_export(FIX)
    assert len(exp.pages) == 7 and len(exp.queries) == 10
    assert exp.pages[1].ctr == pytest.approx(0.0008)
    assert exp.filters["Search type"] == "Web (text-based)"
    assert (exp.date_start, exp.date_end) == ("2026-08-03", "2026-08-04")
    assert exp.totals()["impressions"] == 300  # from Chart, not Pages


def test_multiline_query_is_normalised():
    exp = load_export(FIX)
    assert "ai glass" in [q.key for q in exp.queries]


def test_zip_and_folder_give_same_hash(tmp_path):
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in FIX.iterdir():
            zf.write(f, f"nested/{f.name}")
    assert load_export(z).content_hash == load_export(FIX).content_hash


def test_bad_header_and_missing_column(tmp_path):
    (tmp_path / "Pages.csv").write_text("Nope,Clicks\nx,1\n")
    with pytest.raises(GSCParseError, match="unrecognised header"):
        load_export(tmp_path)
    (tmp_path / "Pages.csv").write_text("Top pages,Clicks,Impressions\nx,1,2\n")
    with pytest.raises(GSCParseError, match="missing metric"):
        load_export(tmp_path)


def test_rejects_non_export(tmp_path):
    with pytest.raises(GSCParseError):
        load_export(tmp_path)  # empty folder


# ---------- storage ----------

def test_import_is_idempotent(tmp_path):
    con = connect(tmp_path / "db.sqlite")
    exp = load_export(FIX)
    a, created_a = save_export(con, exp)
    b, created_b = save_export(con, exp)
    assert (a, created_a, created_b) == (b, True, False)
    n = con.execute("SELECT COUNT(*) FROM gsc_aggregate").fetchone()[0]
    assert n == 7 + 10 + 2 + 2


# ---------- classification ----------

@pytest.mark.parametrize("url,slug", [
    ("https://digitalapricot.io/best-ai-smart-glasses", "best-ai-smart-glasses"),
    ("https://digitalapricot.io/best-ai-smart-glasses/", "best-ai-smart-glasses"),
    ("https://digitalapricot.io/category/mice", None),
    ("https://digitalapricot.io/disclosure", None),
    ("https://digitalapricot.io/#about", None),
    ("https://digitalapricot.io/", None),
    ("https://digitalapricot.io/store/product/x", None),
    ("https://www.digitalapricot.io/best-x-monitors", "best-x-monitors"),
    ("https://digitalapricot.io/favicon.svg", None),
    # Before the move: the old address maps to the same article.
    ("https://protocloudsolutions.com/blog/best-ai-smart-glasses", "best-ai-smart-glasses"),
    ("https://protocloudsolutions.com/blog/best-ai-smart-glasses.html", "best-ai-smart-glasses"),
    # The consulting site in the same property is never an article.
    ("https://protocloudsolutions.com/services", None),
    ("https://protocloudsolutions.com/blog/category/mice", None),
    ("https://elsewhere.com/best-x-monitors", None),
])
def test_slug_of(url, slug):
    assert slug_of(url, CFG) == slug


def test_template_family_detects_padding_but_keeps_real_audiences():
    qs = [q.key for q in load_export(FIX).queries]
    t = template_families(qs, CFG)
    assert "best gaming mouse for cyclists" in t
    assert "best gaming mouse for programmers" not in t
    assert "ai glasses" not in t


def test_template_family_needs_minimum_size():
    qs = ["best gaming mouse for cyclists", "best gaming mouse for yoga practitioners"]
    assert template_families(qs, CFG) == set()


def test_query_assignment_and_shared_queries():
    slugs = ["best-mice-for-gaming-and-work", "best-mice-for-productivity", "best-ai-smart-glasses"]
    qs = [{"key": k, "impressions": 10} for k in
          ["ai glass", "best gaming mouse for teachers", "best mouse under $300"]]
    by_page, shared = assign_queries(slugs, qs, CFG)
    assert [q["key"] for q in by_page["best-ai-smart-glasses"]] == ["ai glass"]
    assert "best gaming mouse for teachers" in [q["key"] for q in by_page["best-mice-for-gaming-and-work"]]
    assert ("best-mice-for-gaming-and-work", "best-mice-for-productivity") in shared


def test_tie_break_prefers_page_with_full_head_match():
    slugs = ["fitbit-air-2026", "google-io-devops-cloud-antigravity"]
    by_page, shared = assign_queries(slugs, [{"key": "google fitbit air 2026", "impressions": 5}], CFG)
    assert list(by_page) == ["fitbit-air-2026"] and not shared


def test_screenless_does_not_match_screen():
    by_page, _ = assign_queries(["best-portable-monitors"],
                                [{"key": "fitbit screenless tracker", "impressions": 5}], CFG)
    assert not by_page


# ---------- scoring ----------

def test_scores_are_bounded_explained_and_sorted():
    exp = load_export(FIX)
    res, summary = score_pages(rows(exp.pages), rows(exp.queries), CFG)
    assert [r.score for r in res] == sorted((r.score for r in res), reverse=True)
    assert all(0 <= r.score <= 100 for r in res)
    assert all(r.reasons for r in res)
    assert summary["articles_scored"] == 3
    assert summary["excluded_non_articles"]  # home, category, disclosure, fragment


def test_templated_queries_flagged_and_lower_relevance():
    exp = load_export(FIX)
    res, _ = score_pages(rows(exp.pages), rows(exp.queries), CFG)
    mice = next(r for r in res if r.page.endswith("gaming-and-work"))
    assert "templated_queries" in mice.flags
    assert mice.components["query_relevance"] < 0.5


def test_ctr_gap_damped_for_small_samples():
    page = dict(key="https://digitalapricot.io/best-x-monitors", clicks=0, ctr=0.0, position=8)
    small, _ = score_pages([{**page, "impressions": 20}], [], CFG)
    big, _ = score_pages([{**page, "impressions": 2000}], [], CFG)
    assert small[0].components["ctr_gap"] < big[0].components["ctr_gap"] == 1.0


def test_position_beyond_20_is_marked():
    page = dict(key="https://digitalapricot.io/best-x-monitors", clicks=0, ctr=0.0,
                impressions=500, position=35)
    r, _ = score_pages([page], [], CFG)
    assert r[0].components["position_band"] < 1 and any("beyond page 2" in x for x in r[0].reasons)


def test_declining_flag_against_previous_import():
    url = "https://digitalapricot.io/best-x-monitors"
    cur = [dict(key=url, clicks=0, ctr=0.0, impressions=100, position=9)]
    prev = {url: dict(key=url, clicks=2, ctr=0.01, impressions=400, position=8)}
    r, _ = score_pages(cur, [], CFG, prev)
    assert "declining" in r[0].flags


def test_dead_url_flagged_only_for_missing_posts():
    live = dict(key="https://digitalapricot.io/best-x-monitors", clicks=0, ctr=0.0,
                impressions=500, position=9)
    gone = {**live, "key": "https://digitalapricot.io/old-removed-post"}
    res, summary = score_pages([live, gone], [], CFG, existing_slugs={"best-x-monitors"})
    by_page = {r.page: r for r in res}
    assert "dead_url" not in by_page[live["key"]].flags
    assert "dead_url" in by_page[gone["key"]].flags
    assert by_page[gone["key"]].reasons[0].startswith("No post with this slug")
    assert summary["dead_urls"] == [gone["key"]]


def test_dead_url_check_skipped_without_slugs():
    page = dict(key="https://digitalapricot.io/anything", clicks=0, ctr=0.0,
                impressions=500, position=9)
    res, summary = score_pages([page], [], CFG)
    assert "dead_url" not in res[0].flags and summary["dead_urls"] == []


def test_weights_must_sum_to_one(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"weights": {"visibility": 0.9}}))
    with pytest.raises(ValueError, match="sum to 1"):
        cfgmod.load(p)


def test_expected_ctr_curve_is_monotonic():
    vals = [expected_ctr(p, CFG) for p in range(1, 40)]
    assert vals == sorted(vals, reverse=True)


# ---------- CLI end to end ----------

def test_cli_import_score_rerun(tmp_path, capsys):
    db = str(tmp_path / "x.sqlite")
    assert main(["--db", db, "score"]) == 2  # nothing imported yet
    assert main(["--db", db, "import", str(FIX)]) == 0
    assert main(["--db", db, "import", str(FIX)]) == 0
    assert "already imported" in capsys.readouterr().out
    out = tmp_path / "s.json"
    assert main(["--db", db, "score", "--json", str(out), "--md", str(tmp_path / "s.md")]) == 0
    assert main(["--db", db, "score", "--json", str(out)]) == 0  # rerun safe
    data = json.loads(out.read_text())
    assert len(data["pages"]) == 3
    con = connect(db)
    assert con.execute("SELECT COUNT(*) FROM opportunity_scores").fetchone()[0] == 3


def test_cli_posts_dir_flags_dead_urls(tmp_path):
    db = str(tmp_path / "x.sqlite")
    posts = tmp_path / "posts"; posts.mkdir()
    (posts / "best-mice-for-gaming-and-work.mdx").write_text("---\ntitle: x\n---\n")
    assert main(["--db", db, "import", str(FIX)]) == 0
    out = tmp_path / "s.json"
    assert main(["--db", db, "score", "--posts-dir", str(posts), "--json", str(out)]) == 0
    pages = {p["page"]: p for p in json.loads(out.read_text())["pages"]}
    dead = {k for k, p in pages.items() if "dead_url" in p["flags"]}
    assert dead and not any(k.endswith("/best-mice-for-gaming-and-work") for k in dead)
    assert main(["--db", db, "score", "--posts-dir", str(tmp_path / "nope")]) == 2


def test_cli_reports_parse_errors(tmp_path):
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / "Pages.csv").write_text("Nope\n")
    assert main(["--db", str(tmp_path / "d.sqlite"), "import", str(bad)]) == 2
