from pydantic import BaseModel, Field


class UserRegistration(BaseModel):
    phone_number: str