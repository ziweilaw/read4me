from r4m.classify import strip_inline_citations
from r4m.commands import parse_command
from r4m.pipeline import load
from r4m.reader import Settings, build_units


def test_inline_citation_stripping():
    f = strip_inline_citations
    assert f("Sleep matters (Smith & Lee, 2019; Wu et al., 2021).") == "Sleep matters."
    assert f("As shown [1, 3] earlier.") == "As shown earlier."
    assert f("Brown (2020) disagrees.") == "Brown disagrees."
    assert f("See (Smith 2020, p. 4) for more") == "See for more"
    assert f("A range [12–15] here.") == "A range here."


def test_classification(sample_pdf):
    doc = load(sample_pdf)
    labels = {b.text.split("\n")[0][:20]: b.label for b in doc.blocks}
    assert labels["Read4me Test Book"] == "header_footer"
    assert labels["1"] == "header_footer"  # printed page number
    foots = [b for b in doc.blocks if b.label == "footnote"]
    assert len(foots) == 4 and all("(" in b.text for b in foots)


def test_page_offset_and_sections(sample_pdf):
    doc = load(sample_pdf)
    assert doc.page_offset == 1  # printed 1 is pdf index 2 -> index = printed + 1
    assert [s.number for s in doc.sections] == [1, 2]
    assert doc.sections[0].start == 2 and doc.sections[0].end == 3


def test_commands(sample_pdf):
    doc = load(sample_pdf)
    c = parse_command("Read chapter 2", doc)
    assert (c.kind, c.start, c.end) == ("read_range", 4, 5)
    c = parse_command("read chapter two please".replace(" please", ""), doc)
    assert c.start == 4
    c = parse_command("go to page 2", doc)  # printed 2 -> index 3
    assert c.start == 3 and c.end == 3
    c = parse_command("pages 1 to 2", doc)
    assert (c.start, c.end) == (2, 3)
    c = parse_command("read the methods", doc)
    assert c.kind == "read_range" and c.section.number == 2
    c = parse_command("next chapter", doc, current_page=2)
    assert c.section.number == 2
    assert parse_command("read chapter 9", doc).kind == "unknown"


def test_reading_skips_side_notes(sample_pdf):
    doc = load(sample_pdf)
    units = build_units(doc, 2, 3, Settings())
    spoken = " ".join(u.text for u in units)
    assert "Smith & Lee" not in spoken and "[1" not in spoken
    assert "Journal of Sleep" not in spoken  # footnote skipped
    assert "Read4me Test Book" not in spoken  # running header skipped
    assert "Memory consolidation depends on sleep." in spoken
    with_notes = " ".join(u.text for u in build_units(doc, 2, 2, Settings(skip_footnotes=False)))
    assert "Journal of Sleep" in with_notes
