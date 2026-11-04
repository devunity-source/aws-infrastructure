"""Static dashboard: data, escaping, CSP and file handling, built from a fake API run."""
import base64
import hashlib
import json
import re
import stat

from seo_agent import cli

A = "https://example.com/blog/best-x-monitors"
EVIL = "</script><script>alert(1)</script>"


def _fake_api(evil=False):
    class Fake:
        def query(self, site, start, end, dims):
            keys = {"date": start, "page": A, "query": EVIL if evil else "best x monitor",
                    "device": "MOBILE", "country": "usa"}
            yield {"keys": [keys[d] for d in dims], "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 7.0}
    return Fake()


def _build(tmp_path, monkeypatch, evil=False):
    monkeypatch.setattr(cli, "make_client", lambda key: _fake_api(evil))
    db = str(tmp_path / "x.sqlite")
    assert cli.main(["--db", db, "fetch", "--site", "sc-domain:example.com",
                     "--start", "2026-09-01", "--end", "2026-11-01"]) == 0
    assert cli.main(["--db", db, "window", "--days", "28"]) == 0
    posts = tmp_path / "posts"; posts.mkdir()
    (posts / "best-x-monitors.md").write_text('---\ntitle: "Best X"\ndescription: "d"\npubDate: 2026-10-01\n---\nBody\n')
    out = tmp_path / "dash"
    assert cli.main(["--db", db, "dashboard", "--out", str(out), "--posts-dir", str(posts),
                     "--today", "2026-11-04"]) == 0
    return (out / "index.html")


def _data(html):
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_dashboard_embeds_every_view(tmp_path, monkeypatch):
    path = _build(tmp_path, monkeypatch)
    d = _data(path.read_text())
    assert d["windows"]["28"]["pages"][0]["slug"] == "best-x-monitors"
    assert d["windows"]["90"] is None  # only a 28-day window was built
    assert d["kpis"]["current"]["impressions"] == 28 * 20
    assert d["weeks"] and all({"week", "clicks", "impressions", "partial"} <= set(w) for w in d["weeks"])
    pg = d["pages"]["best-x-monitors"]
    assert pg["title"] == "Best X" and pg["queries"][0]["query"] == "best x monitor"
    assert pg["history"] and len(pg["series"]) == len(d["weeks"])
    assert d["audit"][0]["slug"] == "best-x-monitors"


def test_dashboard_escapes_hostile_queries_and_pins_its_script(tmp_path, monkeypatch):
    html = _build(tmp_path, monkeypatch, evil=True).read_text()
    data_block = re.search(r'type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "<" not in data_block and "alert(1)" in data_block  # present, but can't close the tag
    assert html.count("<script") == 2  # only the data block and the app
    assert _data(html)["pages"]["best-x-monitors"]["queries"][0]["query"] == EVIL
    app = re.search(r'<script id="app">(.*?)</script>', html, re.S).group(1)
    digest = "sha256-" + base64.b64encode(hashlib.sha256(app.encode()).digest()).decode()
    assert f"script-src '{digest}'" in html and "__CSP_SCRIPT_HASH__" not in html
    assert "esc(q.query)" in app  # queries are rendered through the escaper
    assert "http://" not in app and "https://" not in app.replace("https://protocloudsolutions", "")  # no external loads


def test_dashboard_file_is_group_readable_not_world(tmp_path, monkeypatch):
    mode = stat.S_IMODE(_build(tmp_path, monkeypatch).stat().st_mode)
    assert mode == 0o640
    assert not list((tmp_path / "dash").glob(".index-*"))  # no temp files left behind


def test_dashboard_needs_a_database_and_a_window(tmp_path):
    out = str(tmp_path / "dash")
    assert cli.main(["--db", str(tmp_path / "none.sqlite"), "dashboard", "--out", out]) == 2
    from seo_agent.storage import connect
    connect(tmp_path / "empty.sqlite")
    assert cli.main(["--db", str(tmp_path / "empty.sqlite"), "dashboard", "--out", out]) == 2
