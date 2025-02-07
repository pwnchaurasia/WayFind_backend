from typing import Optional
from uuid import UUID

from fastapi import  Request
from pydantic import BaseModel, Field, EmailStr, HttpUrl


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
        orm_mode = True


class UserResponse(BaseModel):
    id: UUID
    name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    is_active: bool
    profile_picture_url: Optional[HttpUrl]

    class Config:
        from_attributes = True
        # json_encoders = {UUID: str}

    # def to_response(self):
    #     return {
    #         "id": str(self.id),
    #         "name": self.name,
    #         "email": self.email,
    #         "phone_number": self.phone_number,
    #         "is_active": self.is_active,
    #         "profile_picture_url": self.profile_picture_url
    #     }


class CreateGroup(BaseModel):
    name: str

class CreateGroupResponse(BaseModel):
    id: int
    owner: int
    name: str
    code: str

    class Config:
        from_attributes = True

    @staticmethod
    def generate_group_join_url(request: Request, code: str) -> str:
        """Generates a full join URL dynamically."""
        return str(request.url_for("join_group_with_code", code=code))

    def to_response(self, request:Request) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "join_url": CreateGroupResponse.generate_group_join_url(request, self.code)
        }
