"""Prompt template management using Jinja2."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Set up Jinja2 environment
PROMPTS_DIR = Path(__file__).parent
env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **kwargs) -> str:
    """
    Render a prompt template with the given context.

    Args:
        template_name: Name of the template file (e.g., 'memory_analysis.j2')
        **kwargs: Variables to pass to the template

    Returns:
        Rendered prompt string
    """
    template = env.get_template(template_name)
    return template.render(**kwargs)
