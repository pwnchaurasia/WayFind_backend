from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, HttpUrl, computed_field, ConfigDict


class UserProfile(BaseModel):
    email: EmailStr
    name: str
    profile_picture_url: Optional[HttpUrl] = None

    model_config = ConfigDict(from_attributes=True)


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
        """At least two fields are required"""
        return sum(bool(field) for field in [self.name, self.email, self.profile_picture_url]) >= 2

    model_config = ConfigDict(from_attributes=True)


class UserWithLocation(BaseModel):
    id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    profile_picture_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    timestamp: Optional[str] = None