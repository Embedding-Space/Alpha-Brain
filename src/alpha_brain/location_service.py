"""Location service for getting user location at appropriate granularity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import geocoder


class LocationService:
    """Service for location detection with appropriate vagueness."""
    
    # Cache for location (1 hour TTL)
    _location_cache: ClassVar[dict[str, str | datetime | None]] = {
        "location": None,
        "expires_at": None,
    }
    
    @classmethod
    def get_location(cls) -> str:
        """Get current location from geo-IP.
        
        Returns:
            Location string like "Burbank, California"
        """
        now = datetime.now(tz=UTC)
        
        # Check cache
        cached_location = cls._location_cache["location"]
        cached_expires = cls._location_cache["expires_at"]
        if (
            cached_location
            and cached_expires
            and isinstance(cached_expires, datetime)
            and cached_expires > now
        ):
            return str(cached_location)
        
        # Try to detect location
        try:
            g = geocoder.ip("me")
            if g.ok:
                city = g.city
                state = g.state if hasattr(g, 'state') else None
                country = g.country
                
                # Just use what we get - simple and honest
                if city and state:
                    location = f"{city}, {state}"
                elif city and country:
                    location = f"{city}, {country}"
                elif state:
                    location = state
                elif country:
                    location = country
                else:
                    location = "Unknown location"
            else:
                location = "Unknown location"
                
        except Exception:
            location = "Unknown location"
        
        # Cache for 1 hour
        cls._location_cache = {
            "location": location,
            "expires_at": now + timedelta(hours=1),
        }
        
        return location
