"""Markdown parser for converting documents to structured JSON."""

from __future__ import annotations

import re
from typing import Any

import mistune


def parse_markdown_to_structure(content: str) -> dict[str, Any]:
    """Parse Markdown content into a structured JSON representation.
    
    Args:
        content: Raw Markdown text
        
    Returns:
        Dictionary with document structure including sections and hierarchy
    """
    # Create a markdown parser
    markdown = mistune.create_markdown(renderer=None)
    
    # Parse to AST
    tokens = markdown(content)
    
    # Extract sections from tokens
    sections = []
    current_section = None
    current_content = []
    
    def render_content(tokens_list):
        """Render a list of tokens back to markdown."""
        result = []
        for token in tokens_list:
            if token['type'] == 'paragraph':
                result.append(render_inline(token['children']) + '\n')
            elif token['type'] == 'list':
                result.append(render_list(token) + '\n')
            elif token['type'] == 'block_code':
                attrs = token.get('attrs', {})
                info = attrs.get('info', '')
                code = token.get('raw', '').rstrip()
                if info:
                    result.append(f"```{info}\n{code}\n```\n")
                else:
                    result.append(f"```\n{code}\n```\n")
            elif token['type'] == 'block_quote':
                children_text = render_content(token['children'])
                lines = children_text.strip().split('\n')
                quoted = '\n'.join(f"> {line}" for line in lines)
                result.append(quoted + '\n')
            elif token['type'] == 'table':
                result.append(render_table(token) + '\n')
            elif token['type'] == 'thematic_break':
                result.append('---\n')
        return '\n'.join(result)
    
    def render_inline(children):
        """Render inline tokens."""
        result = []
        for child in children:
            if child['type'] == 'text':
                result.append(child['raw'])
            elif child['type'] == 'emphasis':
                result.append(f"*{render_inline(child['children'])}*")
            elif child['type'] == 'strong':
                result.append(f"**{render_inline(child['children'])}**")
            elif child['type'] == 'link':
                text = render_inline(child['children'])
                url = child['attrs']['url']
                title = child['attrs'].get('title', '')
                if title:
                    result.append(f"[{text}]({url} \"{title}\")")
                else:
                    result.append(f"[{text}]({url})")
            elif child['type'] == 'image':
                text = child['attrs'].get('alt', '')
                url = child['attrs']['url']
                title = child['attrs'].get('title', '')
                if title:
                    result.append(f"![{text}]({url} \"{title}\")")
                else:
                    result.append(f"![{text}]({url})")
            elif child['type'] == 'code_span':
                result.append(f"`{child['raw']}`")
            elif child['type'] == 'linebreak':
                result.append('\n')
        return ''.join(result)
    
    def render_list(token):
        """Render a list."""
        items = []
        for item in token['children']:
            # Extract text from list item's block_text children
            item_texts = []
            for child in item['children']:
                if child['type'] == 'block_text':
                    item_texts.append(render_inline(child['children']))
                else:
                    # Handle nested content
                    item_texts.append(render_content([child]).strip())
            
            item_text = ''.join(item_texts)
            items.append(f"- {item_text}")
        return '\n'.join(items)
    
    def render_table(token):
        """Render a table (simplified)."""
        # For now, just indicate there's a table
        return "[Table content]"
    
    # Process tokens
    for token in tokens:
        if token['type'] == 'heading':
            # Save previous section if exists
            if current_section:
                current_section['content'] = render_content(current_content).strip()
                sections.append(current_section)
                current_content = []
            
            # Create new section
            heading_text = render_inline(token['children'])
            current_section = {
                'level': token['attrs']['level'],
                'title': heading_text,
                'content': '',
                'id': _slugify(heading_text)
            }
        else:
            # Accumulate content
            current_content.append(token)
    
    # Don't forget the last section
    if current_section:
        current_section['content'] = render_content(current_content).strip()
        sections.append(current_section)
    elif current_content:
        # No headers found, treat entire content as one section
        sections.append({
            'level': 0,
            'title': 'Content',
            'content': render_content(current_content).strip(),
            'id': 'content'
        })
    
    return {
        "sections": sections,
        "hierarchy": _build_hierarchy(sections)
    }


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Remove leading/trailing hyphens
    return slug.strip('-')


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
