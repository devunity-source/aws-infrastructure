"""Rule-based content audit of blog posts, joined with search opportunity scores.

Every issue has an id, a severity (high, medium, low), a plain-English message and
the evidence behind it, so nothing is a black box. Rules are deterministic, so
confidence is not a separate field: an LLM-based reviewer can be added later
behind the same Issue shape.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from .content import SITE_PAGES, Post

SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
YEAR = re.compile(r"\b(20[12]\d)\b")


@dataclass
class Issue:
    id: str
    severity: str
    message: str
    evidence: str = ""


@dataclass
class ArticleAudit:
    slug: str
    title: str
    issues: list[Issue] = field(default_factory=list)
    opportunity: float | None = None
    priority: float = 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "issues": [asdict(i) for i in self.issues]}


def _rendered_title(p: Post, site_name: str) -> str:
    return p.meta.get("seoTitle") or f"{p.meta.get('title', '')} — {site_name}"


def audit_post(p: Post, posts: dict[str, Post], handled: dict[str, str], inbound: dict[str, set],
               today: date, site_name: str, score: dict | None = None) -> ArticleAudit:
    m = p.meta
    a = ArticleAudit(slug=p.slug, title=str(m.get("title", "")))
    add = lambda *args: a.issues.append(Issue(*args))

    # --- search snippet ---
    title = _rendered_title(p, site_name)
    if len(title) > 60:
        add("title_too_long", "medium", "The search title runs past about 60 characters, so Google may cut it off.",
            f"{len(title)} characters: {title}")
    desc = str(m.get("description", ""))
    if len(desc) > 160:
        add("description_too_long", "medium", "The description runs past about 160 characters and may be cut off.",
            f"{len(desc)} characters")
    elif len(desc) < 70:
        add("description_too_short", "low", "The description is short. Name the top picks or what the guide answers.",
            f"{len(desc)} characters")
    old_years = sorted({y for y in YEAR.findall(f"{m.get('title', '')} {m.get('seoTitle', '')}") if int(y) < today.year})
    if old_years:
        add("stale_year_in_title", "high", "The title names a past year, which looks out of date in search results.",
            f"mentions {', '.join(old_years)}")

    # --- freshness ---
    pub, upd = p.get_date("pubDate"), p.get_date("updatedDate")
    last = upd or pub
    if last and (today - last).days > 180:
        add("not_updated", "low", "No update in over six months. Check picks, prices and availability.",
            f"last changed {last.isoformat()}")

    # --- images ---
    if not m.get("heroImage"):
        add("no_hero_image", "low", "No hero image. Cards and social shares fall back to a placeholder.")
    elif not m.get("heroAlt"):
        add("hero_alt_missing", "medium", "The hero image has no alt text, which hurts accessibility and image search.",
            str(m.get("heroImage")))

    # --- links ---
    for target in p.internal_links:
        if target in posts or target in SITE_PAGES:
            continue
        if target in handled and handled[target].startswith("redirects"):
            add("link_through_redirect", "medium", "Links to a URL that redirects. Point it at the final page.",
                f"/blog/{target} {handled[target]}")
        else:
            add("broken_internal_link", "high", "Links to a page that doesn't exist.",
                f"/blog/{target}" + (f" is {handled[target]}" if target in handled else ""))
    if not inbound.get(p.slug):
        add("orphan", "medium", "No other post links here, so readers and crawlers rarely find it. "
            "Link to it from a related guide.")
    if len(p.internal_links) < 2:
        add("few_internal_links", "low", "Fewer than two links to other guides. Add related reading.",
            f"{len(p.internal_links)} internal link(s)")

    # --- depth and structure ---
    if p.word_count < 600:
        add("thin_content", "medium", "Under 600 words. Short guides struggle to rank for competitive searches.",
            f"{p.word_count} words")
    h2 = sum(1 for level, _ in p.headings if level == 2)
    if h2 < 3:
        add("few_headings", "low", "Fewer than three sections. Headings help skimming and build the table of contents.",
            f"{h2} H2 heading(s)")
    no_link = [pr.get("name", "?") for pr in p.products if not pr.get("asin") and not pr.get("url")]
    if no_link:
        add("product_search_link", "low", "Some products have no ASIN or retailer URL, so the button opens an "
            "Amazon search instead of the product.", ", ".join(no_link))

    # --- search performance ---
    if score:
        a.opportunity = score["score"]
        met, flags = score.get("metrics", {}), set(score.get("flags", []))
        imp, clicks, pos = met.get("impressions", 0), met.get("clicks", 0), met.get("position", 0)
        recently = upd and (today - upd).days <= 28
        if score["score"] >= 70 and clicks == 0 and imp >= 200:
            if recently:
                add("snippet_recently_changed", "low", "No clicks yet, but the page changed in the last 28 days. "
                    "Wait for new data before changing the title again.", f"updated {upd.isoformat()}")
            else:
                add("no_clicks_high_opportunity", "high", "Gets search impressions but no clicks. Rewrite the "
                    "title and description first.", f"{imp:,} impressions, position {pos:.1f}")
        if pos > 20 and imp >= 200:
            add("ranks_beyond_page_2", "medium", "Most impressions come from beyond page 2. A better title won't "
                "fix that. The page needs more depth or better matching to what people search.",
                f"average position {pos:.1f}")
        if "year_in_queries" in flags and str(today.year) not in title:
            add("year_queries_no_current_year", "medium", "Searchers add a year to these queries, but the title "
                "doesn't show the current one.")
        if "possible_cannibalisation" in flags:
            add("overlaps_another_page", "medium", "Shares searches with another page. Check which should rank.")

    sev = sum(SEVERITY_WEIGHT[i.severity] for i in a.issues)
    a.priority = round(sev * (1 + (a.opportunity or 0) / 100), 1)
    return a


def audit_posts(posts: dict[str, Post], handled: dict[str, str] | None = None,
                scores: dict[str, dict] | None = None, today: date | None = None,
                site_name: str = "Protocloud Reviews") -> list[ArticleAudit]:
    """scores: slug -> scored page dict (score, flags, metrics), from the latest import."""
    handled, scores, today = handled or {}, scores or {}, today or date.today()
    inbound: dict[str, set] = {}
    for p in posts.values():
        for t in p.internal_links:
            if t != p.slug:
                inbound.setdefault(t, set()).add(p.slug)
    out = [audit_post(p, posts, handled, inbound, today, site_name, scores.get(s)) for s, p in posts.items()]
    out.sort(key=lambda a: (-a.priority, a.slug))
    return out


def render_audit_md(audits: list[ArticleAudit], today: date, basis: str | None) -> str:
    counts = {s: sum(1 for a in audits for i in a.issues if i.severity == s) for s in SEVERITY_WEIGHT}
    L = [f"# Content audit ({today.isoformat()})", "",
         f"{len(audits)} posts audited. {counts['high']} high, {counts['medium']} medium and "
         f"{counts['low']} low severity issues."
         + (f" Search data: latest import ({basis} query mapping)." if basis else " No search data joined."),
         "", "| # | Post | Priority | Opportunity | High | Medium | Low |", "|---|---|---|---|---|---|---|"]
    for n, a in enumerate(audits, 1):
        c = {s: sum(1 for i in a.issues if i.severity == s) for s in SEVERITY_WEIGHT}
        opp = f"{a.opportunity:.0f}" if a.opportunity is not None else ""
        L.append(f"| {n} | {a.slug} | {a.priority} | {opp} | {c['high']} | {c['medium']} | {c['low']} |")
    for a in audits:
        if not a.issues:
            continue
        L += ["", f"## {a.slug}", ""]
        for i in sorted(a.issues, key=lambda i: -SEVERITY_WEIGHT[i.severity]):
            L.append(f"- **{i.severity}** `{i.id}`: {i.message}" + (f" ({i.evidence})" if i.evidence else ""))
    return "\n".join(L) + "\n"
