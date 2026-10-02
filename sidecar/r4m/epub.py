"""EPUB -> Document. Blocks are labelled directly from the book's own markup (epub:type / roles),
and the book is cut into TOC-delimited segments that play the role of PDF 'pages'."""
from __future__ import annotations

import posixpath
import re
import zipfile
from urllib.parse import unquote, urldefrag
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, Tag

from .classify import CAPTION_RE, REF_HEADING
from .models import BODY, CAPTION, FOOTNOTE, HEADING, REFERENCES, Block, Document, Section
from .structure import chapter_number

NOTE_TYPES = {"footnote", "footnotes", "endnote", "endnotes", "rearnote", "rearnotes",
              "doc-footnote", "doc-endnote", "doc-endnotes", "doc-footnotes"}
REF_TYPES = {"bibliography", "doc-bibliography"}
NOTEREF_TYPES = {"noteref", "doc-noteref"}
SKIP_TYPES = {"pagebreak", "doc-pagebreak", "toc", "doc-toc", "landmarks", "page-list", "index", "doc-index"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
ALWAYS_LEAF = HEADINGS | {"p", "figcaption", "pre"}
BLOCKS = ALWAYS_LEAF | {"div", "ul", "ol", "li", "blockquote", "table", "section", "article", "aside",
                        "figure", "dl", "dt", "dd", "header", "footer", "nav"}
INDEX_HEADING = re.compile(r"^(subject |name |general )?index$", re.I)
BARE_NUMBER = re.compile(r"^[\divxlc]{1,6}$", re.I)
MARKER = re.compile(r"^[\[\(]?[\d*†‡§,\s\-–]+[\]\)]?$")


def _types(el: Tag) -> set[str]:
    out: set[str] = set()
    for k, v in el.attrs.items():
        if k == "role" or k.endswith("type"):
            out.update((v if isinstance(v, str) else " ".join(v)).split())
    return out


def _opf_and_toc(z: zipfile.ZipFile):
    root = ET.fromstring(z.read("META-INF/container.xml"))
    opf_path = root.find(".//{*}rootfile").get("full-path")
    base = posixpath.dirname(opf_path)
    opf = ET.fromstring(z.read(opf_path))
    manifest = {i.get("id"): i for i in opf.findall(".//{*}manifest/{*}item")}
    res = lambda href: posixpath.normpath(posixpath.join(base, unquote(href)))
    spine = [res(manifest[r.get("idref")].get("href")) for r in opf.findall(".//{*}spine/{*}itemref")
             if r.get("idref") in manifest]
    toc_path, toc_kind = None, None
    for it in manifest.values():
        if "nav" in (it.get("properties") or "").split():
            toc_path, toc_kind = res(it.get("href")), "nav"
    if not toc_path:
        ncx_id = opf.find(".//{*}spine").get("toc")
        if ncx_id in manifest:
            toc_path, toc_kind = res(manifest[ncx_id].get("href")), "ncx"
    return spine, toc_path, toc_kind


def _parse_toc(z: zipfile.ZipFile, toc_path: str | None, kind: str | None):
    """-> [(level, title, path, fragment)] in TOC order."""
    if not toc_path or toc_path not in z.namelist():
        return []
    base = posixpath.dirname(toc_path)

    def target(href: str):
        path, frag = urldefrag(unquote(href))
        if not path:
            return None
        return posixpath.normpath(posixpath.join(base, path)), frag

    out: list[tuple[int, str, str, str]] = []
    if kind == "nav":
        soup = BeautifulSoup(z.read(toc_path), "html.parser")
        nav = next((n for n in soup.find_all("nav") if "toc" in " ".join(_types(n)).split()), None) or soup.find("nav")

        def walk(ol: Tag, level: int):
            for li in ol.find_all("li", recursive=False):
                a = li.find("a", recursive=False) or li.find(["a", "span"])
                if a is not None and a.get("href") and (t := target(a["href"])):
                    out.append((level, " ".join(a.get_text().split()), *t))
                for sub in li.find_all("ol", recursive=False):
                    walk(sub, level + 1)

        if nav and (ol := nav.find("ol")):
            walk(ol, 1)
    else:
        root = ET.fromstring(z.read(toc_path))

        def walk_ncx(el, level):
            for np_ in el.findall("{*}navPoint"):
                label = np_.find("{*}navLabel/{*}text")
                content = np_.find("{*}content")
                if content is not None and (t := target(content.get("src", ""))):
                    out.append((level, " ".join((label.text or "").split()) if label is not None else "", *t))
                walk_ncx(np_, level + 1)

        nm = root.find("{*}navMap")
        if nm is not None:
            walk_ncx(nm, 1)
    return out


def _prepare(soup: BeautifulSoup) -> Tag:
    for t in soup(["script", "style", "svg", "table", "img", "head"]):
        t.decompose()
    for el in soup.find_all(True):
        if el.attrs is None:
            continue
        ty = _types(el)
        if ty & SKIP_TYPES:
            el.decompose()
        elif ty & NOTEREF_TYPES:
            el.decompose()
    for sup in soup.find_all("sup"):
        if MARKER.match(sup.get_text().strip() or "x"):
            sup.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    return soup.body or soup


def extract_epub(path: str) -> Document:
    z = zipfile.ZipFile(path)
    spine, toc_path, toc_kind = _opf_and_toc(z)
    entries = _parse_toc(z, toc_path, toc_kind)
    spine = [p for p in spine if p in z.namelist()]
    bodies = {p: _prepare(BeautifulSoup(z.read(p), "html.parser")) for p in spine}

    if not entries:  # no usable TOC: one section per file, titled by its first heading
        for i, p in enumerate(spine):
            h = bodies[p].find(list(HEADINGS))
            title = " ".join(h.get_text().split()) if h else f"Section {i + 1}"
            entries.append((1, title, p, ""))

    by_file: dict[str, list[int]] = {}
    for ei, (_, _, p, frag) in enumerate(entries):
        by_file.setdefault(p, []).append(ei)

    entry_seg: dict[int, int] = {}
    blocks: list[Block] = []
    state = {"cur": -1, "n": {}, "index": False}  # n: blocks per segment

    def boundary() -> int:
        if state["cur"] == -1 or state["n"].get(state["cur"], 0) > 0:
            state["cur"] += 1
            state["index"] = False  # an index spans many letter headings; it ends at the next TOC section
        return state["cur"]

    def emit(el: Tag, ctx: str, in_refs: list[bool]):
        text = " ".join(el.get_text().split())
        if not text or (BARE_NUMBER.match(text) and el.name != "li"):
            return
        if el.name in HEADINGS and INDEX_HEADING.match(text):
            state["index"] = True
        if state["index"] and ctx == BODY:
            label = REFERENCES
        elif el.name in HEADINGS and ctx == BODY:
            label = HEADING
            in_refs[0] = bool(REF_HEADING.match(text))
            if in_refs[0]:
                label = REFERENCES
        elif ctx != BODY:
            label = ctx
        elif el.name == "figcaption" or (CAPTION_RE.match(text) and len(text) < 250):
            label = CAPTION
        else:
            label = REFERENCES if in_refs[0] else BODY
        if state["cur"] == -1:
            state["cur"] = 0
        state["n"][state["cur"]] = state["n"].get(state["cur"], 0) + 1
        blocks.append(Block(state["cur"], (0, 0, 0, 0), text, 12.0, False, 1.0, label))

    in_refs = [False]
    for p in spine:
        eids = by_file.get(p, [])
        frag_map: dict[str, list[int]] = {}
        file_seg = None
        for ei in eids:
            if not entries[ei][3]:
                if file_seg is None:
                    file_seg = boundary()
                entry_seg[ei] = file_seg
            else:
                frag_map.setdefault(entries[ei][3], []).append(ei)
        if file_seg is None:
            file_seg = max(state["cur"], 0)

        def hit(el: Tag, deep: bool):
            ids = [el.get("id")] + ([d.get("id") for d in el.find_all(id=True)] if deep else [])
            for i in ids:
                if i and i in frag_map:
                    seg = boundary()
                    for ei in frag_map.pop(i):
                        entry_seg[ei] = seg

        def handle(el: Tag, ctx: str):
            if el.name in ("html", "body"):
                ctx2 = ctx
            else:
                ty = _types(el)
                cls = " ".join(el.get("class", [])).lower()
                if ty & NOTE_TYPES or el.name == "aside" or "footnote" in cls or "endnote" in cls:
                    ctx2 = FOOTNOTE
                elif ty & REF_TYPES:
                    ctx2 = REFERENCES
                else:
                    ctx2 = ctx
            leaf = el.name in ALWAYS_LEAF or (el.name not in ("body", "html") and not el.find(list(BLOCKS)))
            hit(el, deep=leaf)
            if leaf:
                emit(el, ctx2, in_refs)
            else:
                for child in el.children:
                    if isinstance(child, Tag):
                        handle(child, ctx2)

        handle(bodies[p], BODY)
        for ei in [e for lst in frag_map.values() for e in lst]:  # anchors not found -> file start
            entry_seg[ei] = file_seg

    n_pages = max(1, state["cur"] + 1)
    raw = [(lvl, title, entry_seg.get(i, 0)) for i, (lvl, title, _, _) in enumerate(entries)]
    sections: list[Section] = []
    for i, (lvl, title, start) in enumerate(raw):
        end = n_pages - 1
        for lvl2, _, start2 in raw[i + 1:]:
            if lvl2 <= lvl:
                end = max(start, start2 - 1) if start2 > start else start
                break
        sections.append(Section(title, lvl, start, end, chapter_number(title, lvl)))

    titles = [""] * n_pages
    for s in sections:
        if not titles[s.start]:
            titles[s.start] = s.title
    for i in range(n_pages):
        titles[i] = titles[i] or (titles[i - 1] if i else "Beginning")

    return Document(path=path, n_pages=n_pages, blocks=blocks, toc=[], sections=sections,
                    kind="epub", seg_titles=titles)
