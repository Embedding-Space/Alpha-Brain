"""Output template management for tool responses."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from alpha_brain.time_service import TimeService

# Set up Jinja2 environment for output templates
TEMPLATES_DIR = Path(__file__).parent
OUTPUT_TEMPLATES_DIR = TEMPLATES_DIR / "outputs"

output_env = Environment(
    loader=FileSystemLoader(OUTPUT_TEMPLATES_DIR),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Add custom filters for time formatting
output_env.filters["format_time"] = TimeService.format_for_context
output_env.filters["format_time_readable"] = TimeService.format_readable
output_env.filters["format_time_age"] = TimeService.format_age
output_env.filters["format_time_full"] = TimeService.format_full


def pluralize(count: int, singular: str = "", plural: str = "s") -> str:
    """Simple pluralization filter."""
    if count == 1:
        return singular
    return plural


# Add pluralization filter
output_env.filters["pluralize"] = pluralize


def format_identity_fact_time(fact) -> str:
    """Format identity fact time based on precision level."""
    # If there's a temporal_display, use it
    if hasattr(fact, 'temporal_display') and fact.temporal_display:
        return fact.temporal_display
    
    # Otherwise format based on precision
    precision = getattr(fact, 'temporal_precision', 'day')
    
    if precision == 'datetime':
        return TimeService.format_readable(fact.occurred_at)
    if precision == 'day':
        # Format as just the date
        return TimeService.parse(fact.occurred_at).format("MMMM D, YYYY")
    if precision == 'month':
        return TimeService.parse(fact.occurred_at).format("MMMM YYYY")
    if precision == 'year':
        return TimeService.parse(fact.occurred_at).format("YYYY")
    # For periods and eras, use display or fallback
    return getattr(fact, 'temporal_display', TimeService.format_readable(fact.occurred_at))


# Add identity fact formatting filter
output_env.filters["format_identity_time"] = format_identity_fact_time


def render_output(tool_name: str, **context) -> str:
    """
    Render an output template for a tool.

    Args:
        tool_name: Name of the tool (e.g., 'remember', 'get_memory')
        **context: Variables to pass to the template

    Returns:
        Rendered output string

    Raises:
        jinja2.TemplateNotFound: If the template doesn't exist (this is fatal)
    """
    # Always inject current time for temporal grounding
    context["current_time"] = TimeService.now()

    template_name = f"{tool_name}_output.j2"
    template = output_env.get_template(template_name)
    return template.render(**context)
