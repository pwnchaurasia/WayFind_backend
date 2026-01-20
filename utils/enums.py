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
    BANNED = "banned"

class ActivityType(str, Enum):
    # Attendance activities
    ARRIVED_MEETUP = "arrived_meetup"
    CHECKED_IN_STOP = "checked_in_stop"
    REACHED_DESTINATION = "reached_destination"
    REACHED_HOME = "reached_home"
    
    # Ride lifecycle events
    RIDE_STARTED = "ride_started"
    RIDE_PAUSED = "ride_paused"
    RIDE_RESUMED = "ride_resumed"
    RIDE_ENDED = "ride_ended"
    
    # User actions
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    
    # Alerts
    SOS_ALERT = "sos_alert"
    LOW_FUEL = "low_fuel"
    BREAKDOWN = "breakdown"
    NEED_HELP = "need_help"
