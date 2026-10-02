from __future__ import annotations

from .classify import classify_document
from .extract import extract_document
from .models import Document
from .structure import build_sections


def load(path: str) -> Document:
    if path.lower().endswith(".epub"):
        from .epub import extract_epub
        return extract_epub(path)
    doc = extract_document(path)
    classify_document(doc)
    build_sections(doc)
    return doc
