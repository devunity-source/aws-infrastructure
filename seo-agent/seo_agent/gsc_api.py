"""Google Search Console API client. Read-only, paginated, with retries.

Two queries per day, because Google drops anonymised queries from any result
grouped by query:

- ROW_DIMS (with query) gives the observed query x page join.
- PAGE_DIMS (date and page only) gives complete page totals, anonymised traffic included.

Keep PAGE_DIMS to date and page. Adding device or country makes Google apply the
same privacy filter it uses for queries: on protocloudsolutions.com, Aug to Nov
2026, page totals fell from 9,093 to 5,043 impressions and from 24 to 4 clicks.

Auth uses a service account key. google-auth and requests are optional
dependencies (`pip install -e '.[api]'`), imported only when a real session
is built, so the CSV path and the tests stay standard-library only.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import quote

API = "https://www.googleapis.com/webmasters/v3"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ROW_LIMIT = 25_000  # API maximum per call
ROW_DIMS = ["date", "page", "query", "device", "country"]
PAGE_DIMS = ["date", "page"]
RETRY_STATUS = {429, 500, 502, 503, 504}


class GSCAPIError(RuntimeError):
    pass


def load_key(key: str | None) -> dict:
    """Service account key from a path or raw JSON. Falls back to the
    GSC_SERVICE_ACCOUNT_JSON and GOOGLE_APPLICATION_CREDENTIALS env vars."""
    src = key or os.environ.get("GSC_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not src:
        raise GSCAPIError("no service account key: pass --key, or set GSC_SERVICE_ACCOUNT_JSON "
                          "or GOOGLE_APPLICATION_CREDENTIALS")
    text = src if src.lstrip().startswith("{") else Path(src).read_text(encoding="utf-8")
    info = json.loads(text)
    if info.get("type") != "service_account":
        raise GSCAPIError("the key is not a service account key")
    return info


def session_from_key(info: dict, scope: str = SCOPE):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError:
        raise GSCAPIError("google-auth and requests are needed for the API. "
                          "Install with: pip install -e '.[api]'") from None
    creds = service_account.Credentials.from_service_account_info(info, scopes=[scope])
    return AuthorizedSession(creds)


FORBIDDEN_HINT = (" Add the service account's email as a user on the Search Console property, "
                  "and check the site value with the `sites` command.")


def _error_message(resp, forbidden_hint: str = FORBIDDEN_HINT) -> str:
    try:
        msg = resp.json().get("error", {}).get("message", "")
    except ValueError:
        msg = (resp.text or "")[:200]
    hint = forbidden_hint if resp.status_code == 403 else ""
    if "has not been used in project" in msg or "it is disabled" in msg:
        # The API is off in the key's Google Cloud project. Google's message has the link to enable it.
        hint = " Enable the API at the link above, wait a few minutes, then run again."
    return f"HTTP {resp.status_code}: {msg.rstrip('.')}.{hint}"


class Client:
    forbidden_hint = FORBIDDEN_HINT

    def __init__(self, session, sleep: Callable[[float], None] = time.sleep,
                 max_tries: int = 5, row_limit: int = ROW_LIMIT, timeout: float = 60):
        self.session, self.sleep = session, sleep
        self.max_tries, self.row_limit, self.timeout = max_tries, row_limit, timeout

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        for attempt in range(1, self.max_tries + 1):
            try:
                if method == "GET":
                    resp = self.session.get(url, timeout=self.timeout)
                else:
                    resp = self.session.post(url, json=body, timeout=self.timeout)
            except OSError as e:  # requests' connection and timeout errors are OSErrors
                if attempt == self.max_tries:
                    raise GSCAPIError(f"network error after {attempt} tries: {e}") from None
                self.sleep(min(2 ** attempt, 60))
                continue
            except Exception as e:
                # A bad or revoked key fails while google-auth fetches a token.
                if type(e).__module__.startswith("google.auth"):
                    raise GSCAPIError(f"authentication failed: {e}. Check the key is current "
                                      "and not revoked.") from None
                raise
            if resp.status_code in RETRY_STATUS and attempt < self.max_tries:
                retry_after = (getattr(resp, "headers", None) or {}).get("Retry-After", "")
                self.sleep(float(retry_after) if retry_after.isdigit() else min(2 ** attempt, 60))
                continue
            if resp.status_code >= 400:
                raise GSCAPIError(_error_message(resp, self.forbidden_hint))
            return resp.json()
        raise GSCAPIError("unreachable")  # pragma: no cover

    def sites(self) -> list[dict]:
        """Properties this key can read, as {siteUrl, permissionLevel}."""
        return self._request("GET", f"{API}/sites").get("siteEntry", [])

    def query(self, site: str, start: str, end: str, dimensions: list[str],
              data_state: str = "final", search_type: str = "web") -> Iterator[dict]:
        """Yield every row for the range, following startRow pagination."""
        url = f"{API}/sites/{quote(site, safe='')}/searchAnalytics/query"
        start_row = 0
        while True:
            body = {"startDate": start, "endDate": end, "dimensions": dimensions,
                    "type": search_type, "dataState": data_state,
                    "rowLimit": self.row_limit, "startRow": start_row}
            rows = self._request("POST", url, body).get("rows", [])
            yield from rows
            if len(rows) < self.row_limit:
                return
            start_row += len(rows)


def to_records(rows: list[dict], dimensions: list[str]) -> list[dict]:
    """API rows -> flat dicts keyed by dimension name, with integer counts."""
    out = []
    for r in rows:
        rec = dict(zip(dimensions, r["keys"]))
        rec.update(clicks=int(round(r.get("clicks", 0))), impressions=int(round(r.get("impressions", 0))),
                   ctr=float(r.get("ctr", 0.0)), position=float(r.get("position", 0.0)))
        out.append(rec)
    return out
