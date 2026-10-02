from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Block labels
BODY = "body"
HEADING = "heading"
FOOTNOTE = "footnote"
CAPTION = "caption"
HEADER_FOOTER = "header_footer"
REFERENCES = "references"


@dataclass
class Block:
    page: int  # 0-based PDF page index
    bbox: tuple[float, float, float, float]
    text: str
    size: float
    bold: bool
    page_height: float
    label: str = BODY
    markers: list[str] = field(default_factory=list)  # superscript marker strings removed from text

    @property
    def y_frac(self) -> float:
        """Vertical centre of the block as a fraction of page height (0=top)."""
        return ((self.bbox[1] + self.bbox[3]) / 2) / self.page_height


@dataclass
class Section:
    title: str
    level: int
    start: int  # 0-based PDF page index
    end: int  # inclusive
    number: Optional[int] = None  # chapter number if recognisable


@dataclass
class Document:
    path: str
    n_pages: int
    blocks: list[Block]
    toc: list[tuple[int, str, int]]  # (level, title, 1-based page) from PDF outline
    body_size: float = 10.0
    scanned_pages: list[int] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    page_offset: int = 0  # pdf_index - printed_page_number
    kind: str = "pdf"  # pdf | epub (for epub, a 'page' is a TOC-delimited segment)
    seg_titles: list[str] = field(default_factory=list)  # epub: title shown for each segment

    def printed_to_index(self, printed: int) -> int:
        return max(0, min(self.n_pages - 1, printed + self.page_offset))

    def index_to_printed(self, idx: int) -> int:
        return idx - self.page_offset
