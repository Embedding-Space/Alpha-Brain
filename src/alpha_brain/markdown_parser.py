"""Markdown parser for converting documents to structured JSON."""

import re
from typing import Any

import mistune
from mistune.renderers.rst import RSTRenderer


class StructureExtractor:
    """Custom Mistune renderer that extracts document structure."""
    
    def __init__(self):
        self.sections = []
        self.current_section = None
        self.current_content = []
        self.in_heading = False
        
    def heading(self, text: str, level: int) -> str:
        """Process a heading."""
        # Save previous section if exists
        if self.current_section:
            self.current_section["content"] = ''.join(self.current_content).strip()
            self.sections.append(self.current_section)
            self.current_content = []
        
        # Create new section
        self.current_section = {
            "level": level,
            "title": text,
            "content": "",
            "id": _slugify(text)
        }
        
        # Return empty string since we're extracting, not rendering
        return ""
    
    def paragraph(self, text: str) -> str:
        """Process a paragraph."""
        self.current_content.append(text + "\n\n")
        return ""
    
    def list(self, text: str, ordered: bool, start: int | None = None) -> str:
        """Process a list."""
        if ordered and start is not None:
            self.current_content.append(f"{text}\n")
        else:
            self.current_content.append(f"{text}\n")
        return ""
    
    def list_item(self, text: str, level: int) -> str:
        """Process a list item."""
        prefix = "  " * (level - 1)
        return f"{prefix}- {text}\n"
    
    def block_code(self, code: str, info: str | None = None) -> str:
        """Process a code block."""
        if info:
            self.current_content.append(f"```{info}\n{code}\n```\n\n")
        else:
            self.current_content.append(f"```\n{code}\n```\n\n")
        return ""
    
    def block_quote(self, text: str) -> str:
        """Process a blockquote."""
        lines = text.strip().split('\n')
        quoted = '\n'.join(f"> {line}" for line in lines)
        self.current_content.append(f"{quoted}\n\n")
        return ""
    
    def table(self, header: str, body: str) -> str:
        """Process a table."""
        self.current_content.append(f"{header}{body}\n")
        return ""
    
    def finalize(self) -> list[dict]:
        """Finalize and return all sections."""
        # Don't forget the last section
        if self.current_section:
            self.current_section["content"] = ''.join(self.current_content).strip()
            self.sections.append(self.current_section)
        elif self.current_content:
            # No headers found, treat entire content as one section
            self.sections.append({
                "level": 0,
                "title": "Content",
                "content": ''.join(self.current_content).strip(),
                "id": "content"
            })
        
        return self.sections


class StructureRenderer(mistune.renderers.BaseRenderer):
    """Mistune renderer that builds document structure."""
    
    def __init__(self):
        super().__init__()
        self.extractor = StructureExtractor()
    
    def heading(self, text: str, level: int) -> str:
        return self.extractor.heading(text, level)
    
    def paragraph(self, text: str) -> str:
        return self.extractor.paragraph(text)
    
    def list(self, text: str, ordered: bool, start: int | None = None) -> str:
        return self.extractor.list(text, ordered, start)
    
    def list_item(self, text: str, level: int) -> str:
        return self.extractor.list_item(text, level)
    
    def block_code(self, code: str, info: str | None = None) -> str:
        return self.extractor.block_code(code, info)
    
    def block_quote(self, text: str) -> str:
        return self.extractor.block_quote(text)
    
    def table(self, header: str, body: str) -> str:
        return self.extractor.table(header, body)
    
    def text(self, text: str) -> str:
        return text
    
    def emphasis(self, text: str) -> str:
        return f"*{text}*"
    
    def strong(self, text: str) -> str:
        return f"**{text}**"
    
    def link(self, text: str, url: str, title: str | None = None) -> str:
        if title:
            return f"[{text}]({url} \"{title}\")"
        return f"[{text}]({url})"
    
    def image(self, text: str, url: str, title: str | None = None) -> str:
        if title:
            return f"![{text}]({url} \"{title}\")"
        return f"![{text}]({url})"
    
    def inline_code(self, text: str) -> str:
        return f"`{text}`"
    
    def linebreak(self) -> str:
        return "\n"
    
    def thematic_break(self) -> str:
        self.extractor.current_content.append("---\n\n")
        return ""


def parse_markdown_to_structure(content: str) -> dict[str, Any]:
    """Parse Markdown content into a structured JSON representation.
    
    Args:
        content: Raw Markdown text
        
    Returns:
        Dictionary with document structure including sections and hierarchy
    """
    # Create custom renderer
    renderer = StructureRenderer()
    
    # Create markdown parser with our custom renderer
    markdown = mistune.create_markdown(renderer=renderer)
    
    # Parse the content (this populates the renderer's sections)
    markdown(content)
    
    # Get sections from the renderer
    sections = renderer.extractor.finalize()
    
    structure = {
        "sections": sections,
        "hierarchy": _build_hierarchy(sections)
    }
    
    return structure


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def _build_hierarchy(sections: list[dict]) -> list[dict]:
    """Build a hierarchical structure from flat sections.
    
    This creates a nested structure where H2s are children of H1s, etc.
    """
    if not sections:
        return []
    
    # Create a copy of sections with children arrays
    hierarchy = []
    stack = []  # Stack to track parent sections
    
    for section in sections:
        section_copy = section.copy()
        section_copy["children"] = []
        
        # Pop from stack until we find the right parent level
        while stack and stack[-1]["level"] >= section_copy["level"]:
            stack.pop()
        
        if stack:
            # Add as child to the last item in stack
            stack[-1]["children"].append(section_copy)
        else:
            # Top-level section
            hierarchy.append(section_copy)
        
        # Add to stack for potential children
        stack.append(section_copy)
    
    return hierarchy


def extract_section_by_id(structure: dict[str, Any], section_id: str) -> dict | None:
    """Extract a specific section by its ID.
    
    Args:
        structure: The parsed document structure
        section_id: The ID of the section to find
        
    Returns:
        The section dict if found, None otherwise
    """
    for section in structure.get("sections", []):
        if section.get("id") == section_id:
            return section
    return None


def get_table_of_contents(structure: dict[str, Any]) -> list[str]:
    """Generate a table of contents from the document structure.
    
    Returns:
        List of strings representing the TOC with indentation
    """
    toc = []
    
    def _add_to_toc(sections: list[dict], indent: int = 0):
        for section in sections:
            # Add indentation based on header level
            prefix = "  " * indent
            toc.append(f"{prefix}- {section['title']}")
            
            # Recursively add children
            if "children" in section:
                _add_to_toc(section["children"], indent + 1)
    
    hierarchy = structure.get("hierarchy", [])
    _add_to_toc(hierarchy)
    
    return toc