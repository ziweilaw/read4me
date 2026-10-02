from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz, process

from .models import Document, Section

_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
        "eighth": 8, "ninth": 9, "tenth": 10}


@dataclass
class Command:
    kind: str  # read_range | next | previous | stop | unknown
    start: Optional[int] = None  # 0-based pdf page index
    end: Optional[int] = None
    section: Optional[Section] = None
    message: str = ""


def _num(tok: str) -> Optional[int]:
    tok = tok.lower()
    if tok.isdigit():
        return int(tok)
    return _WORDS.get(tok) or _ORD.get(tok)


def parse_command(text: str, doc: Document, current_page: int = 0) -> Command:
    t = re.sub(r"[,.!?]", " ", text.lower()).strip()
    t = re.sub(r"^(please |can you |could you )?(read|go to|jump to|start|play|begin|skip to)( me)?( from)?\s*", "", t).strip()
    t = re.sub(r"\s+", " ", t)

    if t in {"stop", "pause", "stop reading"}:
        return Command("stop")

    m = re.fullmatch(r"(next|previous|prior|last) (chapter|section)", t)
    if m:
        want_level = 1 if m.group(2) == "chapter" else None
        secs = [s for s in doc.sections if want_level is None or s.level <= want_level]
        cur = max((i for i, s in enumerate(secs) if s.start <= current_page), default=-1)
        j = cur + 1 if m.group(1) == "next" else cur - 1
        if 0 <= j < len(secs):
            s = secs[j]
            return Command("read_range", s.start, s.end, s)
        return Command("unknown", message=f"There is no {m.group(1)} {m.group(2)}.")

    # pages: "page 42", "pages 10 to 15", "pages 10-15", "page ten"
    m = re.fullmatch(r"pages? (\w+)(?: ?(?:to|through|until|-|–) ?(\w+))?", t)
    if m and _num(m.group(1)) is not None:
        a = doc.printed_to_index(_num(m.group(1)))
        b = doc.printed_to_index(_num(m.group(2))) if m.group(2) and _num(m.group(2)) is not None else a
        return Command("read_range", a, max(a, b))

    # chapter N
    m = re.fullmatch(r"(?:the )?(?:chapter|ch) (\w+)", t) or re.fullmatch(r"(?:the )?(\w+) chapter", t)
    if m and _num(m.group(1)) is not None:
        n = _num(m.group(1))
        for s in doc.sections:
            if s.number == n and s.level == min(x.level for x in doc.sections if x.number == n):
                return Command("read_range", s.start, s.end, s)
        return Command("unknown", message=f"I couldn't find chapter {n}.")

    # by title (fuzzy): "the introduction", "methods section", "conclusion"
    title = re.sub(r"^(the |section |chapter )+|( section| chapter)$", "", t).strip()
    if title and doc.sections:
        choices = {i: re.sub(r"^\s*(chapter\s+\w+[:.\s-]*|\d+(\.\d+)*[.\s]+)", "", s.title, flags=re.I).lower()
                   for i, s in enumerate(doc.sections)}
        hit = process.extractOne(title, choices, scorer=fuzz.WRatio, score_cutoff=80)
        if hit:
            s = doc.sections[hit[2]]
            return Command("read_range", s.start, s.end, s)

    return Command("unknown", message=f"I didn't understand “{text}”.")
