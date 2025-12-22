from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CheckInRequest(BaseModel):
    checkpoint_type: str = Field(..., pattern="^(meetup|destination|disbursement|home)$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AttendanceRecordResponse(BaseModel):
    id: UUID
    ride_id: UUID
    user_id: UUID
    checkpoint_type: str
    reached_at: datetime
    latitude: float
    longitude: float
    distance_traveled_km: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckInResponse(BaseModel):
    attendance_record: AttendanceRecordResponse
    message: str
    is_first_checkin: bool = False