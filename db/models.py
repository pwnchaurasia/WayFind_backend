import uuid
from ast import Index

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.util import hybridproperty

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import column_property
from sqlalchemy import select, func
from utils import Base
from utils.enums import GroupUserType, UserRole, RideStatus, CheckpointType, ParticipantRole, OrganizationRole, RideType


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    profile_picture_url = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.NORMAL_USER, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    groups = relationship("GroupMembership", back_populates="user", cascade="all, delete-orphan")
    user_setting = relationship("UserSetting", uselist=False, back_populates="user")
    owned_groups = relationship("Group", back_populates="group_owner", cascade="all, delete-orphan")
    group_settings = relationship("GroupUserSettings", back_populates="user")
    
    # New ride-related relationships
    ride_participations = relationship("RideParticipant", back_populates="user", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="user", cascade="all, delete-orphan")
    
    # Organization relationships
    organization_memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")
    
    # Ride information relationships
    ride_vehicles = relationship("UserRideInformation", back_populates="user", cascade="all, delete-orphan")


    def __repr__(self):
        return f"User -> {self.id} Name: {self.name} is active: {self.is_active}"

    @hybridproperty
    def is_profile_complete(self):
        return sum(bool(field) for field in [self.name, self.email, self.profile_picture_url]) >= 2

class GroupMembership(Base):
    __tablename__ = "group_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    role = Column(Enum(GroupUserType), default=GroupUserType.ADMIN, nullable=False)  # e.g., "owner", "admin", "member"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    group = relationship("Group", back_populates="memberships")
    user = relationship("User", back_populates="groups")


class Group(Base):
    __tablename__ = "groups"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(40), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    code = Column(String(40), nullable=True, index=True)
    owner = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # Relationship to memberships
    memberships = relationship("GroupMembership", back_populates="group", cascade="all, delete-orphan")
    group_owner = relationship("User", back_populates="owned_groups")
    user_settings = relationship("GroupUserSettings", back_populates="group")

    def __repr__(self):
        return f"Group -> id:{self.id} name: {self.name} owner: {self.owner} owner_name: {self.group_owner.name if self.group_owner else None}"

    members_count = column_property(
        select(func.count(GroupMembership.id))
        .where(GroupMembership.group_id == id)
        .correlate_except(GroupMembership)
        .scalar_subquery()
    )


class UserSetting(Base):
    __tablename__ =  "user_setting"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    max_group_creation = Column(Integer, default=3)

    user = relationship("User", back_populates="user_setting")



class DeviceInfo(Base):
    __tablename__ = "device_infos"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(150), nullable=True, index=True)
    device_model = Column(String(150), nullable=True, index=True)
    device_brand = Column(String(150), nullable=True, index=True)
    os_name = Column(String(150), nullable=True, index=True)
    os_version = Column(String(150), nullable=True, index=True)
    app_version = Column(String(150), nullable=True, index=True)
    screen_width = Column(String(150), nullable=True, index=True)
    screen_height = Column(String(150), nullable=True, index=True)
    timezone = Column(String(150), nullable=True, index=True)
    locale = Column(String(150), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Track which device is currently active
    is_current_device = Column(Boolean, default=True, nullable=False)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Add unique constraint for device_id per user
    __table_args__ = (
        UniqueConstraint('user_id', 'device_id', name='unique_user_device'),
    )


class LocationSharingMode(str, Enum):
    ALWAYS = "always"
    ACTIVE_ONLY = "active_only"  # Only when app is active
    TIME_BASED = "time_based"  # Based on sharing_hours
    OFF = "off"


class GroupUserSettings(Base):
    __tablename__ = "group_user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True)

    # Location Settings
    is_location_sharing_on = Column(Boolean, default=True, nullable=False)
    location_sharing_mode = Column(String, default=LocationSharingMode.ALWAYS, nullable=False)
    location_sharing_radius_meters = Column(Integer, default=1000)  # Share only within this radius of group

    # Audio Settings
    is_auto_play_audio = Column(Boolean, default=True, nullable=False)
    # Notification Settings
    is_notification_on = Column(Boolean, default=True, nullable=False)
    is_push_notification_on = Column(Boolean, default=True, nullable=False)

    # Privacy Settings
    is_online_status_visible = Column(Boolean, default=True, nullable=False)
    is_last_seen_visible = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="group_settings")
    group = relationship("Group", back_populates="user_settings")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='unique_user_group_settings'),
    )


# New Models for Rides and Organizations


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    logo = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)  # Add this
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    rides = relationship("Ride", back_populates="organization", cascade="all, delete-orphan")
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Organization -> id:{self.id} name: {self.name}"


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(Enum(OrganizationRole), nullable=False)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id', name='unique_organization_user_member'),
    )

    def __repr__(self):
        return f"OrganizationMember -> id:{self.id} org_id: {self.organization_id} user_id: {self.user_id} role: {self.role}"


class UserRideInformation(Base):
    __tablename__ = "user_ride_information"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=True)
    license_plate = Column(String(20), nullable=True)
    is_primary = Column(Boolean, default=False)  # User's primary vehicle
    is_pillion = Column(Boolean, default=False)  # For passengers
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="ride_vehicles")
    ride_participations = relationship("RideParticipant", back_populates="vehicle_info")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'license_plate', name='unique_user_license_plate'),
    )

    def __repr__(self):
        return f"UserRideInformation -> id:{self.id} user_id: {self.user_id} make: {self.make} model: {self.model}"


class Ride(Base):
    __tablename__ = "rides"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status = Column(Enum(RideStatus), default=RideStatus.PLANNED, nullable=False)
    max_riders = Column(Integer, default=30, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Payment fields
    requires_payment = Column(Boolean, default=False, nullable=False)
    amount = Column(Float, default=0.0, nullable=False)

    # NEW: Scheduled date
    scheduled_date = Column(DateTime(timezone=True), nullable=True)  # When ride is planned
    ride_type = Column(Enum(RideType), default=RideType.ONE_DAY, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="rides")
    checkpoints = relationship("RideCheckpoint", back_populates="ride", cascade="all, delete-orphan")
    participants = relationship("RideParticipant", back_populates="ride", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="ride", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Ride -> id:{self.id} name: {self.name} status: {self.status}"

    # Note: participants_count is defined as a hybrid property or can be added later
    # after all models are defined to avoid forward reference issues


class RideCheckpoint(Base):
    __tablename__ = "ride_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False, index=True)
    type = Column(Enum(CheckpointType), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Integer, default=50, nullable=False)
    address = Column(String, nullable=True)  # Human-readable address
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ride = relationship("Ride", back_populates="checkpoints")

    def __repr__(self):
        return f"RideCheckpoint -> id:{self.id} ride_id: {self.ride_id} type: {self.type}"


class RideParticipant(Base):
    __tablename__ = "ride_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    vehicle_info_id = Column(UUID(as_uuid=True), ForeignKey("user_ride_information.id"), nullable=True, index=True)
    role = Column(Enum(ParticipantRole), default=ParticipantRole.RIDER, nullable=False)
    # Payment tracking
    has_paid = Column(Boolean, default=False, nullable=False)
    paid_amount = Column(Float, default=0.0, nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=True)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ride = relationship("Ride", back_populates="participants")
    user = relationship("User")
    vehicle_info = relationship("UserRideInformation", back_populates="ride_participations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('ride_id', 'user_id', name='unique_ride_participant'),
    )

    def __repr__(self):
        return f"RideParticipant -> id:{self.id} ride_id: {self.ride_id} user_id: {self.user_id} role: {self.role}"


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    ride_id = Column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    checkpoint_type = Column(Enum(CheckpointType), nullable=False)
    reached_at = Column(DateTime(timezone=True), server_default=func.now())
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    distance_traveled_km = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ride = relationship("Ride", back_populates="attendance_records")
    user = relationship("User")

    # Constraints
    __table_args__ = (
        UniqueConstraint('ride_id', 'user_id', 'checkpoint_type', name='unique_ride_user_checkpoint_attendance'),
    )

    def __repr__(self):
        return f"AttendanceRecord -> id:{self.id} ride_id: {self.ride_id} user_id: {self.user_id} checkpoint: {self.checkpoint_type}"
