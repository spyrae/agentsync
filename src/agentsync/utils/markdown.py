"""Markdown section parsing and filtering — pure functions, no I/O."""

from __future__ import annotations

from agentsync.adapters.base import Section


def parse_markdown_sections(content: str) -> list[Section]:
    """Parse markdown *content* into a flat list of :class:`Section` objects.

    Recognises ``##`` (level 2) and ``###`` (level 3) headers.  Content
    before the first header (the preamble) is silently discarded.
    """
    lines = content.split("\n")
    sections: list[Section] = []
    current_header: str | None = None
    current_level: int = 0
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("### "):
            # Flush previous section
            if current_header is not None:
                sections.append(Section(
                    header=current_header,
                    level=current_level,
                    content="\n".join(current_lines),
                ))
            current_header = line[4:].strip()
            current_level = 3
            current_lines = [line]
        elif line.startswith("## "):
            if current_header is not None:
                sections.append(Section(
                    header=current_header,
                    level=current_level,
                    content="\n".join(current_lines),
                ))
            current_header = line[3:].strip()
            current_level = 2
            current_lines = [line]
        elif current_header is not None:
            current_lines.append(line)

    # Flush last section
    if current_header is not None:
        sections.append(Section(
            header=current_header,
            level=current_level,
            content="\n".join(current_lines),
        ))

    return sections


def filter_sections(sections: list[Section], exclude_set: set[str]) -> list[Section]:
    """Filter out sections whose headers appear in *exclude_set*.

    When a level-2 (``##``) section is excluded, all its level-3 children
    are excluded too.  A level-3 section listed explicitly is removed on
    its own without affecting siblings.
    """
    filtered: list[Section] = []
    skip_parent = False

    for section in sections:
        # Level-2: toggle parent skip flag
        if section.level == 2:
            if section.header in exclude_set:
                skip_parent = True
                continue
            else:
                skip_parent = False

        # Level-3 under an excluded parent
        if skip_parent and section.level == 3:
            continue

        # Level-3 excluded individually
        if section.header in exclude_set:
            continue

        filtered.append(section)

    return filtered
