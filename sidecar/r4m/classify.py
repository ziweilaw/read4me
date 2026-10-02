from __future__ import annotations

import re
from collections import Counter

from .models import (BODY, CAPTION, FOOTNOTE, HEADER_FOOTER, HEADING, REFERENCES,
                     Block, Document)

REF_HEADING = re.compile(r"^\s*(\d+[.\s]+)?(references|bibliography|works cited|literature cited|notes)\s*$", re.I)
CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table|plate|box)\s+[\dIVX]+[.:\s]", re.I)
FOOTNOTE_START = re.compile(r"^\s*(\d{1,3}|[*†‡§])[\s.)]\s*\S")
PAGE_NUM = re.compile(r"^\s*(page\s+)?([ivxlc]+|\d{1,4})\s*$", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip().lower()))


def classify_document(doc: Document) -> None:
    """Assign a label to every block in place."""
    body = doc.body_size

    # 1. running headers/footers: same normalised text near the page edges on many pages
    edge = Counter()
    for b in doc.blocks:
        if b.y_frac < 0.10 or b.y_frac > 0.90:
            edge[_norm(b.text)] += 1
    min_repeats = max(3, int(0.3 * doc.n_pages)) if doc.n_pages > 4 else 2
    repeated = {t for t, n in edge.items() if n >= min_repeats}

    for b in doc.blocks:
        t = b.text.strip()
        at_edge = b.y_frac < 0.10 or b.y_frac > 0.90
        if at_edge and (_norm(b.text) in repeated or PAGE_NUM.match(t)):
            b.label = HEADER_FOOTER
        elif CAPTION_RE.match(t) and b.size <= body * 1.05:
            b.label = CAPTION
        elif (b.y_frac > 0.65 and b.size < body * 0.92 and FOOTNOTE_START.match(t)) or (
            b.y_frac > 0.65 and b.size < body * 0.85 and len(t) > 25
        ):
            b.label = FOOTNOTE
        elif (b.size >= body * 1.15 or (b.bold and b.size >= body * 0.98)) and len(t) < 120 and t.count("\n") < 3:
            b.label = HEADING
        else:
            b.label = BODY

    # 2. everything after a "References" heading is bibliography until a different heading
    in_refs = False
    for b in doc.blocks:
        if b.label == HEADING:
            in_refs = bool(REF_HEADING.match(b.text))
            if in_refs:
                b.label = REFERENCES
        elif in_refs and b.label == BODY:
            b.label = REFERENCES


# ---- inline citations -------------------------------------------------------

_YEAR = r"(?:1[5-9]|20)\d{2}[a-z]?"
_AUTHOR = r"[A-Z][A-Za-z'’\-]+(?:\s+(?:et al\.?|and|&)\s+[A-Z][A-Za-z'’\-]+)*(?:\s+et al\.?)?"
# (Smith, 2020), (Smith & Lee, 2019; Wu et al., 2021), (see Smith 2020, p. 4)
_PAREN_AUTHOR_YEAR = re.compile(
    rf"\s*\((?:(?:see|e\.g\.,?|cf\.|also)\s+)*{_AUTHOR},?\s+{_YEAR}(?:[,:]\s*(?:pp?\.\s*)?\d+(?:[–-]\d+)?)?"
    rf"(?:\s*;\s*(?:(?:see|e\.g\.,?|cf\.)\s+)?{_AUTHOR},?\s+{_YEAR}(?:[,:]\s*(?:pp?\.\s*)?\d+(?:[–-]\d+)?)?)*\)"
)
# [1], [1,3], [1–5], [12, 14-16]
_NUMERIC = re.compile(r"\s*\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
# Smith (2020) -> keep the name, drop the year
_NARRATIVE_YEAR = re.compile(rf"(?<=[a-z])\s*\(\s*{_YEAR}(?:[,:]\s*(?:pp?\.\s*)?\d+(?:[–-]\d+)?)?\s*\)")
_IBID = re.compile(r"\b(?:ibid|op\. cit|loc\. cit)\.?,?", re.I)


def strip_inline_citations(text: str) -> str:
    text = _PAREN_AUTHOR_YEAR.sub("", text)
    text = _NUMERIC.sub("", text)
    text = _NARRATIVE_YEAR.sub("", text)
    text = _IBID.sub("", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)  # tidy space left before punctuation
    return re.sub(r"[ \t]{2,}", " ", text)
