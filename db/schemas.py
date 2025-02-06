from typing import Optional

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
    id: int
    name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    is_active: bool
    profile_picture_url: Optional[HttpUrl]

    class Config:
        from_attributes = True


class CreateGroup(BaseModel):
    name: str

class CreateGroupResponse(BaseModel):
    name: str
    code: str