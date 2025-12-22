from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    logo: Optional[str] = None


class CreateOrganization(OrganizationBase):
    pass


class UpdateOrganization(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    logo: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    members_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    members_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# Organization Member Schemas
class AddOrganizationMember(BaseModel):
    user_id: UUID
    role: str = Field(..., pattern="^(founder|co_founder|admin)$")


class UpdateOrganizationMember(BaseModel):
    role: Optional[str] = Field(None, pattern="^(founder|co_founder|admin)$")
    is_active: Optional[bool] = None


class OrganizationMemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Add to existing file
class InviteMember(BaseModel):
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone_number: str = Field(..., min_length=10, max_length=15)
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern="^(founder|co_founder|admin)$")


class UpdateMemberRole(BaseModel):
    role: str = Field(..., pattern="^(founder|co_founder|admin)$")


class OrganizationMemberWithUser(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    created_at: datetime

    # User details
    user_name: Optional[str]
    user_email: Optional[str]
    user_phone: Optional[str]
    user_profile_picture: Optional[str]

    model_config = ConfigDict(from_attributes=True)