"""Search Console API path: client, storage and CLI, against a fake session (no network)."""
import json

import pytest

from seo_agent import cli
from seo_agent import config as cfgmod
from seo_agent.gsc_api import PAGE_DIMS, ROW_DIMS, Client, GSCAPIError, load_key, to_records
from seo_agent.scoring import score_pages
from seo_agent.storage import (aggregate, build_window_import, connect, fetch_log,
                               observed_query_pages, save_api_day)

CFG = {**cfgmod.load(), "site": "https://digitalapricot.io"}
A = "https://digitalapricot.io/best-x-monitors"
B = "https://digitalapricot.io/best-y-monitors"


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class Session:
    """Replays queued responses and records every request."""
    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def _next(self, method, url, body):
        self.calls.append((method, url, body))
        r = self.queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, url, timeout=None):
        return self._next("GET", url, None)

    def post(self, url, json=None, timeout=None):
        return self._next("POST", url, json)


def row(keys, clicks=0, impressions=10, position=5.0):
    return {"keys": keys, "clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0, "position": position}


# ---------- client ----------

def test_query_paginates_until_a_short_page():
    s = Session(Resp(body={"rows": [row(["a"]), row(["b"])]}), Resp(body={"rows": [row(["c"])]}))
    rows = list(Client(s, row_limit=2).query("sc-domain:digitalapricot.io", "2026-11-01", "2026-11-01", ["query"]))
    assert [r["keys"][0] for r in rows] == ["a", "b", "c"]
    assert [c[2]["startRow"] for c in s.calls] == [0, 2]
    body = s.calls[0][2]
    assert body["dataState"] == "final" and body["type"] == "web" and body["rowLimit"] == 2


def test_site_url_is_encoded_in_the_path():
    s = Session(Resp(body={}))
    list(Client(s).query("https://digitalapricot.io/", "2026-11-01", "2026-11-01", ["page"]))
    assert "/sites/https%3A%2F%2Fdigitalapricot.io%2F/searchAnalytics/query" in s.calls[0][1]


def test_retries_on_rate_limit_and_server_errors():
    slept = []
    s = Session(Resp(429, headers={"Retry-After": "7"}), Resp(503), OSError("reset"),
                Resp(body={"rows": [row(["a"])]}))
    rows = list(Client(s, sleep=slept.append).query("sc-domain:x", "2026-11-01", "2026-11-01", ["query"]))
    assert len(rows) == 1 and slept == [7.0, 4, 8]


def test_gives_up_after_max_tries():
    s = Session(*[Resp(500)] * 3)
    with pytest.raises(GSCAPIError, match="HTTP 500"):
        list(Client(s, sleep=lambda _: None, max_tries=3).query("sc-domain:x", "d", "d", ["query"]))


def test_permission_error_explains_the_fix_and_does_not_retry():
    s = Session(Resp(403, {"error": {"message": "User does not have sufficient permission"}}))
    with pytest.raises(GSCAPIError, match="Add the service account"):
        Client(s, sleep=lambda _: pytest.fail("should not retry")).sites()
    assert len(s.calls) == 1


def test_auth_failure_becomes_a_clear_error():
    RefreshError = type("RefreshError", (Exception,), {"__module__": "google.auth.exceptions"})
    s = Session(RefreshError("invalid_grant: Invalid JWT Signature"))
    with pytest.raises(GSCAPIError, match="authentication failed: invalid_grant"):
        Client(s, sleep=lambda _: pytest.fail("should not retry")).sites()


def test_page_totals_are_not_split_by_device_or_country():
    # Splitting by device or country made Google drop 45% of impressions in real data.
    assert PAGE_DIMS == ["date", "page"]


def test_to_records_names_the_dimensions():
    recs = to_records([row(["2026-11-01", A, "q", "MOBILE", "usa"], clicks=1, impressions=4)], ROW_DIMS)
    assert recs == [{"date": "2026-11-01", "page": A, "query": "q", "device": "MOBILE", "country": "usa",
                     "clicks": 1, "impressions": 4, "ctr": 0.25, "position": 5.0}]


def test_load_key_accepts_path_or_json_and_rejects_other_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    k = tmp_path / "k.json"
    k.write_text(json.dumps({"type": "service_account", "client_email": "x@y"}))
    assert load_key(str(k))["client_email"] == "x@y"
    assert load_key(k.read_text())["client_email"] == "x@y"
    with pytest.raises(GSCAPIError, match="not a service account"):
        load_key('{"type": "authorized_user"}')
    with pytest.raises(GSCAPIError, match="no service account key"):
        load_key(None)


# ---------- storage ----------

def _store_day(con, day, rows, pages, site="sc-domain:digitalapricot.io"):
    save_api_day(con, site, day, to_records(rows, ROW_DIMS), to_records(pages, PAGE_DIMS))


def test_window_aggregates_weighted_position_and_complete_page_totals(tmp_path):
    con = connect(tmp_path / "db.sqlite")
    # Page totals include anonymised traffic the query rows don't show.
    _store_day(con, "2026-11-01", [row(["2026-11-01", A, "q1", "MOBILE", "usa"], 1, 10, 4.0)],
               [row(["2026-11-01", A], 2, 30, 4.0)])
    _store_day(con, "2026-11-02", [row(["2026-11-02", A, "q1", "DESKTOP", "usa"], 0, 10, 8.0)],
               [row(["2026-11-02", A], 0, 10, 8.0)])
    iid, created, t = build_window_import(con, "sc-domain:digitalapricot.io", "2026-11-01", "2026-11-02")
    assert created and t == {"clicks": 2, "impressions": 40, "pages": 1, "queries": 1}
    page = aggregate(con, iid, "page")[0]
    assert page["impressions"] == 40 and page["ctr"] == pytest.approx(0.05)
    assert page["position"] == pytest.approx((4.0 * 30 + 8.0 * 10) / 40)
    q = aggregate(con, iid, "query")[0]
    assert q["impressions"] == 20 and q["position"] == pytest.approx(6.0)
    assert {r["key"] for r in aggregate(con, iid, "date")} == {"2026-11-01", "2026-11-02"}
    assert aggregate(con, iid, "device") == []  # page totals are not split by device
    again = build_window_import(con, "sc-domain:digitalapricot.io", "2026-11-01", "2026-11-02")
    assert again[:2] == (iid, False)


def test_saving_a_day_twice_replaces_it(tmp_path):
    con = connect(tmp_path / "db.sqlite")
    for _ in range(2):
        _store_day(con, "2026-11-01", [row(["2026-11-01", A, "q", "MOBILE", "usa"])],
                   [row(["2026-11-01", A])])
    assert con.execute("SELECT COUNT(*) FROM gsc_rows").fetchone()[0] == 1
    assert fetch_log(con, "sc-domain:digitalapricot.io") == {"2026-11-01": 1}


# ---------- scoring with the observed join ----------

def test_observed_mapping_beats_inference_and_finds_real_overlap():
    pages = [dict(key=A, clicks=0, ctr=0.0, impressions=500, position=9),
             dict(key=B, clicks=0, ctr=0.0, impressions=300, position=12)]
    # "acme 27 inch" has no topic words, so inference could never map it.
    observed = {A: [dict(key="acme 27 inch", clicks=0, ctr=0.0, impressions=40, position=9)],
                B: [dict(key="acme 27 inch", clicks=0, ctr=0.0, impressions=15, position=12)]}
    queries = [dict(key="acme 27 inch", clicks=0, ctr=0.0, impressions=55, position=10)]
    inferred, s1 = score_pages(pages, queries, CFG)
    assert all(not r.top_queries for r in inferred) and s1["query_mapping"] == "inferred"
    res, s2 = score_pages(pages, queries, CFG, observed=observed)
    a = next(r for r in res if r.page == A)
    assert a.top_queries[0]["query"] == "acme 27 inch" and s2["query_mapping"] == "observed"
    assert s2["cannibalisation"][0]["shared_impressions"] == 55
    assert "observed in Search Console" in s2["cannibalisation"][0]["basis"]
    assert "possible_cannibalisation" in a.flags
    assert not any("(inferred)" in x for x in a.reasons)


# ---------- CLI end to end ----------

def _fake_api(calls):
    """Answers each (day, dims) query with one row on page A."""
    class Fake:
        def query(self, site, start, end, dims):
            calls.append((start, tuple(dims)))
            keys = {"date": start, "page": A, "query": "best x monitor", "device": "MOBILE", "country": "usa"}
            return iter([row([keys[d] for d in dims], clicks=1, impressions=20, position=7.0)])
    return Fake()


def test_cli_fetch_is_incremental_then_window_and_score(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "make_client", lambda key: _fake_api(calls))
    db = str(tmp_path / "x.sqlite")
    args = ["--db", db, "fetch", "--site", "sc-domain:digitalapricot.io", "--start", "2026-10-01", "--end", "2026-10-03"]
    assert cli.main(args) == 0
    assert len(calls) == 6  # 3 days x (query rows + page totals)
    assert cli.main(args) == 0 and len(calls) == 6  # nothing new to fetch
    assert "nothing to fetch" in capsys.readouterr().out
    assert cli.main(["--db", db, "window", "--days", "3"]) == 0
    assert "2026-10-01 to 2026-10-03" in capsys.readouterr().out
    posts = tmp_path / "posts"; posts.mkdir(); (posts / "best-x-monitors.md").write_text("x")
    out = tmp_path / "s.json"
    assert cli.main(["--db", db, "score", "--posts-dir", str(posts), "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["summary"]["query_mapping"] == "observed"
    assert data["pages"][0]["metrics"]["impressions"] == 60
    assert data["pages"][0]["top_queries"][0]["query"] == "best x monitor"


def test_cli_refetches_recent_empty_days(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "make_client", lambda key: _fake_api(calls))
    monkeypatch.setattr(cli, "pacific_today", lambda: __import__("datetime").date(2026, 11, 4))
    db = str(tmp_path / "x.sqlite")
    con = connect(db)
    save_api_day(con, "sc-domain:digitalapricot.io", "2026-10-31", [], [])  # recent and empty: not final yet
    save_api_day(con, "sc-domain:digitalapricot.io", "2026-10-01", [], [])  # old and empty: a real zero day
    assert cli.main(["--db", db, "fetch", "--site", "sc-domain:digitalapricot.io",
                     "--start", "2026-10-01", "--end", "2026-10-31"]) == 0
    fetched = {d for d, _ in calls}
    assert "2026-10-31" in fetched and "2026-10-01" not in fetched


def test_score_days_picks_the_matching_window(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "make_client", lambda key: _fake_api(calls))
    db = str(tmp_path / "x.sqlite")
    assert cli.main(["--db", db, "fetch", "--site", "sc-domain:digitalapricot.io",
                     "--start", "2026-10-01", "--end", "2026-10-28"]) == 0
    # Build 7 then 28, then rebuild 7: same end date, so "latest" alone would be ambiguous.
    for d in (7, 28, 7):
        assert cli.main(["--db", db, "window", "--days", str(d)]) == 0
    for d, start in ((7, "2026-10-22"), (28, "2026-10-01")):
        out = tmp_path / f"s{d}.json"
        assert cli.main(["--db", db, "score", "--days", str(d), "--posts-dir", str(tmp_path),
                         "--json", str(out)]) == 0
        assert json.loads(out.read_text())["import"]["date_start"] == start
    assert cli.main(["--db", db, "score", "--days", "90"]) == 2  # no 90-day window built


def test_cli_window_needs_fetched_data(tmp_path):
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "window"]) == 2


def test_cli_fetch_needs_a_site(tmp_path, monkeypatch):
    monkeypatch.delenv("GSC_SITE", raising=False)
    assert cli.main(["--db", str(tmp_path / "x.sqlite"), "fetch"]) == 2


def test_cli_sites_reports_api_errors(tmp_path, monkeypatch, capsys):
    def boom(key):
        raise GSCAPIError("no service account key")
    monkeypatch.setattr(cli, "make_client", boom)
    assert cli.main(["sites"]) == 2
    assert "no service account key" in capsys.readouterr().err


def test_two_properties_share_a_day_and_old_urls_merge_into_new(tmp_path):
    """The blog moved from protocloudsolutions.com/blog to digitalapricot.io. Both properties
    are fetched; saving one doesn't wipe the other, and an article's two URLs score as one."""
    con = connect(tmp_path / "x.sqlite")
    old = "https://protocloudsolutions.com/blog/best-x-monitors"
    new = "https://digitalapricot.io/best-x-monitors"
    rec = lambda page, imp, pos: {"page": page, "query": "best x monitor", "device": "", "country": "",
                                  "clicks": 1, "impressions": imp, "ctr": 0.1, "position": pos}
    save_api_day(con, "https://protocloudsolutions.com/", "2026-11-01", [rec(old, 30, 8.0)],
                 [rec(old, 30, 8.0), rec("https://protocloudsolutions.com/services", 50, 3.0)])
    save_api_day(con, "sc-domain:digitalapricot.io", "2026-11-01", [rec(new, 10, 4.0)], [rec(new, 10, 4.0)])
    save_api_day(con, "sc-domain:digitalapricot.io", "2026-11-01", [rec(new, 10, 4.0)], [rec(new, 10, 4.0)])  # rerun
    assert con.execute("SELECT COUNT(*) FROM gsc_page_rows").fetchone()[0] == 3  # old day kept, new not doubled
    iid, _, t = build_window_import(con, "both", "2026-11-01", "2026-11-01")
    pages = {r["key"]: r for r in aggregate(con, iid, "page")}
    assert set(pages) == {new, "https://protocloudsolutions.com/services"}
    assert pages[new]["impressions"] == 40 and pages[new]["position"] == (30 * 8.0 + 10 * 4.0) / 40
    assert list(observed_query_pages(con, "2026-11-01", "2026-11-01")) == [new]
