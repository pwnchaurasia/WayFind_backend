from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class CheckInRequest(BaseModel):
    """Request to check in at a location"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    checkpoint_type: Optional[str] = None  # Optional - can auto-detect


class LocationUpdateRequest(BaseModel):
    """Request to update user's location during active ride"""
    latitude: float
    longitude: float
    heading: Optional[float] = None  # Direction in degrees
    speed: Optional[float] = None  # Speed in km/h
    accuracy: Optional[float] = None


class AlertRequest(BaseModel):
    """Request to send an alert (SOS, need help, etc.)"""
    alert_type: str  # sos_alert, low_fuel, breakdown, need_help
    message: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ActivityUser(BaseModel):
    """User info in activity response"""
    id: str
    name: Optional[str] = None
    profile_picture: Optional[str] = None


class ActivityCheckpoint(BaseModel):
    """Checkpoint info in activity response"""
    id: str
    type: str
    address: Optional[str] = None


class ActivityResponse(BaseModel):
    """Single activity in the feed"""
    id: str
    activity_type: str
    message: Optional[str] = None
    user: Optional[ActivityUser] = None
    checkpoint: Optional[ActivityCheckpoint] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityFeedResponse(BaseModel):
    """Activity feed response"""
    status: str
    activities: List[ActivityResponse]
    total: int
    has_more: bool


class RiderLocationResponse(BaseModel):
    """Rider location for map view"""
    user_id: str
    name: Optional[str] = None
    profile_picture: Optional[str] = None
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    last_updated: datetime
    attendance_status: Optional[str] = None  # present, absent, etc.


class LiveRideDataResponse(BaseModel):
    """Comprehensive live ride data"""
    status: str
    ride_status: str  # planned, active, completed
    activities: List[ActivityResponse]
    rider_locations: List[RiderLocationResponse]
    checkpoints: List[dict]
    my_attendance: dict
