from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CreateCheckpoint(BaseModel):
    type: str = Field(..., pattern="^(meetup|destination|disbursement)$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: Optional[int] = Field(50, ge=10, le=1000)


class CheckpointResponse(BaseModel):
    id: UUID
    ride_id: UUID
    type: str
    latitude: float
    longitude: float
    radius_meters: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateRide(BaseModel):
    organization_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    max_riders: Optional[int] = Field(30, ge=1, le=100)
    requires_payment: bool = False
    amount: float = Field(0.0, ge=0.0)
    checkpoints: List[CreateCheckpoint]


class UpdateRide(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[str] = Field(None, pattern="^(planned|active|completed)$")
    max_riders: Optional[int] = Field(None, ge=1, le=100)
    requires_payment: Optional[bool] = None
    amount: Optional[float] = Field(None, ge=0.0)


class RideResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    status: str
    max_riders: int
    requires_payment: bool
    amount: float
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    updated_at: datetime
    checkpoints: Optional[List[CheckpointResponse]] = None
    participants_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class JoinRide(BaseModel):
    vehicle_info_id: Optional[UUID] = None
    is_pillion: Optional[bool] = False


class UpdateRideParticipant(BaseModel):
    role: str = Field(..., pattern="^(rider|lead|marshal|sweep)$")


class RideParticipantResponse(BaseModel):
    id: UUID
    ride_id: UUID
    user_id: UUID
    vehicle_info_id: Optional[UUID] = None
    role: str
    has_paid: bool
    paid_amount: float
    payment_date: Optional[datetime]
    registered_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RideJoinResponse(BaseModel):
    participant: RideParticipantResponse
    ride: RideResponse
    message: str


class RideHistoryResponse(BaseModel):
    rides: List[RideResponse]
    total_distance_km: float = 0
    total_rides: int = 0

class MarkPaymentRequest(BaseModel):
    participant_id: UUID
    amount: float = Field(..., ge=0.0)