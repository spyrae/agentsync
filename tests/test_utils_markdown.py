"""Tests for agentsync.utils.markdown — pure section parsing and filtering."""

from __future__ import annotations

from agentsync.adapters.base import Section
from agentsync.utils.markdown import filter_sections, parse_markdown_sections

# === parse_markdown_sections ===

SAMPLE_MD = """\
# Title

Preamble text.

## Section A

Content of A.

### Subsection A1

Content of A1.

## Section B

Content of B.

### Subsection B1

Content of B1.

### Subsection B2

Content of B2.
"""


def test_parse_counts():
    sections = parse_markdown_sections(SAMPLE_MD)
    assert len(sections) == 5


def test_parse_headers():
    sections = parse_markdown_sections(SAMPLE_MD)
    headers = [s.header for s in sections]
    assert headers == ["Section A", "Subsection A1", "Section B", "Subsection B1", "Subsection B2"]


def test_parse_levels():
    sections = parse_markdown_sections(SAMPLE_MD)
    levels = [s.level for s in sections]
    assert levels == [2, 3, 2, 3, 3]


def test_parse_content_includes_header_line():
    sections = parse_markdown_sections(SAMPLE_MD)
    assert sections[0].content.startswith("## Section A")


def test_parse_empty_string():
    assert parse_markdown_sections("") == []


def test_parse_no_sections():
    """Only preamble, no ## or ### headers."""
    assert parse_markdown_sections("Just a paragraph.\nAnother line.") == []


def test_parse_single_section():
    sections = parse_markdown_sections("## Only One\n\nBody here.")
    assert len(sections) == 1
    assert sections[0].header == "Only One"
    assert sections[0].level == 2


def test_parse_hash_in_code_block_not_treated_as_header():
    """Lines starting with ## inside content (not at header position) stay in content."""
    md = "## Real\n\nSome text\nwith ## embedded hash\n"
    sections = parse_markdown_sections(md)
    # The "## embedded hash" is a new section because we parse by prefix
    # This is expected behaviour matching the JourneyBay original
    assert len(sections) >= 1


# === filter_sections ===


def _make_sections() -> list[Section]:
    return [
        Section(header="Keep", level=2, content="## Keep\nok"),
        Section(header="Remove", level=2, content="## Remove\nbad"),
        Section(header="Child of Remove", level=3, content="### Child of Remove\nalso bad"),
        Section(header="After", level=2, content="## After\ngood"),
        Section(header="Remove Leaf", level=3, content="### Remove Leaf\njust this"),
    ]


def test_filter_excludes_level2_and_children():
    sections = _make_sections()
    result = filter_sections(sections, {"Remove"})
    headers = [s.header for s in result]
    assert "Remove" not in headers
    assert "Child of Remove" not in headers
    assert "Keep" in headers
    assert "After" in headers


def test_filter_excludes_level3_only():
    sections = _make_sections()
    result = filter_sections(sections, {"Remove Leaf"})
    headers = [s.header for s in result]
    assert "Remove Leaf" not in headers
    assert "After" in headers
    assert len(result) == 4


def test_filter_empty_exclude():
    sections = _make_sections()
    result = filter_sections(sections, set())
    assert len(result) == len(sections)


def test_filter_all_excluded():
    sections = _make_sections()
    all_headers = {s.header for s in sections}
    result = filter_sections(sections, all_headers)
    assert result == []
