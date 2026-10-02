import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sidecar"))

BODY1 = ("Memory consolidation depends on sleep (Smith & Lee, 2019; Wu et al., 2021). Recent work "
         "extends this idea [1, 3]. Researchers e.g. Brown (2020) disagree.")
BODY2 = "The second chapter introduces methods used throughout the book. We sampled 40 participants."


def _page(pdf, printed, title, body, footnote, chapter=None):
    page = pdf.new_page(width=595, height=842)
    page.insert_text((72, 40), "Read4me Test Book", fontsize=9)  # running header
    if chapter:
        page.insert_text((72, 110), chapter, fontsize=22)
    page.insert_text((72, 150), title, fontsize=14)
    page.insert_textbox(pymupdf.Rect(72, 170, 523, 400), body, fontsize=11)
    page.insert_text((72, 700), footnote, fontsize=8)  # footnote near bottom, small
    page.insert_text((295, 800), str(printed), fontsize=10)  # page number


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    """Front-matter page (roman), then chapters 1 and 2 starting at printed page 1 -> offset 2."""
    p = tmp_path_factory.mktemp("pdf") / "book.pdf"
    pdf = pymupdf.open()
    for label in ("Title Page", "Contents"):  # two unnumbered front-matter pages
        pdf.new_page(width=595, height=842).insert_text((72, 300), label, fontsize=24)
    _page(pdf, 1, "Introduction", BODY1, "1 Smith, J. (2019). Sleep and memory. Journal of Sleep.", "Chapter 1")
    _page(pdf, 2, "More on sleep", BODY1, "2 Lee, K. (2020). Notes on consolidation. Sleep Press.")
    _page(pdf, 3, "Methods", BODY2, "3 Wu, T. (2021). Participant sampling. Methods Review.", "Chapter 2")
    _page(pdf, 4, "Results", BODY2, "4 Brown, A. (2020). Findings. Results Today.")
    pdf.set_toc([[1, "Chapter 1: Introduction", 3], [1, "Chapter 2: Methods", 5]])
    pdf.save(p)
    return str(p)


@pytest.fixture(scope="session")
def sample_epub(tmp_path_factory):
    import zipfile
    p = tmp_path_factory.mktemp("epub") / "book.epub"
    X = '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>%s</body></html>'
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest><item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/><item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
        z.writestr("OEBPS/nav.xhtml", X % '<nav epub:type="toc"><ol><li><a href="ch1.xhtml">Chapter 1: Introduction</a></li><li><a href="ch2.xhtml">Chapter 2: Methods</a><ol><li><a href="ch2.xhtml#sampling">Sampling</a></li><li><a href="ch2.xhtml#refs">References</a></li></ol></li></ol></nav>')
        z.writestr("OEBPS/ch1.xhtml", X % ('<h1>Chapter 1: Introduction</h1><p>Memory consolidation depends on sleep (Smith &amp; Lee, 2019).<a epub:type="noteref" href="#n1">1</a> '
            'Recent work extends this idea.<sup>2</sup></p><p>A second paragraph.</p><aside epub:type="footnote" id="n1"><p>1. See Smith, J. (2019). Sleep. Journal of Sleep.</p></aside><p><img src="x.png"/></p>'))
        z.writestr("OEBPS/ch2.xhtml", X % ('<h1>Chapter 2: Methods</h1><p>We sampled forty people.</p><h2 id="sampling">Sampling</h2><p>Sampling was random.</p>'
            '<figure><figcaption>Figure 1. A diagram.</figcaption></figure><h2 id="refs">References</h2><p>Smith, J. (2019). Sleep. Journal of Sleep.</p>'))
    return str(p)
