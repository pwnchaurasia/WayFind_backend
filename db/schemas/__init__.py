# Auth schemas
from db.schemas.auth import UserRegistration, OTPVerification, Token

# User schemas
from db.schemas.user import UserProfile, UserResponse, UserWithLocation

# Group schemas (legacy)
from db.schemas.group import CreateGroup, GroupResponse, GroupMemberResponse

# Location schemas
from db.schemas.location import LocationUpdate, LocationResponse

# Organization schemas
from db.schemas.organization import (
    CreateOrganization, UpdateOrganization, OrganizationResponse,
    OrganizationListResponse, AddOrganizationMember,
    UpdateOrganizationMember, OrganizationMemberResponse
)

# Vehicle schemas
from db.schemas.vehicle import CreateVehicle, UpdateVehicle, VehicleResponse

# Ride schemas
from db.schemas.ride import (
    CreateRide, UpdateRide, RideResponse,
    CreateCheckpoint, CheckpointResponse,
    JoinRide, RideJoinResponse,
    UpdateRideParticipant, RideParticipantResponse,
    RideHistoryResponse
)

# Attendance schemas
from db.schemas.attendance import (
    CheckInRequest, CheckInResponse, AttendanceRecordResponse
)

__all__ = [
    # Auth
    "UserRegistration", "OTPVerification", "Token",

    # User
    "UserProfile", "UserResponse", "UserWithLocation",

    # Group
    "CreateGroup", "GroupResponse", "GroupMemberResponse",

    # Location
    "LocationUpdate", "LocationResponse",

    # Organization
    "CreateOrganization", "UpdateOrganization", "OrganizationResponse",
    "OrganizationListResponse", "AddOrganizationMember",
    "UpdateOrganizationMember", "OrganizationMemberResponse",

    # Vehicle
    "CreateVehicle", "UpdateVehicle", "VehicleResponse",

    # Ride
    "CreateRide", "UpdateRide", "RideResponse",
    "CreateCheckpoint", "CheckpointResponse",
    "JoinRide", "RideJoinResponse",
    "UpdateRideParticipant", "RideParticipantResponse",
    "RideHistoryResponse",

    # Attendance
    "CheckInRequest", "CheckInResponse", "AttendanceRecordResponse",
]