import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import uuid

from db.schemas import LocationUpdate, LocationResponse
from utils.redis_helper import RedisHelper


class LocationService:
    def __init__(self):
        self.redis = RedisHelper()
        self.location_ttl = int(os.getenv('LOCATION_TTL'))  # 1 hour TTL
        self.stale_threshold_minutes = int(os.getenv('LOCATION_STALE_THRESHOLD'))  # Location is stale after 15 minutes

    def update_user_location(self, user_id: uuid.UUID, location_data: LocationUpdate) -> bool:
        """Update user's location in Redis."""
        try:
            location_key = f"user_location:{user_id}"

            # Prepare location data
            location_dict = {
                "user_id": str(user_id),
                "latitude": location_data.latitude,
                "longitude": location_data.longitude,
                "accuracy": location_data.accuracy,
                "altitude": location_data.altitude,
                "speed": location_data.speed,
                "heading": location_data.heading,
                "last_updated": datetime.now().isoformat(),
                "client_timestamp": location_data.timestamp.isoformat() if location_data.timestamp else None
            }

            # Store in Redis with TTL
            return self.redis.set_json(location_key, location_dict, expire=self.location_ttl)

        except Exception as e:
            print(f"Error updating location for user {user_id}: {e}")
            return False

    def get_user_location(self, user_id: uuid.UUID) -> Optional[LocationResponse]:
        """Get user's current location."""
        try:
            location_key = f"user_location:{user_id}"
            location_data = self.redis.get_json(location_key)

            if not location_data:
                return None

            # Check if location is stale
            last_updated = datetime.fromisoformat(location_data["last_updated"])
            is_stale = datetime.now() - last_updated > timedelta(minutes=self.stale_threshold_minutes)

            return LocationResponse(
                user_id=location_data["user_id"],
                latitude=float(location_data["latitude"]),
                longitude=float(location_data["longitude"]),
                accuracy=float(location_data["accuracy"]) if location_data["accuracy"] else None,
                altitude=float(location_data["altitude"]) if location_data["altitude"] else None,
                speed=float(location_data["speed"]) if location_data["speed"] else None,
                heading=float(location_data["heading"]) if location_data["heading"] else None,
                last_updated=last_updated,
                is_stale=is_stale
            )

        except Exception as e:
            print(f"Error getting location for user {user_id}: {e}")
            return None

    def get_multiple_user_locations(self, user_ids: List[uuid.UUID]) -> Dict[str, LocationResponse]:
        """Get locations for multiple users efficiently."""
        locations = {}

        for user_id in user_ids:
            location = self.get_user_location(user_id)
            if location:
                locations[str(user_id)] = location

        return locations

    def delete_user_location(self, user_id: uuid.UUID) -> bool:
        """Delete user's location (for privacy)."""
        location_key = f"user_location:{user_id}"
        return bool(self.redis.delete(location_key))

    def is_location_fresh(self, user_id: uuid.UUID, max_age_minutes: int = 5) -> bool:
        """Check if user's location is fresh (within max_age_minutes)."""
        location = self.get_user_location(user_id)
        if not location:
            return False

        age = datetime.now() - location.last_updated
        return age <= timedelta(minutes=max_age_minutes)