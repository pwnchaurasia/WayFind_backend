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

class CheckpointType(str, Enum):
    MEETUP = "meetup"
    DESTINATION = "destination"
    DISBURSEMENT = "disbursement"

class ParticipantRole(str, Enum):
    RIDER = "rider"
    LEAD = "lead"
    MARSHAL = "marshal"
    SWEEP = "sweep"
