from __future__ import annotations

from dataclasses import dataclass, field

from .classify import strip_inline_citations
from .models import (BODY, CAPTION, FOOTNOTE, HEADER_FOOTER, HEADING, REFERENCES, Document)
from .normalize import clean_paragraph, expand_abbreviations, split_sentences


@dataclass
class Settings:
    skip_footnotes: bool = True
    skip_citations: bool = True
    skip_captions: bool = True
    skip_references: bool = True


@dataclass
class Unit:
    """One speakable chunk with enough info to highlight and seek."""
    page: int
    kind: str  # heading | sentence
    text: str
    paragraph: int  # paragraph counter, used by the player to insert longer pauses


def build_units(doc: Document, start: int, end: int, s: Settings | None = None) -> list[Unit]:
    s = s or Settings()
    skip = {HEADER_FOOTER}
    if s.skip_footnotes: skip.add(FOOTNOTE)
    if s.skip_captions: skip.add(CAPTION)
    if s.skip_references: skip.add(REFERENCES)

    units: list[Unit] = []
    para = 0
    for b in doc.blocks:
        if not (start <= b.page <= end) or b.label in skip:
            continue
        if b.page in doc.scanned_pages:
            continue
        # reading order within a page follows extraction order (pymupdf sorts blocks top-to-bottom)
        text = clean_paragraph(b.text)
        if s.skip_citations:
            text = strip_inline_citations(text)
        text = expand_abbreviations(text)
        if not text:
            continue
        para += 1
        if b.label == HEADING:
            units.append(Unit(b.page, "heading", text, para))
        else:
            units.extend(Unit(b.page, "sentence", sent, para) for sent in split_sentences(text))
    return units
