from __future__ import annotations

from collections import Counter

import pymupdf

from .models import Block, Document

SUPERSCRIPT_FLAG = 1  # pymupdf span flag bit 0


def _is_marker(span: dict, body_size: float) -> bool:
    txt = span["text"].strip()
    if not txt:
        return False
    small = span["size"] < body_size * 0.75
    sup = bool(span["flags"] & SUPERSCRIPT_FLAG)
    return (sup or small) and all(c.isdigit() or c in "*†‡§,-–" for c in txt)


def _dominant_body_size(page_dicts: list[dict]) -> float:
    counts: Counter[float] = Counter()
    for pd in page_dicts:
        for b in pd["blocks"]:
            if b["type"] != 0:
                continue
            for ln in b["lines"]:
                for sp in ln["spans"]:
                    counts[round(sp["size"], 1)] += len(sp["text"].strip())
    return counts.most_common(1)[0][0] if counts else 10.0


def extract_document(path: str, min_chars_for_text_page: int = 25) -> Document:
    pdf = pymupdf.open(path)
    page_dicts = [p.get_text("dict") for p in pdf]
    body_size = _dominant_body_size(page_dicts)

    blocks: list[Block] = []
    scanned: list[int] = []
    for pno, (page, pd) in enumerate(zip(pdf, page_dicts)):
        page_chars = 0
        for b in pd["blocks"]:
            if b["type"] != 0:
                continue
            lines_txt: list[str] = []
            markers: list[str] = []
            size_weight: Counter[float] = Counter()
            bold_chars = total_chars = 0
            for ln in b["lines"]:
                parts: list[str] = []
                for sp in ln["spans"]:
                    t = sp["text"]
                    if _is_marker(sp, body_size) and parts:
                        markers.append(t.strip())
                        continue
                    parts.append(t)
                    n = len(t.strip())
                    size_weight[round(sp["size"], 1)] += n
                    total_chars += n
                    if sp["flags"] & 16:
                        bold_chars += n
                lines_txt.append("".join(parts).strip())
            text = "\n".join(l for l in lines_txt if l)
            if not text.strip():
                continue
            page_chars += total_chars
            size = size_weight.most_common(1)[0][0] if size_weight else body_size
            blocks.append(
                Block(
                    page=pno,
                    bbox=tuple(b["bbox"]),
                    text=text,
                    size=size,
                    bold=total_chars > 0 and bold_chars / total_chars > 0.6,
                    page_height=page.rect.height,
                    markers=markers,
                )
            )
        if page_chars < min_chars_for_text_page:
            scanned.append(pno)  # needs OCR (milestone 6)

    return Document(
        path=path,
        n_pages=len(pdf),
        blocks=blocks,
        toc=pdf.get_toc(),
        body_size=body_size,
        scanned_pages=scanned,
    )
