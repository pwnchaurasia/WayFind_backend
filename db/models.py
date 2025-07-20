import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.util import hybridproperty

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import column_property
from sqlalchemy import select, func
from utils import Base
from utils.enums import GroupUserType


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    profile_picture_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    groups = relationship("GroupMembership", back_populates="user", cascade="all, delete-orphan")
    user_setting = relationship("UserSetting", uselist=False, back_populates="user")
    owned_groups = relationship("Group", back_populates="group_owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"User -> {self.id} Name: {self.name} is active: {self.is_active}"

    @hybridproperty
    def is_profile_complete(self):
        if not self.name or not self.email or not self.profile_picture_url:
            return False
        return True

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

    def __repr__(self):
        return f"Group -> id:{self.id} name: {self.name} owner: {self.owner} owner_name: {self.group_owner.name if self.group_owner else None}"

        # ✅ Add this line inside the class

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