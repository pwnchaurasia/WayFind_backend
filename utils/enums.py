from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"  # Application owner
    NORMAL_USER = "normal_user"

class GroupUserType(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"

class OrganizationRole(str, Enum):
    FOUNDER = "founder"
    CO_FOUNDER = "co_founder"
    ADMIN = "admin"

class RideStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"

class RideType(str, Enum):
    ONE_DAY = "One Day"
    MULTI_DAY = "Multi Day"
    QUICK_RIDE = "Quick Ride"

class CheckpointType(str, Enum):
    MEETUP = "meetup"
    DESTINATION = "destination"
    DISBURSEMENT = "disbursement"
    REFRESHMENT = 'refreshment'

class ParticipantRole(str, Enum):
    RIDER = "rider"
    LEAD = "lead"
    MARSHAL = "marshal"
    SWEEP = "sweep"
