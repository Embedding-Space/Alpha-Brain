"""Parse temporal intervals from natural language and ISO 8601 formats."""

import re
from typing import cast

import dateparser
import pendulum
from pendulum import DateTime, Duration
from structlog import get_logger

from alpha_brain.time_service import TimeService

logger = get_logger()


def parse_interval(interval_str: str) -> tuple[DateTime, DateTime]:
    """
    Parse a time interval string into start and end datetimes.
    
    Supports:
    - Natural language: "yesterday", "past 3 hours", "this week"
    - ISO 8601 intervals: "2024-01-01/2024-01-31", "P3H/", etc.
    
    Args:
        interval_str: The interval string to parse
        
    Returns:
        Tuple of (start_datetime, end_datetime) in UTC
        
    Raises:
        ValueError: If the interval cannot be parsed
    """
    # Check for ISO 8601 interval format first (contains "/")
    if "/" in interval_str:
        return parse_iso_interval(interval_str)
    
    # Otherwise use natural language parsing
    return parse_natural_interval(interval_str)


def parse_iso_interval(interval_str: str) -> tuple[DateTime, DateTime]:
    """
    Parse ISO 8601 interval format.
    
    Formats:
    - start/end: "2024-01-01/2024-01-31"
    - start/duration: "2024-01-01/P7D"
    - duration/end: "P3H/2024-01-01T18:00:00Z"
    - duration/: "P3H/" (3 hours before now)
    """
    parts = interval_str.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid ISO interval format: {interval_str}")
    
    left, right = parts
    now = pendulum.now("UTC")
    
    def parse_duration(duration_str: str) -> Duration:
        """Parse ISO 8601 duration string to pendulum Duration."""
        # Simple parser for common ISO 8601 durations
        # Full spec would require a more complex parser
        import re
        pattern = r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?"
        match = re.match(pattern, duration_str)
        if not match:
            raise ValueError(f"Invalid ISO 8601 duration: {duration_str}")
        
        years, months, days, hours, minutes, seconds = match.groups()
        
        # Create duration (note: pendulum doesn't support years/months in duration)
        # so we convert to days (approximate)
        total_days = int(days or 0)
        if years:
            total_days += int(years) * 365
        if months:
            total_days += int(months) * 30
            
        return pendulum.duration(
            days=total_days,
            hours=int(hours or 0),
            minutes=int(minutes or 0),
            seconds=float(seconds or 0)
        )
    
    try:
        # Case 1: duration/end (e.g., "P3H/2024-04-03T18:00:00Z")
        if left.startswith("P"):
            duration = parse_duration(left)
            if right:
                end = cast(DateTime, pendulum.parse(right))
                return (end - duration, end)
            # Case 3: duration/ (e.g., "P3H/")
            return (now - duration, now)
        
        # Case 2: start/duration (e.g., "2024-04-03T14:00:00Z/P3H")
        if right.startswith("P"):
            start = cast(DateTime, pendulum.parse(left))
            duration = parse_duration(right)
            return (start, start + duration)
        
        # Case 4: start/end (e.g., "2024-04-03/2024-04-05")
        start = cast(DateTime, pendulum.parse(left))
        end = cast(DateTime, pendulum.parse(right))
        # If only dates (no time), end should be end of day
        if not right.count("T"):  # No time component
            end = end.end_of("day")
        return (start, end)
            
    except Exception as e:
        raise ValueError(
            f"Invalid ISO 8601 interval. Expected format: "
            f"'start/end', 'start/P[duration]', 'P[duration]/end', or 'P[duration]/'. "
            f"Got: {interval_str}. Error: {e!s}"
        ) from e


def parse_natural_interval(interval_str: str) -> tuple[DateTime, DateTime]:  # noqa: PLR0911, PLR0912
    """
    Parse natural language time intervals in local timezone.
    
    Returns UTC boundaries for database queries, but calculates intervals
    based on local time (e.g., "yesterday" = local midnight to midnight).
    
    Examples:
    - "yesterday"
    - "today"
    - "past 3 hours"
    - "this week"
    - "last month"
    """
    # Use TimeService to get actual local timezone (from geo-IP)
    local_tz = TimeService.get_timezone()
    now_local = pendulum.now(local_tz)  # Actual local timezone
    now_utc = pendulum.now("UTC")  # For duration-based calculations
    interval_lower = interval_str.lower().strip()
    
    # Common cases with explicit handling (use local time for date boundaries)
    if interval_lower == "today":
        start_local = now_local.start_of("day")
        end_local = now_local
        return (start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
    
    if interval_lower == "yesterday":
        yesterday_local = now_local.subtract(days=1)
        start_local = yesterday_local.start_of("day") 
        end_local = yesterday_local.end_of("day")
        return (start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
    
    if interval_lower == "this week":
        # Week starts on Sunday for consistency
        week_start_local = now_local.start_of("week")
        end_local = now_local
        return (week_start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
    
    if interval_lower == "last week":
        last_week_local = now_local.subtract(weeks=1)
        week_start_local = last_week_local.start_of("week")
        week_end_local = last_week_local.end_of("week")
        return (week_start_local.in_timezone("UTC"), week_end_local.in_timezone("UTC"))
    
    if interval_lower == "this month":
        start_local = now_local.start_of("month")
        end_local = now_local
        return (start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
    
    if interval_lower == "last month":
        last_month_local = now_local.subtract(months=1)
        start_local = last_month_local.start_of("month")
        end_local = last_month_local.end_of("month")
        return (start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
    
    # Handle "past N hours/days/weeks" patterns (use UTC for duration-based)
    past_pattern = r"^(?:past|last)\s+(\d+)\s+(hour|day|week|month)s?$"
    if match := re.match(past_pattern, interval_lower):
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == "hour":
            start = now_utc.subtract(hours=amount)
        elif unit == "day":
            start = now_utc.subtract(days=amount)
        elif unit == "week":
            start = now_utc.subtract(weeks=amount)
        else:  # unit == "month"
            start = now_utc.subtract(months=amount)
        
        return (start, now_utc)
    
    # Try dateparser as fallback (use local timezone for day names like "Thursday")
    try:
        # Parse in local timezone for day names
        parsed = dateparser.parse(
            interval_str,
            settings={
                'PREFER_DATES_FROM': 'past',
                'RETURN_AS_TIMEZONE_AWARE': True,
                'TIMEZONE': local_tz,
            }
        )
        
        if parsed:
            parsed_dt = pendulum.instance(parsed)
            
            # If it parsed to a specific time, assume the whole day
            # unless it looks like a duration ("3 hours ago")
            if any(word in interval_lower for word in ["ago", "past", "last"]):
                # It's a duration from now - convert to UTC
                return (parsed_dt.in_timezone("UTC"), now_utc)
            # It's a specific day - get local day boundaries and convert to UTC
            start_local = parsed_dt.start_of("day")
            end_local = parsed_dt.end_of("day")
            return (start_local.in_timezone("UTC"), end_local.in_timezone("UTC"))
        # dateparser returned None - provide helpful suggestions
        logger.debug(f"dateparser returned None for '{interval_str}'")
            
    except Exception as e:
        # dateparser threw an exception - include the original error
        logger.debug(f"dateparser failed for '{interval_str}': {e}")
        raise ValueError(f"Could not parse interval: '{interval_str}'. Dateparser error: {e}") from e
    
    # Provide more helpful error message with examples
    raise ValueError(
        f"Could not parse interval: '{interval_str}'. "
        f"Supported formats include: 'yesterday', 'today', 'past 3 hours', 'last week', "
        f"'Thursday', 'July 19, 2025', or ISO 8601 intervals like '2024-01-01/2024-01-31'."
    )
