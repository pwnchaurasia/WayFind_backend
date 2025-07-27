from typing import Optional
from uuid import UUID
import random
from datetime import datetime, timedelta
from fastapi import  Request
from pydantic import BaseModel, EmailStr, HttpUrl, computed_field, field_validator, root_validator


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
