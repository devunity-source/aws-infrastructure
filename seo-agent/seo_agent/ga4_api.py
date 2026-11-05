"""GA4 Data API: product button clicks per article, read-only.

The blog sends an `affiliate_click` event from every product button (see Base.astro).
This counts those events per day and page, and per product when the custom dimensions
exist. It counts clicks only. Purchases come from Amazon Associates reports, never
from clicks.

Setup, once:
- In GA4 Admin > Property access management, add the service account's email as a Viewer.
- In GA4 Admin > Custom definitions, add event-scoped custom dimensions for the
  `product_name` and `asin` parameters. Without them, clicks are still counted per page.
"""
from __future__ import annotations

from .gsc_api import Client, GSCAPIError

API = "https://analyticsdata.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
EVENT = "affiliate_click"
PAGE_DIMS = ["date", "pagePath"]
PRODUCT_DIMS = PAGE_DIMS + ["customEvent:product_name", "customEvent:asin"]
NOT_SET = "(not set)"
ROW_LIMIT = 100_000


class GA4Client(Client):
    forbidden_hint = (" Add the service account's email as a Viewer in GA4 Admin > Property access "
                      "management, and check the numeric property ID (not the G- measurement ID).")

    def report(self, prop: str, start: str, end: str, dims: list[str]) -> list[dict]:
        url = f"{API}/properties/{prop}:runReport"
        out, offset = [], 0
        while True:
            body = {"dateRanges": [{"startDate": start, "endDate": end}],
                    "dimensions": [{"name": d} for d in dims],
                    "metrics": [{"name": "eventCount"}],
                    "dimensionFilter": {"filter": {"fieldName": "eventName",
                                                   "stringFilter": {"matchType": "EXACT", "value": EVENT}}},
                    "limit": ROW_LIMIT, "offset": offset}
            resp = self._request("POST", url, body)
            rows = resp.get("rows", [])
            out.extend(rows)
            offset += len(rows)
            if not rows or offset >= int(resp.get("rowCount", 0)):
                return out

    def clicks(self, prop: str, start: str, end: str) -> tuple[list[dict], bool]:
        """Rows as {date, page_path, product, asin, clicks}, and whether products are known.
        Falls back to per-page counts when the custom dimensions aren't registered."""
        try:
            rows, dims = self.report(prop, start, end, PRODUCT_DIMS), PRODUCT_DIMS
        except GSCAPIError as e:
            if "customEvent" not in str(e):
                raise
            rows, dims = self.report(prop, start, end, PAGE_DIMS), PAGE_DIMS
        return [to_record(r, dims) for r in rows], dims == PRODUCT_DIMS


def to_record(row: dict, dims: list[str]) -> dict:
    vals = dict(zip(dims, (v.get("value", "") for v in row.get("dimensionValues", []))))
    d = vals.get("date", "")
    clean = lambda v: "" if v in (None, NOT_SET) else v
    return {"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d,
            "page_path": vals.get("pagePath", ""),
            "product": clean(vals.get("customEvent:product_name")),
            "asin": clean(vals.get("customEvent:asin")),
            "clicks": int(float(row.get("metricValues", [{}])[0].get("value", 0) or 0))}
