"""
LiveKit Service - Handles token generation and room management for Universal Intercom
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from livekit import api
from utils.app_logger import createLogger

logger = createLogger("livekit_service")


class LiveKitService:
    """Service for managing LiveKit rooms and access tokens"""
    
    def __init__(self):
        self.api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
        self.api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
        self.livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        
        if not self.api_key or not self.api_secret:
            logger.warning("LiveKit API credentials not configured")
    
    def get_room_name(self, ride_id: UUID) -> str:
        """Generate consistent room name for a ride"""
        return f"ride_{str(ride_id)}"
    
    def generate_token(
        self,
        ride_id: UUID,
        user_id: UUID,
        user_name: str,
        is_lead: bool = False,
        ttl_hours: int = 24
    ) -> Optional[str]:
        """
        Generate a LiveKit access token for a user.
        
        Args:
            ride_id: The ride UUID (used for room name)
            user_id: The user UUID (used as participant identity)
            user_name: Display name for the user
            is_lead: If True, grants publish permissions (broadcaster)
            ttl_hours: Token validity in hours
        
        Returns:
            JWT token string or None if generation fails
        """
        try:
            room_name = self.get_room_name(ride_id)
            identity = str(user_id)
            
            # Create access token using the fluent API (livekit-api 0.6.x)
            # Lead can publish (broadcast), all can subscribe (listen)
            token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(identity)
                .with_name(user_name or "Rider")
                .with_ttl(timedelta(hours=ttl_hours))
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=is_lead,  # Only Lead can broadcast
                    can_subscribe=True,  # Everyone can listen
                    can_publish_data=is_lead,  # Lead can send data messages
                ))
            )
            
            jwt_token = token.to_jwt()
            
            logger.info(f"Generated LiveKit token for user {user_id} in room {room_name}, is_lead={is_lead}")
            return jwt_token
            
        except Exception as e:
            logger.exception(f"Failed to generate LiveKit token: {e}")
            return None
    
    def get_livekit_url(self) -> str:
        """Get the LiveKit server URL for client connection"""
        return self.livekit_url
    
    async def list_room_participants(self, ride_id: UUID) -> list:
        """
        List current participants in a room.
        Useful for showing who's connected to intercom.
        """
        try:
            room_name = self.get_room_name(ride_id)
            http_url = self.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
            
            async with api.LiveKitAPI(http_url, self.api_key, self.api_secret) as lkapi:
                response = await lkapi.room.list_participants(
                    api.ListParticipantsRequest(room=room_name)
                )
            
            # Extract relevant info for debuging
            participants_data = []
            for p in response.participants:
                tracks = []
                for t in p.tracks:
                    tracks.append({
                        "sid": t.sid,
                        "type": str(t.type),  # AUDIO or VIDEO
                        "source": str(t.source), # MICROPHONE, CAMERA, etc
                        "muted": t.muted
                    })
                
                participants_data.append({
                    "identity": p.identity,
                    "name": p.name,
                    "state": str(p.state),
                    "joined_at": str(p.joined_at),
                    "tracks": tracks
                })
                
            return participants_data
        except Exception as e:
            logger.exception(f"Failed to list room participants: {e}")
            return []
    
    async def remove_participant(self, ride_id: UUID, user_id: UUID) -> bool:
        """
        Remove a participant from the room (e.g., when Lead changes)
        """
        try:
            room_name = self.get_room_name(ride_id)
            http_url = self.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
            
            async with api.LiveKitAPI(http_url, self.api_key, self.api_secret) as lkapi:
                await lkapi.room.remove_participant(
                    api.RoomParticipantIdentity(room=room_name, identity=str(user_id))
                )
            logger.info(f"Removed participant {user_id} from room {room_name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to remove participant: {e}")
            return False
    
    async def mute_participant(self, ride_id: UUID, user_id: UUID, mute: bool = True) -> bool:
        """
        Mute/unmute a participant's audio track.
        """
        try:
            room_name = self.get_room_name(ride_id)
            http_url = self.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
            
            async with api.LiveKitAPI(http_url, self.api_key, self.api_secret) as lkapi:
                await lkapi.room.mute_published_track(
                    api.MuteRoomTrackRequest(
                        room=room_name,
                        identity=str(user_id),
                        muted=mute,
                        # track_sid would need to be obtained from track listing
                    )
                )
            return True
        except Exception as e:
            logger.exception(f"Failed to mute participant: {e}")
            return False


# Singleton instance
livekit_service = LiveKitService()
