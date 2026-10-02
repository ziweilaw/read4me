from __future__ import annotations

import re

import pysbd

_seg = pysbd.Segmenter(language="en", clean=False)

_ABBR = [
    (r"\be\.g\.,?", "for example,"), (r"\bi\.e\.,?", "that is,"), (r"\betc\.", "et cetera"),
    (r"\bvs\.", "versus"), (r"\bcf\.", "compare"), (r"\bFig\.", "Figure"), (r"\bEq\.", "Equation"),
    (r"\bNo\.\s*(?=\d)", "number "), (r"\bpp\.\s*(?=\d)", "pages "), (r"\bp\.\s*(?=\d)", "page "),
    (r"\bet al\.", "and colleagues"), (r"\bDr\.", "Doctor"), (r"\bProf\.", "Professor"),
]


def clean_paragraph(text: str) -> str:
    """Join lines / repair ligatures. Run citation stripping next, THEN expand_abbreviations."""
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\u00ad", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def expand_abbreviations(text: str) -> str:
    for pat, rep in _ABBR:
        text = re.sub(pat, rep, text)
    return text


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _seg.segment(text) if s.strip()]
