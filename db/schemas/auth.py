from pydantic import BaseModel


class UserRegistration(BaseModel):
    phone_number: str


class OTPVerification(BaseModel):
    phone_number: str
    otp: str


class Token(BaseModel):
    access_token: str
    token_type: str


class GoogleLoginRequest(BaseModel):
    token: str