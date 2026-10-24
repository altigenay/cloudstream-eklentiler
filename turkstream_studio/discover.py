"""Discovery: fetch a site and describe the card sections a provider must expose.

This is the deterministic half of the studio. It does not write Kotlin; it
produces `review.json` (what was found, one entry per repeated card block) and
`spec.json` (the provider identity and the main-page requests). A human or an
agent confirms the roles, `approve` freezes them into `decisions.json`, and
`build` packages the Kotlin implementation.

Everything here treats the fetched page as untrusted data.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import htmltree
from .htmltree import Node

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

HEADING_TAGS = ("h1", "h2", "h3", "h4")
MEDIA_RE = re.compile(r"https?://[^\s\"'<>]+?\.(?:m3u8|mp4|mpd)(?:\?[^\s\"'<>]*)?", re.I)
IFRAME_HINT_RE = re.compile(r"(?:player|embed|iframe|video)[-_]?(?:url|src|link)", re.I)
API_HINT_RE = re.compile(r"""["'](/[a-zA-Z0-9_\-/]*(?:api|ajax|graphql)[a-zA-Z0-9_\-/]*)["']""")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    text: str
    content_type: str
    elapsed_ms: int
    headers: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400 and bool(self.text)


def fetch(url: str, headers: dict | None = None, timeout: int = 25) -> FetchResult:
    request = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            encoding_header = (response.headers.get("Content-Encoding") or "").lower()
            if "gzip" in encoding_header:
                raw = gzip.decompress(raw)
            elif "deflate" in encoding_header:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            content_type = response.headers.get("Content-Type", "")
            charset = response.headers.get_content_charset()
            if not charset:
                match = re.search(rb"charset=[\"']?([\w-]+)", raw[:4096], re.I)
                charset = match.group(1).decode() if match else "utf-8"
            text = raw.decode(charset, errors="replace")
            return FetchResult(
                url=url,
                final_url=response.geturl(),
                status=response.status,
                text=text,
                content_type=content_type,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                headers=dict(response.headers),
            )
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return FetchResult(url, error.geturl() or url, error.code, body,
                           error.headers.get("Content-Type", ""),
                           int((time.monotonic() - started) * 1000))
    except Exception as error:  # network, TLS, timeout
        return FetchResult(url, url, 0, "", f"error: {error}",
                           int((time.monotonic() - started) * 1000))


def _title_of(node: Node) -> str:
    for attribute in ("title", "alt", "aria-label", "data-title"):
        value = node.attr(attribute).strip()
        if value:
            return value
    return node.text()


def _card_fields(card: Node, base_url: str) -> dict:
    link = card if card.tag == "a" and card.attr("href") else None
    if link is None:
        links = [n for n in card.iter() if n.tag == "a" and n.attr("href").strip()]
        links.sort(key=lambda n: len(n.text()), reverse=True)
        link = links[0] if links else None

    href = urllib.parse.urljoin(base_url, link.attr("href").strip()) if link else ""

    image = next((n for n in card.iter() if n.tag == "img"), None)
    poster = ""
    if image is not None:
        for attribute in ("data-src", "data-lazy-src", "data-original", "srcset", "src"):
            value = image.attr(attribute).strip()
            if value and not value.startswith("data:"):
                poster = urllib.parse.urljoin(base_url, value.split()[0].split(",")[0])
                break

    title = ""
    for selector in ("h1", "h2", "h3", "h4", ".title", "[class*=title]", "[class*=name]"):
        hit = card.select_first(selector)
        if hit and hit.text():
            title = hit.text()
            break
    if not title and link is not None:
        title = _title_of(link)
    if not title:
        title = _title_of(card)

    meta = ""
    for selector in (".episode", "[class*=episode]", "[class*=year]", "[class*=meta]", "small", "span"):
        hit = card.select_first(selector)
        if hit and hit.text() and hit.text() != title:
            meta = hit.text()[:80]
            break

    return {"title": title[:160], "href": href, "poster": poster, "meta": meta}


def _section_title(node: Node, signature: str) -> str:
    """Nearest heading before the block, else a readable class name."""
    parent = node.parent
    if parent is not None:
        siblings = parent.children
        try:
            index = siblings.index(node)
        except ValueError:
            index = -1
        for previous in reversed(siblings[:index] if index > 0 else []):
            if previous.tag in HEADING_TAGS and previous.text():
                return previous.text()[:120]
            heading = previous.select_first("h1, h2, h3, h4")
            if heading and heading.text():
                return heading.text()[:120]
    for attribute in ("data-title", "aria-label", "data-section"):
        if node.attr(attribute).strip():
            return node.attr(attribute).strip()[:120]
    cleaned = re.sub(r"[._-]+", " ", signature).strip()
    return cleaned or "bölüm"


def _region(node: Node) -> str:
    """Which page region the block lives in: nav, header, footer or main."""
    ancestor: Node | None = node
    while ancestor is not None:
        if ancestor.tag in ("nav", "header"):
            return "nav"
        if ancestor.tag == "footer":
            return "footer"
        ancestor = ancestor.parent
    return "main"


def _href_set(members: list[Node], base_url: str) -> set[str]:
    hrefs: set[str] = set()
    for member in members:
        for anchor in member.iter():
            if anchor.tag == "a" and anchor.attr("href").strip():
                hrefs.add(urllib.parse.urljoin(base_url, anchor.attr("href").strip()))
    return hrefs


def _score_group(members: list[Node], base_url: str) -> float:
    score = 0.0
    hrefs: set[str] = set()
    for member in members:
        anchors = [n for n in member.iter() if n.tag == "a" and n.attr("href").strip()]
        if anchors:
            score += 1.0
            for anchor in anchors:
                hrefs.add(urllib.parse.urljoin(base_url, anchor.attr("href").strip()))
        if any(n.tag == "img" for n in member.iter()):
            score += 0.6
        if member.select_first("h1, h2, h3, h4, .title, [class*=title]"):
            score += 0.4
    # Many identical links usually means a menu, not a catalog.
    if len(hrefs) < max(3, len(members) // 2):
        score *= 0.25
    return score + min(len(hrefs), 40) * 0.05


def discover(html: str, base_url: str, limit: int = 8) -> dict:
    tree = htmltree.parse(html)
    sections: list[dict] = []
    used_signatures: set[str] = set()

    candidates: list[tuple[float, Node, list[Node], str]] = []
    for node in tree.iter():
        children = node.element_children()
        if len(children) < 4:
            continue
        grouped: dict[str, list[Node]] = {}
        for child in children:
            if child.tag in ("script", "style", "br"):
                continue
            grouped.setdefault(child.signature(), []).append(child)
        for signature, members in grouped.items():
            if len(members) < 4:
                continue
            score = _score_group(members, base_url)
            if score < 2.0:
                continue
            candidates.append((score, node, members, signature))

    candidates.sort(key=lambda item: item[0], reverse=True)

    taken_roots: list[Node] = []
    covered: set[str] = set()
    host = urllib.parse.urlparse(base_url).netloc
    for score, container, members, signature in candidates:
        if len(sections) >= limit:
            break
        if signature in used_signatures:
            continue
        # Skip a block nested inside an already accepted, stronger block.
        ancestor = container
        nested = False
        while ancestor is not None:
            if ancestor in taken_roots:
                nested = True
                break
            ancestor = ancestor.parent
        if nested:
            continue

        hrefs = _href_set(members, base_url)
        # Menus, nav and footer repeat the same handful of category links.
        if covered and len(hrefs & covered) >= max(3, int(len(hrefs) * 0.6)):
            continue
        if hrefs and len(hrefs) <= 2:
            continue
        if hrefs and all(not urllib.parse.urlparse(url).path.strip("/") for url in hrefs):
            continue

        selector = members[0].path()
        region = _region(container)
        samples = [_card_fields(member, base_url) for member in members[:6]]
        samples = [sample for sample in samples if sample["href"] or sample["title"]]
        if not samples:
            continue
        used_signatures.add(signature)
        taken_roots.append(container)
        covered |= hrefs

        external = all(urllib.parse.urlparse(url).netloc not in ("", host) for url in hrefs) if hrefs else False
        with_images = sum(1 for member in members if any(n.tag == "img" for n in member.iter()))
        if region != "main" or external or len(hrefs) < 6 or with_images * 2 < len(members):
            suggested = "text"
        else:
            suggested = "media"

        sections.append(
            {
                "id": f"s{len(sections) + 1}",
                "title": _section_title(container, signature),
                "selector": selector,
                "container": container.path(),
                "card": signature,
                "region": region,
                "count": len(members),
                "score": round(score, 2),
                "include": True,
                "role": None,          # media | text | ignore  (confirmed by approve)
                "suggestedRole": suggested,
                "data": "",            # value the provider sends for this main-page request
                "samples": samples,
            }
        )

    scripts = "\n".join(node.text() for node in tree.iter() if node.tag == "script")
    media_urls = sorted(set(MEDIA_RE.findall(html)))[:20]
    iframes = [
        urllib.parse.urljoin(base_url, node.attr("src").strip())
        for node in tree.iter()
        if node.tag == "iframe" and node.attr("src").strip()
    ][:20]
    api_hints = sorted(set(API_HINT_RE.findall(scripts)))[:15]

    page_title = (tree.select_first("title").text() if tree.select_first("title") else "").strip()
    og_site = ""
    for node in tree.iter():
        if node.tag == "meta" and node.attr("property") in ("og:site_name", "og:title"):
            og_site = node.attr("content").strip()
            break
    generator = ""
    for node in tree.iter():
        if node.tag == "meta" and node.attr("name") == "generator":
            generator = node.attr("content").strip()
            break

    canonical = ""
    for node in tree.iter():
        if node.tag == "link" and node.attr("rel") == "canonical":
            canonical = urllib.parse.urljoin(base_url, node.attr("href").strip())
            break

    warnings: list[str] = []
    link_count = sum(1 for node in tree.iter() if node.tag == "a" and node.attr("href"))
    if link_count < 20:
        warnings.append(
            "sayfada çok az bağlantı var (muhtemelen JavaScript ile çiziliyor); "
            "tarayıcı ağ kaydıyla doğrulanmalı"
        )
    if not sections:
        warnings.append("tekrar eden kart bloğu bulunamadı; seçiciler elle belirlenmeli")

    return {
        "url": base_url,
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pageTitle": page_title,
        "siteName": og_site,
        "canonical": canonical,
        "generator": generator,
        "sections": sections,
        "signals": {
            "anchors": link_count,
            "scripts": sum(1 for node in tree.iter() if node.tag == "script"),
            "iframes": iframes,
            "mediaUrls": media_urls,
            "apiHints": api_hints,
        },
        "warnings": warnings,
        "instructions": [
            "Her bölüm için bir rol seç: media (katalog kartları), text (menü/duyuru) veya ignore.",
            "Yalnızca media bölümleri eklentiye girer; en az bir media bölümü zorunludur.",
            "data alanına eklentinin bu bölüm için göndereceği değeri yaz (ör. kategori id veya slug).",
            "Sonra: python -m turkstream_studio.workflow approve <JOB>",
        ],
    }


def detect_kind(review: dict) -> str:
    signals = review.get("signals", {})
    text = " ".join(
        [review.get("pageTitle", ""), review.get("siteName", "")]
        + signals.get("iframes", [])[:5]
        + signals.get("mediaUrls", [])[:5]
    ).lower()
    if any(word in text for word in ("canlı", "live", "yayın", "tv", "m3u8")):
        return "live"
    return "movie"


def slugify(value: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    value = value.translate(table).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "provider"


def build_spec(review: dict, kind: str, language: str = "tr") -> dict:
    parsed = urllib.parse.urlparse(review["url"])
    name = (review.get("siteName") or review.get("pageTitle") or parsed.netloc).split("|")[0].split("—")[0]
    name = name.strip()[:60] or parsed.netloc
    media = [section for section in review["sections"] if section.get("role") == "media"]
    tv_types = ["Live"] if kind == "live" else ["Movie", "TvSeries"]
    return {
        "name": name,
        "slug": slugify(name),
        "baseUrl": f"{parsed.scheme}://{parsed.netloc}",
        "kind": kind,
        "language": language,
        "tvTypes": tv_types,
        "mainPage": [
            {"name": section["title"], "data": section.get("data") or section["id"], "selector": section["selector"]}
            for section in media
        ],
        "notes": [
            "spec.json approve adımında media bölümlerinden üretilir.",
            "mainPage sırası CloudStream ana sayfasındaki kategori sırasıdır.",
        ],
    }


def write_review(job: Path, review: dict) -> Path:
    path = job / "review.json"
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
