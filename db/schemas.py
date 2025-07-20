from typing import Optional
from uuid import UUID

from fastapi import  Request
from pydantic import BaseModel, Field, EmailStr, HttpUrl, computed_field


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
