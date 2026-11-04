"""Read the blog's own files: posts (frontmatter, headings, products, links) and
the nginx snippet that retires or redirects old URLs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$", re.M)
INTERNAL_LINK = re.compile(r"\]\((?:https?://protocloudsolutions\.com)?/blog/([a-z0-9-]+)/?(?:#[^)]*)?\)")
EXTERNAL_LINK = re.compile(r"\]\(https?://(?!protocloudsolutions\.com)[^)]+\)")
COMPONENT_OR_IMPORT = re.compile(r"^\s*(import\s.+|<[A-Za-z][^>]*/?>|</[A-Za-z]+>)\s*$", re.M)
# Pages under /blog/ that are not posts but are valid link targets.
SITE_PAGES = {"about", "contact", "privacy", "disclosure", "search", "category", "tags"}


@dataclass
class Post:
    slug: str
    path: str
    meta: dict
    headings: list[tuple[int, str]] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: int = 0
    word_count: int = 0

    @property
    def products(self) -> list[dict]:
        return self.meta.get("products") or []

    def get_date(self, key: str) -> date | None:
        v = self.meta.get(key)
        if isinstance(v, date):
            return v
        try:
            return date.fromisoformat(str(v)[:10]) if v else None
        except ValueError:
            return None


def parse_post(path: str | Path) -> Post:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"{path.name}: no frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]
    prose = COMPONENT_OR_IMPORT.sub("", body)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", re.sub(r"\]\([^)]*\)", "]", prose))
    return Post(
        slug=path.stem, path=str(path), meta=meta,
        headings=[(len(h), t) for h, t in HEADING.findall(body)],
        internal_links=list(dict.fromkeys(INTERNAL_LINK.findall(body))),
        external_links=len(EXTERNAL_LINK.findall(body)),
        word_count=len(words))


def load_posts(posts_dir: str | Path) -> dict[str, Post]:
    d = Path(posts_dir)
    return {p.stem: parse_post(p) for p in sorted(d.iterdir()) if p.suffix in (".md", ".mdx")}


# ---------- nginx rules ----------

RULE = re.compile(r"location\s*=\s*/blog/([a-z0-9-]+)/?\s*\{\s*return\s+(\d{3})(?:\s+([^;\s]+))?\s*;\s*\}")


def handled_urls(nginx_conf: str | Path | None) -> dict[str, str]:
    """slug -> how the server handles it, e.g. 'retired (410)' or 'redirects to /blog/x (301)'.
    Only exact-match return rules count. A missing file gives {}."""
    if not nginx_conf or not Path(nginx_conf).is_file():
        return {}
    out = {}
    for slug, code, target in RULE.findall(Path(nginx_conf).read_text(encoding="utf-8")):
        if code in ("410", "404"):
            out[slug] = f"retired ({code})"
        elif code in ("301", "302", "307", "308") and target:
            out[slug] = f"redirects to {target} ({code})"
    return out
