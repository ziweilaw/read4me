from __future__ import annotations

import re
from collections import Counter

from .models import HEADER_FOOTER, HEADING, Document, Section

_CHAPTER_RE = re.compile(r"^\s*(?:chapter|ch\.?)\s+(\d+|[ivxlc]+)\b", re.I)
_LEADING_NUM = re.compile(r"^\s*(\d+)[.\s]")
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s.lower()):
        v = _ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def chapter_number(title: str, level: int) -> int | None:
    m = _CHAPTER_RE.match(title)
    if m:
        g = m.group(1)
        return int(g) if g.isdigit() else roman_to_int(g)
    m = _LEADING_NUM.match(title)
    if m and level == 1:
        return int(m.group(1))
    return None


def detect_page_offset(doc: Document) -> int:
    """pdf_index - printed_page_number, from digit-only header/footer blocks (most common wins)."""
    votes: Counter[int] = Counter()
    for b in doc.blocks:
        if b.label == HEADER_FOOTER and b.text.strip().isdigit():
            votes[b.page - int(b.text.strip())] += 1
    return votes.most_common(1)[0][0] if votes else 0


def build_sections(doc: Document) -> None:
    raw: list[tuple[int, str, int]] = []
    if doc.toc:
        raw = [(lvl, title.strip(), max(0, pg - 1)) for lvl, title, pg in doc.toc if pg > 0]
    else:
        heads = [b for b in doc.blocks if b.label == HEADING]
        if heads:
            sizes = sorted({round(b.size, 1) for b in heads}, reverse=True)
            for b in heads:
                lvl = 1 + min(sizes.index(round(b.size, 1)), 2)
                raw.append((lvl, " ".join(b.text.split()), b.page))

    sections: list[Section] = []
    for i, (lvl, title, start) in enumerate(raw):
        end = doc.n_pages - 1
        for lvl2, _, start2 in raw[i + 1:]:
            if lvl2 <= lvl:
                end = max(start, start2 - 1) if start2 > start else start
                break
        sections.append(Section(title, lvl, start, end, chapter_number(title, lvl)))
    doc.sections = sections
    doc.page_offset = detect_page_offset(doc)
