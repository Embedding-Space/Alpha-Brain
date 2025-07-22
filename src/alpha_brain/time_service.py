"""Time service for consistent datetime handling across Alpha Brain.

Philosophy:
- ISO in, human-readable out
- All internal representations use Pendulum
- All user-facing output is human-friendly
- Single source of truth for time formatting
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import geocoder
import pendulum
from pendulum import DateTime


class TimeService:
    """Centralized service for all datetime operations."""

    # Cache for timezone detection (1 hour TTL)
    _timezone_cache: ClassVar[dict[str, str | datetime | None]] = {
        "timezone": None,
        "expires_at": None,
    }

    @classmethod
    def get_timezone(cls) -> str:
        """Get current timezone using geo-IP, with caching.

        Returns:
            Timezone string (e.g., 'America/Los_Angeles')
        """
        now = datetime.now(tz=UTC)

        # Check cache
        cached_tz = cls._timezone_cache["timezone"]
        cached_expires = cls._timezone_cache["expires_at"]
        if (
            cached_tz
            and cached_expires
            and isinstance(cached_expires, datetime)
            and cached_expires > now
        ):
            return str(cached_tz)

        # Try to detect timezone
        try:
            g = geocoder.ip("me")
            if g.ok and g.raw and "timezone" in g.raw:
                timezone = g.raw["timezone"]
            else:
                # Fallback to UTC if detection fails
                timezone = "UTC"
        except Exception:
            # If geo-IP fails, fall back to UTC
            timezone = "UTC"

        # Cache for 1 hour
        cls._timezone_cache = {
            "timezone": timezone,
            "expires_at": now + timedelta(hours=1),
        }

        return timezone

    @classmethod
    def now(cls) -> DateTime:
        """Get current time as Pendulum DateTime in local timezone."""
        return pendulum.now(cls.get_timezone())
    
    @classmethod
    def get_local_timezone(cls) -> str:
        """Get the local timezone string (alias for get_timezone for clarity)."""
        return cls.get_timezone()

    @classmethod
    def parse(cls, dt: str | datetime | DateTime | None) -> DateTime:
        """Parse various datetime inputs to Pendulum DateTime.

        Args:
            dt: ISO string, Python datetime, Pendulum DateTime, or None (returns now())

        Returns:
            Pendulum DateTime object in local timezone
        """
        if dt is None:
            return cls.now()
        if isinstance(dt, DateTime):
            # Convert to local timezone if needed
            return dt.in_timezone(cls.get_timezone())
        if isinstance(dt, datetime):
            # Convert Python datetime to Pendulum DateTime
            # Assume naive datetimes are in UTC (common for DB storage)
            if dt.tzinfo is None:
                dt = pendulum.instance(dt, tz="UTC")
            else:
                dt = pendulum.instance(dt)
            return dt.in_timezone(cls.get_timezone())
        # pendulum.parse returns a DateTime for valid ISO strings
        parsed = pendulum.parse(dt)
        if not isinstance(parsed, DateTime):
            # This shouldn't happen with valid datetime strings, but handle it
            return cls.now()
        return parsed.in_timezone(cls.get_timezone())

    @classmethod
    def format_age(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime as human-readable age (e.g., '5 minutes ago').

        Args:
            dt: The datetime to format

        Returns:
            Human-readable age string
        """
        parsed = cls.parse(dt)
        return parsed.diff_for_humans()

    @classmethod
    def format_readable(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime as human-readable date/time with timezone.

        Uses smart formatting:
        - Today: "3:45 PM PST"
        - This year: "July 19 at 3:45 PM PST"
        - Other years: "July 19, 2024 at 3:45 PM PST"

        Args:
            dt: The datetime to format

        Returns:
            Human-readable datetime string with timezone
        """
        parsed = cls.parse(dt)
        now = cls.now()

        # Get timezone abbreviation
        # Use 'zz' for just the abbreviation (PST, PDT)
        tz_abbr = parsed.format("zz")

        if parsed.date() == now.date():
            # Today - just show time with timezone
            time_part = parsed.format("h:mm A")
            return f"{time_part} {tz_abbr}"
        if parsed.year == now.year:
            # This year - omit year
            date_time_part = parsed.format("MMMM D [at] h:mm A")
            return f"{date_time_part} {tz_abbr}"
        # Other years - full format
        date_time_part = parsed.format("MMMM D, YYYY [at] h:mm A")
        return f"{date_time_part} {tz_abbr}"

    @classmethod
    def format_short(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime as short human-readable string.

        Args:
            dt: The datetime to format

        Returns:
            Short datetime string (e.g., "Jul 19")
        """
        parsed = cls.parse(dt)
        now = cls.now()

        if parsed.date() == now.date():
            return "Today"
        if parsed.year == now.year:
            return parsed.format("MMM D")
        return parsed.format("MMM D, YYYY")

    @classmethod
    def format_iso(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime as ISO with offset (not Z).

        Args:
            dt: The datetime to format

        Returns:
            ISO string with offset (e.g., 2025-07-19T18:23:46+00:00)
        """
        parsed = cls.parse(dt)
        return parsed.isoformat()

    @classmethod
    def format_age_difference(cls, start_dt: str | datetime | DateTime, end_dt: str | datetime | DateTime) -> str:
        """Format the time difference between two datetimes as human-readable.
        
        Args:
            start_dt: The start datetime
            end_dt: The end datetime
            
        Returns:
            Human-readable time difference (e.g., "5 days", "2 hours", "1 minute")
        """
        start_parsed = cls.parse(start_dt)
        end_parsed = cls.parse(end_dt)
        
        diff = end_parsed - start_parsed
        total_seconds = diff.total_seconds()
        
        if total_seconds < 60:
            return "less than a minute"
        if total_seconds < 3600:  # Less than 1 hour
            minutes = int(total_seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        if total_seconds < 86400:  # Less than 1 day
            hours = int(total_seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
        days = int(total_seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''}"

    @classmethod
    def format_for_context(
        cls, dt: str | datetime | DateTime, include_age: bool = True
    ) -> str:
        """Format datetime with both readable and age info.

        Perfect for showing "when" something happened with full context.

        Args:
            dt: The datetime to format
            include_age: Whether to include the age component

        Returns:
            Combined format (e.g., "July 19 at 3:45 PM PST (2 hours ago)")
        """
        parsed = cls.parse(dt)
        readable = cls.format_readable(parsed)

        if include_age:
            age = cls.format_age(parsed)
            return f"{readable} ({age})"

        return readable

    @classmethod
    def format_full(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime in full, consistent format ideal for temporal grounding.

        Always shows: "November 19, 2024 at 2:38 PM PST"

        This format is designed for AI model consumption - it's complete,
        unambiguous, and doesn't change based on proximity to current time.

        Args:
            dt: The datetime to format

        Returns:
            Full datetime string with timezone
        """
        parsed = cls.parse(dt)
        date_time_part = parsed.format("dddd, MMMM D, YYYY [at] h:mm A")
        tz_abbr = parsed.format("zz")
        return f"{date_time_part} {tz_abbr}"

    @classmethod
    def format_datetime_scannable(cls, dt: str | datetime | DateTime) -> str:
        """Format datetime in scannable format for crystallization.

        Format: "7/20/2025 5:06 AM PDT"

        Args:
            dt: The datetime to format

        Returns:
            Scannable datetime string
        """
        parsed = cls.parse(dt)
        date_time_part = parsed.format("M/D/YYYY h:mm A")
        tz_abbr = parsed.format("zz")
        return f"{date_time_part} {tz_abbr}"
