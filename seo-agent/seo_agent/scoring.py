"""Transparent 0-100 opportunity score for blog articles.

Every component is 0..1 and every non-trivial component emits a plain-English
reason. Anything inferred (query-to-page mapping from CSV exports) is labelled
as inferred so nobody mistakes it for observed data.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

WORD = re.compile(r"[a-z0-9$]+")


@dataclass
class PageScore:
    page: str
    score: float
    components: dict
    reasons: list[str]
    flags: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    top_queries: list[dict] = field(default_factory=list)


# ---------- page classification ----------

def slug_of(url: str, cfg: dict) -> str | None:
    """Return the article slug, or None if the URL isn't a blog article."""
    p = urlparse(url)
    if p.fragment or p.query:
        return None
    path = p.path.rstrip("/")
    prefix = cfg["article_prefix"].rstrip("/")
    if not path.startswith(prefix + "/"):
        return None
    if any(path.startswith(x.rstrip("/")) for x in cfg["non_article_prefixes"]):
        return None
    slug = path[len(prefix) + 1:]
    if "/" in slug or slug in cfg["non_article_slugs"]:
        return None
    return slug


# ---------- query classification ----------

def is_brand(q: str, cfg: dict) -> bool:
    return any(b in q for b in cfg["brand_terms"])


def _template_parts(q: str, cfg: dict) -> tuple[str, str] | None:
    """Split a 'best ...' query into (product, off-topic variant) or None.

    'best gaming mouse for cyclists'     -> ('gaming mouse', 'cyclists')
    'best pet friendly thunderbolt hub'  -> ('thunderbolt hub', 'pet friendly')
    'best ergonomic split keyboard'      -> None (normal modifier)
    """
    m = re.match(r"^best (.+?) for (.+)$", q)
    if m:
        aud = m.group(2).strip()
        return None if aud in cfg["relevant_audiences"] else (m.group(1), aud)
    m = re.match(r"^best (.+) (\S+ \S+)$", q)
    if m:
        mod = m.group(1).strip()
        return None if mod in cfg["relevant_modifiers"] else (m.group(2), mod)
    return None


def template_families(queries: list[str], cfg: dict) -> set[str]:
    """Find product families padded with off-topic audiences or modifiers.

    Example: 'best gaming mouse for cyclists', '... for yoga practitioners',
    'best rust proof thunderbolt hub', 'best thunderbolt hub for toddlers'.
    Real searchers rarely produce families like this at volume, so the scorer
    treats them as low signal rather than as content gaps.
    """
    fam: dict[str, set[str]] = defaultdict(set)
    parts = {}
    for q in queries:
        pt = _template_parts(q, cfg)
        if pt:
            parts[q] = pt
            fam[pt[0]].add(pt[1])
    # 'thunderbolt hub' and 'cordless thunderbolt hub' should share a family:
    # merge by the last two words of the product phrase.
    tail = lambda prod: " ".join(prod.split()[-2:])
    merged: dict[str, set[str]] = defaultdict(set)
    for prod, variants in fam.items():
        merged[tail(prod)] |= variants
    bad = {k for k, v in merged.items() if len(v) >= cfg["template_family_min"]}
    return {q for q, (prod, _) in parts.items() if tail(prod) in bad}


def is_commercial(q: str, cfg: dict) -> bool:
    words = set(WORD.findall(q))
    return bool(words & set(cfg["commercial_modifiers"])) or "$" in q


# ---------- query -> page inference ----------

def page_terms(slug: str, cfg: dict) -> tuple[list[list[str]], list[str]]:
    toks = [t for t in slug.split("-") if t and t not in cfg["slug_stopwords"]]
    syn = cfg["synonyms"]
    heads = [syn[t] for t in toks if t in syn]
    quals = [t for t in toks if t not in syn]
    if not heads:  # e.g. fitbit-air-2026: distinctive tokens become heads
        heads, quals = [[t] for t in toks if len(t) >= 4], []
    return heads, quals


def _has(words: list[str], qtext: str, term: str, prefix: bool) -> bool:
    if " " in term:
        return term in qtext
    if prefix and len(term) >= 4:
        return any(w.startswith(term) for w in words)
    return any(w == term or w == term + "s" or w + "s" == term for w in words)


def match_strength(q: str, heads, quals) -> tuple[int, float]:
    """(points, share of the page's head terms hit). Compared as a tuple, so
    'google fitbit air' prefers /fitbit-air-2026 over /google-io-... ."""
    words = WORD.findall(q)
    head_hits = sum(1 for g in heads if any(_has(words, q, t, False) for t in g))
    if not head_hits:
        return (0, 0.0)
    pts = head_hits * 2 + sum(1 for t in quals if _has(words, q, t, True))
    return (pts, head_hits / len(heads))


def assign_queries(slugs: list[str], queries: list[dict], cfg: dict):
    """Map each query to its best-matching article(s). Ties = shared query."""
    terms = {s: page_terms(s, cfg) for s in slugs}
    by_page: dict[str, list[dict]] = defaultdict(list)
    shared: dict[tuple, list[dict]] = defaultdict(list)
    for q in queries:
        scores = {s: match_strength(q["key"], *terms[s]) for s in slugs}
        best = max(scores.values(), default=(0, 0.0))
        if best[0] == 0:
            continue
        winners = tuple(sorted(s for s, v in scores.items() if v == best))
        for s in winners:
            by_page[s].append(q)
        if len(winners) > 1:
            shared[winners].append(q)
    return by_page, shared


# ---------- components ----------

def expected_ctr(pos: float, cfg: dict) -> float:
    r = max(1, round(pos))
    if str(r) in cfg["ctr_curve"]:
        return cfg["ctr_curve"][str(r)]
    return cfg["ctr_curve_11_20"] if r <= 20 else cfg["ctr_curve_beyond_20"]


def position_component(pos: float, cfg: dict) -> float:
    b = cfg["position_band"]
    if b["sweet_min"] <= pos <= b["sweet_max"]:
        return 1.0
    if pos < b["sweet_min"]:
        return b["top"]
    return b["near"] if pos <= b["near_max"] else b["far"]


def score_pages(pages: list[dict], queries: list[dict], cfg: dict,
                previous: dict[str, dict] | None = None,
                existing_slugs: set[str] | None = None) -> tuple[list[PageScore], dict]:
    """pages/queries: dicts with key, clicks, impressions, ctr, position.

    existing_slugs: slugs that have a post in the blog. When given, scored pages
    without a post get a dead_url flag. None skips the check.
    """
    w = cfg["weights"]
    articles = {}
    for p in pages:
        s = slug_of(p["key"], cfg)
        if s:
            articles[s] = p

    nonbrand = [q for q in queries if not is_brand(q["key"], cfg)]
    templated = template_families([q["key"] for q in nonbrand], cfg)
    by_page, _ = assign_queries(list(articles), nonbrand, cfg)
    # Cannibalisation only on real-looking queries; templated noise inflates overlap.
    _, shared = assign_queries(list(articles), [q for q in nonbrand if q["key"] not in templated], cfg)

    results = []
    for slug, p in articles.items():
        imp, clicks, pos, ctr = p["impressions"], p["clicks"], p["position"], p["ctr"]
        reasons, flags = [], []
        pq = sorted(by_page.get(slug, []), key=lambda q: -q["impressions"])
        q_imp = sum(q["impressions"] for q in pq) or 0
        tmpl_imp = sum(q["impressions"] for q in pq if q["key"] in templated)
        comm_imp = sum(q["impressions"] for q in pq if is_commercial(q["key"], cfg))

        # visibility
        vis = min(1.0, math.sqrt(imp / cfg["visibility_ref_impressions"]))

        # CTR gap vs position baseline, damped when sample is small
        exp = expected_ctr(pos, cfg)
        gap = max(0.0, (exp - ctr) / exp) if exp else 0.0
        conf = min(1.0, imp / cfg["min_impressions_for_ctr"])
        ctr_gap = gap * conf
        if imp >= cfg["min_impressions_for_ctr"] and gap > 0.5:
            reasons.append(f"CTR {ctr:.2%} on {imp:,} impressions at avg position {pos:.1f}; "
                           f"pages at that position often get around {exp:.1%}. "
                           "Title and meta description are the first suspects.")

        # position band
        pb = position_component(pos, cfg)
        if pb == 1.0:
            reasons.append(f"Avg position {pos:.1f} sits in the 4-20 band where on-page "
                           "improvements most often move rankings.")
        elif pos > cfg["position_band"]["sweet_max"]:
            reasons.append(f"Avg position {pos:.1f} is beyond page 2; snippet tweaks won't help "
                           "much until relevance or depth improves.")

        # commercial intent
        slug_comm = slug.startswith("best-") or "-vs-" in slug
        q_comm = (comm_imp / q_imp) if q_imp else 0.0
        com = max(0.6 if slug_comm else 0.0, q_comm)
        if slug_comm:
            reasons.append("Commercial page (best-of or comparison) so affiliate value is plausible.")

        # query relevance: on-topic, non-templated share of inferred impressions
        if q_imp:
            rel = 1 - tmpl_imp / q_imp
            if tmpl_imp / q_imp >= 0.3:
                flags.append("templated_queries")
                reasons.append(f"{tmpl_imp / q_imp:.0%} of inferred query impressions come from "
                               "templated 'best X for <random audience>' queries. Low signal: "
                               "don't chase them with new sections.")
        else:
            rel = 0.5  # unknown, stay neutral
            flags.append("no_query_data")

        stale = [q for q in pq if re.search(r"\b(2023|2024|2025)\b", q["key"])]
        stale_imp = sum(q["impressions"] for q in stale)
        if q_imp and stale_imp / q_imp >= 0.15:
            flags.append("year_in_queries")
            reasons.append(f"{stale_imp:,} impressions come from queries with an older year "
                           f"(e.g. '{stale[0]['key']}'). Searchers want a current guide, so check "
                           "the title year and the freshness of picks.")

        if imp >= 300 and clicks == 0:
            flags.append("zero_clicks")

        if existing_slugs is not None and slug not in existing_slugs:
            flags.append("dead_url")
            reasons.insert(0, "No post with this slug exists in the blog, so the URL returns 404 or 410 "
                              "unless a redirect covers it. Restore, redirect or retire it before any "
                              "on-page work.")

        comps = {"visibility": vis, "ctr_gap": ctr_gap, "position_band": pb,
                 "commercial_intent": com, "query_relevance": rel}
        total = 100 * sum(w[k] * v for k, v in comps.items())

        if previous and p["key"] in previous:
            prev = previous[p["key"]]
            if prev["impressions"] >= 50 and imp < 0.7 * prev["impressions"]:
                flags.append("declining")
                reasons.append(f"Impressions fell from {prev['impressions']:,} to {imp:,} "
                               "versus the previous import.")

        results.append(PageScore(
            page=p["key"], score=round(total, 1),
            components={k: round(v, 3) for k, v in comps.items()},
            reasons=reasons, flags=flags,
            metrics={"clicks": clicks, "impressions": imp, "ctr": ctr, "position": pos,
                     "inferred_query_impressions": q_imp},
            top_queries=[{"query": q["key"], "impressions": q["impressions"],
                          "clicks": q["clicks"], "position": q["position"],
                          "templated": q["key"] in templated} for q in pq[:10]]))

    # cannibalisation: material shared query volume between two articles
    cannibal = []
    for pair, qs in shared.items():
        imp = sum(q["impressions"] for q in qs)
        if imp >= 20:
            cannibal.append({"pages": list(pair), "shared_impressions": imp,
                             "examples": [q["key"] for q in sorted(qs, key=lambda q: -q["impressions"])[:5]],
                             "basis": "inferred from query wording (CSV has no query x page join)"})
    cannibal.sort(key=lambda c: -c["shared_impressions"])
    for c in cannibal:
        for r in results:
            if slug_of(r.page, cfg) in c["pages"]:
                other = [s for s in c["pages"] if s != slug_of(r.page, cfg)]
                r.flags.append("possible_cannibalisation")
                r.reasons.append(f"Possible overlap with /{', /'.join(other)} on "
                                 f"{c['shared_impressions']:,} impressions of shared queries "
                                 "(inferred). Confirm with page+query API data before merging.")

    results.sort(key=lambda r: -r.score)
    excluded = [p["key"] for p in pages if not slug_of(p["key"], cfg)]
    summary = {"articles_scored": len(results), "excluded_non_articles": excluded,
               "dead_urls": [r.page for r in results if "dead_url" in r.flags],
               "brand_queries": [q["key"] for q in queries if is_brand(q["key"], cfg)],
               "templated_query_count": len(templated),
               "templated_impressions": sum(q["impressions"] for q in nonbrand if q["key"] in templated),
               "cannibalisation": cannibal}
    return results, summary
