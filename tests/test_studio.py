"""Offline tests for the local TurkStream Studio.

Run: python3 -m pytest tests/test_studio.py -q
     (or) python3 tests/test_studio.py
No network access; fixtures are inline HTML.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turkstream_studio import discover, htmltree, knowledge  # noqa: E402

CATALOG_HTML = """
<html><head><title>Örnek Dizi | Site</title>
<meta property="og:site_name" content="Örnek Dizi"></head>
<body>
<nav><a href="/">Ana</a><a href="/diziler">Diziler</a><a href="/filmler">Filmler</a>
<a href="/canli">Canlı</a></nav>
<h2>Son Eklenenler</h2>
<div class="grid">
  <div class="card"><a href="/dizi/bir"><img data-src="/p/1.jpg"><h3 class="title">Bir</h3></a></div>
  <div class="card"><a href="/dizi/iki"><img data-src="/p/2.jpg"><h3 class="title">İki</h3></a></div>
  <div class="card"><a href="/dizi/uc"><img data-src="/p/3.jpg"><h3 class="title">Üç</h3></a></div>
  <div class="card"><a href="/dizi/dort"><img data-src="/p/4.jpg"><h3 class="title">Dört</h3></a></div>
  <div class="card"><a href="/dizi/bes"><img data-src="/p/5.jpg"><h3 class="title">Beş</h3></a></div>
  <div class="card"><a href="/dizi/alti"><img data-src="/p/6.jpg"><h3 class="title">Altı</h3></a></div>
</div>
<footer><a href="/diziler">Diziler</a><a href="/filmler">Filmler</a>
<a href="/canli">Canlı</a><a href="/hakkinda">Hakkında</a></footer>
</body></html>
"""


def test_selector_engine():
    tree = htmltree.parse(CATALOG_HTML)
    assert len(tree.select("div.card")) == 6
    assert len(tree.select("div.grid > div.card")) == 6
    assert tree.select_first("h2").text() == "Son Eklenenler"
    assert len(tree.select('a[href^="/dizi/"]')) == 6
    assert len(tree.select(".card .title")) == 6
    assert tree.select_first("div.card h3").attr("class") == "title"


def test_path_roundtrip_selects_same_node():
    tree = htmltree.parse(CATALOG_HTML)
    for card in tree.select("div.card"):
        path = card.path()
        assert any(node is card for node in tree.select(path)), path


def test_discover_finds_catalog_and_drops_menu():
    review = discover.discover(CATALOG_HTML, "https://ornek.site/")
    assert review["sections"], "kart bloğu bulunmalı"
    media = [s for s in review["sections"] if s["suggestedRole"] == "media"]
    assert media, "katalog bölümü media önerilmeli"
    section = media[0]
    assert section["count"] >= 6
    assert section["region"] == "main"
    titles = {sample["title"] for sample in section["samples"]}
    assert "Bir" in titles
    posters = {sample["poster"] for sample in section["samples"]}
    assert "https://ornek.site/p/1.jpg" in posters
    # nav/footer tekrar eden linkler ayrı bölüm olarak listelenmemeli
    assert len(review["sections"]) <= 3


def test_spec_uses_only_media_sections():
    review = discover.discover(CATALOG_HTML, "https://ornek.site/")
    for section in review["sections"]:
        section["role"] = "media" if section["suggestedRole"] == "media" else "text"
    spec = discover.build_spec(review, "movie")
    assert spec["slug"] == "ornek-dizi"
    assert spec["baseUrl"] == "https://ornek.site"
    assert spec["mainPage"], "mainPage media bölümlerinden üretilmeli"
    assert all(entry["selector"] for entry in spec["mainPage"])


def test_slugify_turkish():
    assert discover.slugify("İnat TV — Canlı") == "inat-tv-canli"
    assert discover.slugify("ÇĞİÖŞÜ") == "cgiosu"


def test_knowledge_index_has_both_sources():
    index = knowledge.Index()
    stats = index.stats()
    assert stats["bySource"].get("skill", 0) > 0
    assert stats["bySource"].get("csdocs", 0) > 0
    hits = index.search("loadLinks extractor")
    assert hits
    assert all(chunk.path for _score, chunk in hits)
    # arama terimleri kaynak dosyalarda gerçekten bulunmalı
    assert any("loadLinks" in chunk.text for _score, chunk in hits)


if __name__ == "__main__":
    failures = 0
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            try:
                function()
                print(f"ok   {name}")
            except AssertionError as error:
                failures += 1
                print(f"FAIL {name}: {error}")
    sys.exit(1 if failures else 0)
