"""Scoring configuration. Every number here is a tunable heuristic, not a benchmark.

Override any key with a JSON file: `seo-agent score --config my.json`.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

DEFAULTS: dict = {
    "site": "https://digitalapricot.io",
    "article_prefix": "/",
    # Where articles used to live -> where they live now. Old URLs (Search Console history,
    # old GA4 page paths) are rewritten to the new ones, so a moved article keeps one history.
    "legacy_urls": {"https://protocloudsolutions.com/blog/": "https://digitalapricot.io/"},
    "non_article_slugs": ["about", "contact", "privacy", "disclosure", "terms", "search", "404"],
    "non_article_prefixes": ["/category/", "/tags/", "/tag/", "/author/"],
    "brand_terms": ["digital apricot", "digitalapricot", "protocloud", "proto cloud", "protocloudsolutions"],

    # Weights must sum to 1. Each component is 0..1, so score = 100 * weighted sum.
    "weights": {
        "visibility": 0.25,       # are people already seeing this page?
        "ctr_gap": 0.25,          # CTR below what its position usually earns
        "position_band": 0.20,    # 4-20 is where on-page work moves the needle
        "commercial_intent": 0.15,
        "query_relevance": 0.15,  # share of impressions from on-topic, non-templated queries
    },
    "visibility_ref_impressions": 1500,   # sqrt-scaled; this many = 1.0
    "min_impressions_for_ctr": 200,        # below this, CTR gap is scaled down

    # Rough organic CTR baseline by rounded position. Deliberately conservative.
    # Used only to say "below what this position usually gets", never to predict uplift.
    "ctr_curve": {"1": 0.25, "2": 0.14, "3": 0.09, "4": 0.06, "5": 0.045, "6": 0.035,
                  "7": 0.028, "8": 0.022, "9": 0.018, "10": 0.015},
    "ctr_curve_11_20": 0.008,
    "ctr_curve_beyond_20": 0.003,

    "position_band": {"sweet_min": 4, "sweet_max": 20, "top": 0.35, "near": 0.5,
                      "near_max": 30, "far": 0.1},

    "commercial_modifiers": ["best", "vs", "review", "under", "cheap", "budget",
                             "top", "buy", "price", "deal", "alternative", "worth"],

    # "for <audience>" suffixes that are genuinely on-brand for a dev-gear blog.
    "relevant_audiences": ["programmer", "programmers", "programming", "developer",
                           "developers", "coding", "coders", "work", "office",
                           "remote work", "remote workers", "working from home",
                           "gaming", "productivity", "students", "mac", "macbook",
                           "linux", "windows", "zoom", "video calls", "calls", "meetings",
                           "streaming", "home office", "small hands", "large hands"],
    # Modifiers that are normal for this niche ("best wireless mouse").
    "relevant_modifiers": ["ergonomic", "wireless", "wired", "budget", "cheap", "affordable",
                           "quiet", "silent", "mechanical", "split", "vertical", "4k", "5k",
                           "ultrawide", "portable", "usb", "usb-c", "thunderbolt", "gaming",
                           "lightweight", "bluetooth", "low profile", "compact", "75%", "60%",
                           "tkl", "hall effect", "noise cancelling", "ai", "smart", "1080p"],
    # A "best <product> for <X>" / "best <X> <product>" family with at least this many distinct
    # off-audience suffixes is treated as templated long-tail (low signal).
    "template_family_min": 5,

    # Topic synonyms used to infer which page a query belongs to.
    "synonyms": {
        "mice": ["mouse", "mice"], "mouse": ["mouse", "mice"],
        "webcams": ["webcam", "webcams", "camera", "cameras", "cam"],
        "monitors": ["monitor", "monitors", "display", "displays", "screen"],
        "keyboards": ["keyboard", "keyboards"],
        "glasses": ["glasses", "glass", "spectacles", "eyewear", "brille"],
        "docks": ["dock", "docks", "hub", "hubs", "thunderbolt"],
        "chargers": ["charger", "chargers"],
        "microphones": ["microphone", "microphones", "mic", "mics"],
        "earbuds": ["earbuds", "earbud", "earphones"],
        "headphones": ["headphones", "headset", "headphone"],
        "laptops": ["laptop", "laptops", "notebook", "macbook"],
        "switches": ["switch", "switches"],
        "banks": ["power bank", "power banks", "powerbank"],
    },
    "slug_stopwords": ["best", "for", "the", "and", "to", "of", "a", "how", "in",
                       "with", "vs", "is", "2024", "2025", "2026", "choose", "your",
                       "ai", "how", "works", "really", "platform", "cloud", "devops"],
}


def load(path: str | Path | None = None) -> dict:
    cfg = deepcopy(DEFAULTS)
    if path:
        override = json.loads(Path(path).read_text())
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    total = sum(cfg["weights"].values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total:.3f}")
    return cfg
