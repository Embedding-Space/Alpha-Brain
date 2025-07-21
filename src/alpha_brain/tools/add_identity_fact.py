"""Add an identity fact to the chronicle of becoming."""

from datetime import UTC

import dateparser

from alpha_brain.identity_service import get_identity_service
from alpha_brain.time_service import TimeService


async def add_identity_fact(
    fact: str,
    datetime_str: str | None = None,
    day: int | None = None,
    month: int | None = None, 
    year: int | None = None,
    period: str | None = None,
    era: str | None = None,
) -> str:
    """
    Add a new identity fact to your chronicle.
    
    Identity facts record significant moments of change and choice.
    Specify how precisely you know when it happened:
    
    From most to least precise:
        datetime_str: Exact moment (e.g., "July 12, 2025 at 3:47 PM")
        day + month + year: Specific day
        month + year: Sometime that month  
        year: Sometime that year
        period: A range or season (e.g., "Summer 2025")
        era: Vague reference (e.g., "the before times")
        
    If none specified, records the current moment.
    
    Args:
        fact: The fact to record
        datetime_str: Full datetime string if you know exactly when
        day: Day of month (1-31) 
        month: Month (1-12)
        year: Year (e.g., 2025)
        period: Time period description
        era: Vague era description
        
    Returns:
        Confirmation of the recorded fact
    """
    service = get_identity_service()
    
    # Get local timezone
    import pendulum
    local_tz = TimeService.get_timezone()
    
    # Determine precision and construct datetime
    precision = None
    temporal_display = None
    parsed_time = None
    period_end = None
    
    try:
        if datetime_str:
            # Full datetime provided
            precision = "datetime"
            temporal_display = None  # Will use the formatted datetime
            
            settings = {
                'TIMEZONE': str(local_tz),
                'RETURN_AS_TIMEZONE_AWARE': True,
            }
            parsed_time = dateparser.parse(datetime_str, settings=settings)
            if not parsed_time:
                return f"Could not parse datetime: '{datetime_str}'"
                
        elif year is not None:
            # Build date from components
            if month is not None and day is not None:
                # Full date
                precision = "day"
                try:
                    # Create date in local timezone
                    parsed_time = pendulum.datetime(year, month, day, tz=local_tz)
                    temporal_display = parsed_time.format("MMMM D, YYYY")
                except ValueError as e:
                    return f"Invalid date: {e}"
                    
            elif month is not None:
                # Just month and year
                precision = "month"
                try:
                    # First day of the month at midnight
                    parsed_time = pendulum.datetime(year, month, 1, tz=local_tz)
                    temporal_display = parsed_time.format("MMMM YYYY")
                except ValueError as e:
                    return f"Invalid month/year: {e}"
                    
            else:
                # Just year
                precision = "year"
                try:
                    # First moment of the year
                    parsed_time = pendulum.datetime(year, 1, 1, tz=local_tz)
                    temporal_display = str(year)
                except ValueError as e:
                    return f"Invalid year: {e}"
                    
        elif period:
            # Handle periods
            precision = "period"
            temporal_display = period
            
            # Try to parse the period to get a sort date
            settings = {
                'TIMEZONE': str(local_tz),
                'RETURN_AS_TIMEZONE_AWARE': True,
            }
            parsed_time = dateparser.parse(period, settings=settings)
            if not parsed_time:
                # Default to current time if we can't parse
                parsed_time = pendulum.now(local_tz)
                
        elif era:
            # Very vague temporal reference
            precision = "era"
            temporal_display = era
            
            # Use year 1900 as sentinel for "long ago"
            parsed_time = pendulum.datetime(1900, 1, 1, tz="UTC")
            
        else:
            # Nothing provided - use current moment
            precision = "datetime"
            parsed_time = pendulum.now(local_tz)
            
        # Ensure UTC storage
        if hasattr(parsed_time, 'in_timezone'):
            parsed_time = parsed_time.in_timezone("UTC")
        else:
            parsed_time = parsed_time.replace(tzinfo=UTC)
            
    except Exception as e:
        return f"Error constructing temporal information: {e}"
    
    # Add the fact with precision metadata
    identity_fact = await service.add_fact(
        fact=fact,
        occurred_at=parsed_time,
        temporal_precision=precision,
        temporal_display=temporal_display,
        period_end=period_end
    )
    
    # Format the response based on precision
    if temporal_display:
        occurred_str = temporal_display
    else:
        occurred_str = TimeService.format_readable(identity_fact.occurred_at)
    
    return f"Recorded identity fact: \"{fact}\" ({occurred_str})"
