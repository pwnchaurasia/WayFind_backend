from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CreateVehicle(BaseModel):
    make: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    license_plate: Optional[str] = Field(None, max_length=20)
    is_primary: bool = False
    is_pillion: bool = False


class UpdateVehicle(BaseModel):
    make: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    license_plate: Optional[str] = Field(None, max_length=20)
    is_primary: Optional[bool] = None
    is_pillion: Optional[bool] = None


class VehicleResponse(BaseModel):
    id: UUID
    user_id: UUID
    make: str
    model: str
    year: Optional[int]
    license_plate: Optional[str]
    is_primary: bool
    is_pillion: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)