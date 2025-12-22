from typing import Optional, List
from uuid import UUID
import random
from datetime import datetime, timedelta
from fastapi import Request
from pydantic import BaseModel, EmailStr, HttpUrl, computed_field, field_validator, root_validator, Field


class UserRegistration(BaseModel):
    phone_number: str

class OTPVerification(BaseModel):
    phone_number: str
    otp: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfile(BaseModel):
    email: EmailStr
    name: str
    profile_picture_url: Optional[HttpUrl] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: UUID
    name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    is_active: bool
    profile_picture_url: Optional[HttpUrl]

    @computed_field
    @property
    def is_profile_complete(self) -> bool:
        ## at least two fields are there then it's true
        return sum(bool(field) for field in [self.name, self.email, self.profile_picture_url]) >= 2

    class Config:
        from_attributes = True


class GroupMemberResponse(BaseModel):
    # User fields
    id: UUID
    name: str
    email: Optional[EmailStr]
    phone_number: Optional[str]
    is_active: bool
    profile_picture_url: Optional[HttpUrl]

    # Group membership fields
    role: str  # or whatever type your role field is
    is_member_active: bool  # renamed to avoid confusion with user's is_active


    @field_validator('name', mode='before')
    @classmethod
    def remove_empty_name(cls, name_val: str) -> str:
        if not name_val or (isinstance(name_val, str) and name_val.strip() == ""):
            return "No Name"
        return name_val

    @field_validator('email', mode='before')
    @classmethod
    def remove_empty_email(cls, email_val: str) -> str:
        if not email_val or (isinstance(email_val, str) and email_val.strip() == ""):
            return "noemail@example.com"
        return email_val

    @computed_field
    @property
    def last_seen(self) -> datetime:
        #TODO fix this random last_seen
        # Random time within last 7 days
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        return datetime.now() - timedelta(days=days_ago, hours=hours_ago)

    @computed_field
    @property
    def is_profile_complete(self) -> bool:
        return sum(bool(field) for field in [self.name, self.email, self.profile_picture_url]) >= 2

    class Config:
        from_attributes = True

class CreateGroup(BaseModel):
    name: str

class GroupResponse(BaseModel):
    id: UUID
    owner: UUID
    name: str
    code: str
    members_count: int

    class Config:
        from_attributes = True

    @staticmethod
    def generate_group_join_url(request: Request, code: str) -> str:
        """Generates a full join URL dynamically."""
        return str(request.url_for("join_group_with_code", code=code))

    def to_response(self, request:Request) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "owner_id": str(self.owner),
            "join_url": GroupResponse.generate_group_join_url(request, self.code),
            "members_count": self.members_count,
        }


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)  # GPS accuracy in meters
    altitude: Optional[float] = None
    speed: Optional[float] = Field(None, ge=0)  # Speed in m/s
    heading: Optional[float] = Field(None, ge=0, le=360)  # Direction in degrees
    timestamp: Optional[datetime] = None  # Client timestamp (for validation)


class LocationResponse(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float]
    altitude: Optional[float]
    speed: Optional[float]
    heading: Optional[float]
    last_updated: datetime
    is_stale: bool  # True if location is older than X minutes


class UserWithLocation(BaseModel):
    id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    profile_picture_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    timestamp: Optional[datetime] = None


# NEW: Organization Schemas


class CreateOrganization(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    logo: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AddOrganizationMember(BaseModel):
    user_id: UUID
    role: str  # FOUNDER, CO_FOUNDER, ADMIN


class OrganizationMemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Populated user info
    user: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True


# NEW: Vehicle Schemas


class CreateVehicle(BaseModel):
    make: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    license_plate: Optional[str] = Field(None, max_length=20)
    is_primary: bool = False
    is_pillion: bool = False


class VehicleResponse(BaseModel):
    id: UUID
    user_id: UUID
    make: str
    model: str
    year: Optional[int]
    license_plate: Optional[str]
    is_primary: bool
    is_pillion: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# NEW: Ride Schemas


class CreateRide(BaseModel):
    organization_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    max_riders: Optional[int] = Field(30, ge=1, le=100)
    checkpoints: List['CreateCheckpoint']


class CreateCheckpoint(BaseModel):
    type: str  # MEETUP, DESTINATION, DISBURSEMENT
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: Optional[int] = Field(50, ge=10, le=1000)


class UpdateRide(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[str] = None  # PLANNED, ACTIVE, COMPLETED
    max_riders: Optional[int] = Field(None, ge=1, le=100)


class RideResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    status: str
    max_riders: int
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    updated_at: datetime
    
    # Relationships
    organization: Optional['OrganizationResponse'] = None
    checkpoints: Optional[List['CheckpointResponse']] = None
    participants: Optional[List['RideParticipantResponse']] = None
    
    class Config:
        from_attributes = True


class CheckpointResponse(BaseModel):
    id: UUID
    ride_id: UUID
    type: str
    latitude: float
    longitude: float
    radius_meters: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class JoinRide(BaseModel):
    phone_number: str
    otp_code: str
    vehicle_info_id: Optional[UUID] = None
    is_pillion: Optional[bool] = False


class RideJoinResponse(BaseModel):
    participant: 'RideParticipantResponse'
    ride: 'RideResponse'
    message: str


class UpdateRideParticipant(BaseModel):
    role: str  # RIDER, LEAD, MARSHAL, SWEEP


class RideParticipantResponse(BaseModel):
    id: UUID
    ride_id: UUID
    user_id: UUID
    vehicle_info_id: Optional[UUID] = None
    role: str
    registered_at: datetime
    updated_at: datetime
    
    # Relationships
    user: Optional['UserResponse'] = None
    vehicle_info: Optional['VehicleResponse'] = None
    
    class Config:
        from_attributes = True


class CheckInRequest(BaseModel):
    checkpoint_type: str  # MEETUP, DESTINATION, DISBURSEMENT
    latitude: float
    longitude: float


class CheckInResponse(BaseModel):
    attendance_record: 'AttendanceRecordResponse'
    message: str


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
    
    class Config:
        from_attributes = True


class RideHistoryResponse(BaseModel):
    rides: List['RideResponse']
    attendance_records: List['AttendanceRecordResponse']
