"""Merged knowledge index: skill references plus the CloudStream developer docs.

Both sources are plain markdown, so the studio indexes them into heading-sized
chunks and answers with a small BM25 ranking. No network, no dependencies, and
no generated text: every hit is a real file and line range the agent can open.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs" / "cloudstream"
SKILL_ROOT = REPO_ROOT

STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "için", "olan", "the", "and", "for",
    "with", "from", "that", "this", "are", "you", "your", "can", "not", "all",
}


@dataclass
class Chunk:
    source: str          # skill | csdocs
    path: str            # path relative to the repository
    heading: str
    line: int
    text: str


def _sources() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        found.append(("csdocs", path))
    for path in [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "references").glob("*.md")),
                 SKILL_ROOT / "extractors" / "INDEX.md"]:
        if path.is_file():
            found.append(("skill", path))
    return found


def _strip_frontmatter(lines: list[str]) -> list[str]:
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return lines[index + 1:]
    return lines


def load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for source, path in _sources():
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = _strip_frontmatter(raw.splitlines())
        heading = path.stem
        buffer: list[str] = []
        start = 1
        in_fence = False

        def flush() -> None:
            text = "\n".join(buffer).strip()
            if text:
                chunks.append(
                    Chunk(source, str(path.relative_to(SKILL_ROOT)), heading, start, text)
                )

        for number, line in enumerate(lines, start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if not in_fence and re.match(r"^#{1,4}\s", line):
                flush()
                buffer = []
                heading = line.lstrip("#").strip()[:120]
                start = number
                continue
            buffer.append(line)
        flush()
    return chunks


def tokenize(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_]{2,}", text.lower())
        if token not in STOPWORDS
    ]


class Index:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks if chunks is not None else load_chunks()
        self.docs = [tokenize(chunk.heading + " " + chunk.text) for chunk in self.chunks]
        self.lengths = [len(tokens) for tokens in self.docs]
        self.avg = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.tf: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for tokens in self.docs:
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            self.tf.append(counts)
            for token in counts:
                df[token] = df.get(token, 0) + 1
        total = len(self.chunks) or 1
        self.idf = {token: math.log(1 + (total - count + 0.5) / (count + 0.5)) for token, count in df.items()}

    def search(self, query: str, limit: int = 8, source: str | None = None) -> list[tuple[float, Chunk]]:
        terms = tokenize(query)
        if not terms:
            return []
        k1, b = 1.5, 0.75
        scored: list[tuple[float, Chunk]] = []
        for index, chunk in enumerate(self.chunks):
            if source and chunk.source != source:
                continue
            score = 0.0
            for term in terms:
                frequency = self.tf[index].get(term, 0)
                if not frequency:
                    continue
                norm = 1 - b + b * (self.lengths[index] / (self.avg or 1))
                score += self.idf.get(term, 0.0) * (frequency * (k1 + 1)) / (frequency + k1 * norm)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    def stats(self) -> dict:
        by_source: dict[str, int] = {}
        for chunk in self.chunks:
            by_source[chunk.source] = by_source.get(chunk.source, 0) + 1
        return {
            "chunks": len(self.chunks),
            "bySource": by_source,
            "files": len({chunk.path for chunk in self.chunks}),
            "terms": len(self.idf),
        }
