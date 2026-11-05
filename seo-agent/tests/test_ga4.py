"""GA4 product-click import and its dashboard view, against a fake session (no network)."""
import json
import re

from seo_agent import cli, ga4_api
from seo_agent.ga4_api import PAGE_DIMS, PRODUCT_DIMS, GA4Client
from seo_agent.gsc_api import GSCAPIError
from seo_agent.storage import connect, save_ga4_range

from test_gsc_api import Resp, Session


def ga4_row(day, path, clicks, product=None, asin=None):
    vals = [day.replace("-", ""), path] + ([product, asin] if product is not None else [])
    return {"dimensionValues": [{"value": v} for v in vals], "metricValues": [{"value": str(clicks)}]}


def test_report_filters_to_the_click_event_and_pages():
    s = Session(Resp(body={"rows": [ga4_row("2026-11-01", "/blog/a", 3, "Cam", "B0DDTH3HX8")] * 2, "rowCount": 3}),
                Resp(body={"rows": [ga4_row("2026-11-02", "/blog/a", 1, "Cam", "(not set)")], "rowCount": 3}))
    c = GA4Client(s, sleep=lambda _: None)
    rows, by_product = c.clicks("123", "2026-11-01", "2026-11-02")
    assert by_product and len(rows) == 3
    method, url, body = s.calls[0]
    assert url.endswith("/properties/123:runReport")
    assert body["dimensionFilter"]["filter"]["stringFilter"]["value"] == "affiliate_click"
    assert [d["name"] for d in body["dimensions"]] == PRODUCT_DIMS
    assert s.calls[1][2]["offset"] == 2  # second page
    assert rows[0] == {"date": "2026-11-01", "page_path": "/blog/a", "product": "Cam", "asin": "B0DDTH3HX8", "clicks": 3}
    assert rows[2]["asin"] == ""  # "(not set)" is stored as empty


def test_falls_back_to_pages_without_custom_dimensions():
    bad = Resp(400, {"error": {"message": "Field customEvent:product_name is not a valid dimension"}})
    s = Session(bad, Resp(body={"rows": [ga4_row("2026-11-01", "/blog/a", 2)], "rowCount": 1}))
    rows, by_product = GA4Client(s, sleep=lambda _: None).clicks("123", "2026-11-01", "2026-11-01")
    assert not by_product and rows[0]["product"] == "" and rows[0]["clicks"] == 2
    assert [d["name"] for d in s.calls[1][2]["dimensions"]] == PAGE_DIMS


def test_forbidden_explains_ga4_access():
    s = Session(Resp(403, {"error": {"message": "User does not have sufficient permissions"}}))
    try:
        GA4Client(s, sleep=lambda _: None).clicks("123", "2026-11-01", "2026-11-01")
    except GSCAPIError as e:
        assert "Property access management" in str(e) and "Search Console" not in str(e)
    else:
        raise AssertionError("expected an error")


def test_disabled_api_says_to_enable_it():
    msg = "Google Analytics Data API has not been used in project 1 before or it is disabled. Enable it by visiting https://x then retry."
    s = Session(Resp(403, {"error": {"message": msg}}))
    try:
        GA4Client(s, sleep=lambda _: None).clicks("123", "2026-11-01", "2026-11-01")
    except GSCAPIError as e:
        assert "Enable the API" in str(e) and "Property access" not in str(e) and "retry.." not in str(e)
    else:
        raise AssertionError("expected an error")


def test_save_replaces_the_range(tmp_path):
    con = connect(tmp_path / "x.sqlite")
    r = {"date": "2026-11-01", "page_path": "/blog/a", "product": "Cam", "asin": "", "clicks": 2}
    save_ga4_range(con, "123", "2026-11-01", "2026-11-02", [r, r], True)  # duplicates are summed
    save_ga4_range(con, "123", "2026-11-01", "2026-11-02", [r], True)     # a rerun replaces
    assert con.execute("SELECT SUM(clicks) FROM ga4_clicks").fetchone()[0] == 2


def test_cli_needs_a_numeric_property(tmp_path, capsys):
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "ga4", "--property", "G-2GGCFXYL86"]) == 2
    assert "numeric GA4 property ID" in capsys.readouterr().err


def test_dashboard_shows_product_clicks(tmp_path, monkeypatch):
    from test_dashboard import _build, _data
    rows = [{"date": "2026-10-30", "page_path": "/blog/best-x-monitors", "product": "Cam <b>", "asin": "B0DDTH3HX8", "clicks": 4},
            {"date": "2026-08-20", "page_path": "/blog/best-x-monitors.html", "product": "", "asin": "", "clicks": 1},
            {"date": "2026-10-30", "page_path": "/blog/tag/x", "product": "", "asin": "", "clicks": 9}]

    class Fake:
        def clicks(self, prop, start, end):
            return rows, True
    monkeypatch.setattr(cli, "make_ga4_client", lambda key: Fake())
    db = str(tmp_path / "x.sqlite")
    assert cli.main(["--db", db, "ga4", "--property", "123", "--start", "2026-08-01", "--end", "2026-11-01"]) == 0
    html = _build(tmp_path, monkeypatch).read_text()  # same db path, so the GA4 rows are included
    d = _data(html)
    assert d["affiliate"]["current"] == 13 and d["affiliate"]["by_product"]
    pg = d["pages"]["best-x-monitors"]["affiliate"]
    assert pg["clicks28"] == 4 and pg["clicks90"] == 5 and pg["products"][0]["product"] == "Cam <b>"
    assert d["windows"]["28"]["pages"][0]["product_clicks"] == 4
    assert "<b>" not in re.search(r'type="application/json">(.*?)</script>', html, re.S).group(1)
    assert any(w["product_clicks"] for w in d["weeks"])


def test_properties_keep_their_own_rows(tmp_path):
    con = connect(tmp_path / "x.sqlite")
    r = {"date": "2026-11-01", "page_path": "/blog/a", "product": "", "asin": "", "clicks": 2}
    save_ga4_range(con, "410797663", "2026-11-01", "2026-11-02", [r], False)
    save_ga4_range(con, "562537573", "2026-11-01", "2026-11-02", [{**r, "page_path": "/a", "clicks": 3}], True)
    save_ga4_range(con, "562537573", "2026-11-01", "2026-11-02", [{**r, "page_path": "/a", "clicks": 3}], True)  # rerun
    assert [tuple(x) for x in con.execute("SELECT property, SUM(clicks) FROM ga4_clicks GROUP BY property ORDER BY property")] == \
        [("410797663", 2), ("562537573", 3)]


def test_v05_database_is_migrated_with_its_property(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE ga4_clicks (date TEXT NOT NULL, page_path TEXT NOT NULL, product TEXT NOT NULL,
          asin TEXT NOT NULL, clicks INTEGER NOT NULL, PRIMARY KEY (date, page_path, product, asin));
        CREATE TABLE ga4_fetches (id INTEGER PRIMARY KEY, property TEXT NOT NULL, date_start TEXT NOT NULL,
          date_end TEXT NOT NULL, rows INTEGER NOT NULL, by_product INTEGER NOT NULL, fetched_at TEXT NOT NULL);
        INSERT INTO ga4_fetches VALUES (1, '410797663', '2026-07-08', '2026-11-04', 2, 1, 'x');
        INSERT INTO ga4_clicks VALUES ('2026-10-06', '/blog/a', '', '', 2), ('2026-11-03', '/blog/b', 'Ray-Ban', '', 1);
    """)
    old.commit(); old.close()
    con = connect(path)
    assert [tuple(x) for x in con.execute("SELECT property, date, clicks FROM ga4_clicks ORDER BY date")] == \
        [("410797663", "2026-10-06", 2), ("410797663", "2026-11-03", 1)]
    connect(path)  # a second open is a no-op
    assert con.execute("SELECT COUNT(*) FROM ga4_clicks").fetchone()[0] == 2
