"""Minimal HTML tree and CSS-lite selector engine (standard library only).

The studio must run on a clean machine with no pip installs, so this replaces
BeautifulSoup/selectolax for the small job the discovery step needs: find
repeated card containers and pull titles, links and images out of them.

Supported selector syntax (a deliberate subset of CSS):

    div                 tag
    .card               class
    #main               id
    div.card            tag + class
    [data-id]           attribute presence
    a[href^=/film/]     attribute presence/prefix/suffix/contains (^=, $=, *=)
    div.card > a        direct child
    div.card a          descendant
    div, span           selector list

Unsupported (returns no matches instead of guessing): pseudo classes,
sibling combinators, attribute case-insensitivity flags.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

RAW_TEXT_TAGS = {"script", "style"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text_parts")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None, parent: "Node | None" = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node] = []
        self.parent = parent
        self.text_parts: list[str] = []

    # -- identity ---------------------------------------------------------
    @property
    def classes(self) -> list[str]:
        return [part for part in (self.attrs.get("class") or "").split() if part]

    @property
    def id(self) -> str:
        return self.attrs.get("id") or ""

    def attr(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    # -- content ----------------------------------------------------------
    def text(self) -> str:
        parts = list(self.text_parts)
        for child in self.children:
            if child.tag in RAW_TEXT_TAGS:
                continue
            parts.append(child.text())
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def own_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()

    def iter(self):
        yield self
        for child in self.children:
            yield from child.iter()

    # -- selection --------------------------------------------------------
    def select(self, selector: str) -> list["Node"]:
        return select(self, selector)

    def select_first(self, selector: str) -> "Node | None":
        found = select(self, selector, limit=1)
        return found[0] if found else None

    # -- structural -------------------------------------------------------
    def element_children(self) -> list["Node"]:
        return self.children

    def path(self) -> str:
        """CSS path from the root, compacted with nth-of-type where needed."""
        parts: list[str] = []
        node: Node | None = self
        while node is not None and node.parent is not None:
            part = node.tag
            if node.id:
                parts.append(f"{part}#{node.id}")
                break
            if node.classes:
                part += "." + ".".join(node.classes[:2])
            siblings = [c for c in node.parent.children if c.tag == node.tag]
            if len(siblings) > 1:
                part += f":nth-of-type({siblings.index(node) + 1})"
            parts.append(part)
            node = node.parent
        return " > ".join(reversed(parts))

    def signature(self) -> str:
        return self.tag + "".join("." + c for c in self.classes)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.signature()} children={len(self.children)}>"


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].text_parts.append(data)


def parse(html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


# ---------------------------------------------------------------------------
# selectors
# ---------------------------------------------------------------------------

_COMPOUND = re.compile(
    r"""
    (?P<tag>[a-zA-Z][\w-]*|\*)?
    (?P<rest>(?:\#[-\w]+|\.[-\w]+|\[[^\]]+\]|:[-\w]+(?:\([^)]*\))?)*)
    """,
    re.VERBOSE,
)

_ATTR = re.compile(r"\[([-\w:]+)\s*(?:([\^$*]?=)\s*(?:\"([^\"]*)\"|'([^']*)'|([^\]\s]*)))?\]")
_PSEUDO = re.compile(r":([-\w]+)(?:\(([^)]*)\))?")


class _Step:
    __slots__ = ("tag", "ids", "classes", "attrs", "child", "nth_type", "nth_child")

    def __init__(self):
        self.tag = "*"
        self.ids: list[str] = []
        self.classes: list[str] = []
        self.attrs: list[tuple[str, str, str]] = []
        self.child = False
        self.nth_type: int | None = None
        self.nth_child: int | None = None


def _parse_selector(selector: str) -> list[list[_Step]]:
    """Return a selector list, each entry a sequence of steps (descendant/child)."""
    groups: list[list[_Step]] = []
    for raw_group in selector.split(","):
        tokens = raw_group.strip().replace(">", " > ").split()
        steps: list[_Step] = []
        pending_child = False
        for token in tokens:
            if token == ">":
                pending_child = True
                continue
            step = _Step()
            step.child = pending_child and bool(steps)
            pending_child = False
            match = _COMPOUND.fullmatch(token)
            if not match:
                return []
            if match.group("tag"):
                step.tag = match.group("tag")
            rest = match.group("rest") or ""
            for piece in re.finditer(r"\#[-\w]+|\.[-\w]+|\[[^\]]+\]|:[-\w]+(?:\([^)]*\))?", rest):
                value = piece.group(0)
                if value.startswith("#"):
                    step.ids.append(value[1:])
                elif value.startswith("."):
                    step.classes.append(value[1:])
                elif value.startswith(":"):
                    pseudo = _PSEUDO.fullmatch(value)
                    if not pseudo:
                        return []
                    name, argument = pseudo.group(1), (pseudo.group(2) or "").strip()
                    if name in ("nth-of-type", "nth-child"):
                        try:
                            step.nth_type = int(argument) if name == "nth-of-type" else step.nth_type
                            if name == "nth-child":
                                step.nth_child = int(argument)
                        except ValueError:
                            return []
                    elif name == "first-child":
                        step.nth_child = 1
                    elif name == "last-child":
                        step.nth_child = -1
                    else:
                        return []
                else:
                    found = _ATTR.fullmatch(value)
                    if not found:
                        return []
                    name, op = found.group(1), found.group(2) or ""
                    expected = next((g for g in found.groups()[2:] if g is not None), "")
                    step.attrs.append((name, op, expected))
            steps.append(step)
        if steps:
            groups.append(steps)
    return groups


def _matches(node: Node, step: _Step) -> bool:
    if step.tag != "*" and node.tag != step.tag:
        return False
    if step.ids and node.id not in step.ids:
        return False
    if step.classes:
        owned = set(node.classes)
        if not set(step.classes).issubset(owned):
            return False
    for name, op, expected in step.attrs:
        if name not in node.attrs:
            return False
        value = node.attrs[name]
        if op == "=" and value != expected:
            return False
        if op == "^=" and not value.startswith(expected):
            return False
        if op == "$=" and not value.endswith(expected):
            return False
        if op == "*=" and expected not in value:
            return False
    if step.nth_type is not None:
        parent = node.parent
        if parent is None:
            return False
        same_tag = [child for child in parent.children if child.tag == node.tag]
        try:
            if same_tag.index(node) + 1 != step.nth_type:
                return False
        except ValueError:
            return False
    if step.nth_child is not None:
        parent = node.parent
        if parent is None:
            return False
        siblings = parent.children
        try:
            index = siblings.index(node) + 1
        except ValueError:
            return False
        if step.nth_child == -1:
            if index != len(siblings):
                return False
        elif index != step.nth_child:
            return False
    return True


def _walk(node: Node, steps: list[_Step], index: int):
    step = steps[index]
    last = index == len(steps) - 1
    if step.child and index > 0:
        candidates = [child for child in node.children if _matches(child, step)]
        for child in candidates:
            if last:
                yield child
            else:
                yield from _walk(child, steps, index + 1)
        return
    for descendant in node.iter():
        if descendant is node or not _matches(descendant, step):
            continue
        if last:
            yield descendant
        else:
            yield from _walk(descendant, steps, index + 1)


def select(root: Node, selector: str, limit: int = 0) -> list[Node]:
    groups = _parse_selector(selector)
    if not groups:
        return []
    results: list[Node] = []
    seen: set[int] = set()
    for steps in groups:
        for hit in _walk(root, steps, 0):
            if id(hit) in seen:
                continue
            seen.add(id(hit))
            results.append(hit)
            if limit and len(results) >= limit:
                return results
    return results


def document_order(root: Node) -> list[Node]:
    return list(root.iter())
