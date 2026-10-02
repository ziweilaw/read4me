from r4m.commands import parse_command
from r4m.pipeline import load
from r4m.reader import Settings, build_units


def test_epub_structure(sample_epub):
    doc = load(sample_epub)
    assert doc.kind == "epub"
    assert [(s.title, s.level) for s in doc.sections] == [
        ("Chapter 1: Introduction", 1), ("Chapter 2: Methods", 1), ("Sampling", 2), ("References", 2)]
    ch1, ch2 = doc.sections[0], doc.sections[1]
    assert ch1.end < ch2.start and ch2.end == doc.n_pages - 1
    assert doc.seg_titles[ch2.start] == "Chapter 2: Methods"


def test_epub_reading_skips_side_notes(sample_epub):
    doc = load(sample_epub)
    spoken = " ".join(u.text for u in build_units(doc, 0, doc.n_pages - 1, Settings()))
    assert "Memory consolidation depends on sleep." in spoken
    assert "Smith & Lee" not in spoken        # inline citation
    assert "Journal of Sleep" not in spoken   # footnote aside + bibliography
    assert "Figure 1" not in spoken           # caption
    assert "sampled forty people" in spoken and "Sampling was random" in spoken
    assert "sleep.1" not in spoken and "idea.2" not in spoken  # note markers dropped
    notes = " ".join(u.text for u in build_units(doc, 0, 0, Settings(skip_footnotes=False)))
    assert "Journal of Sleep" in notes


def test_epub_chapter_command(sample_epub):
    doc = load(sample_epub)
    c = parse_command("read chapter 2", doc)
    assert c.kind == "read_range" and c.section.title.startswith("Chapter 2")
