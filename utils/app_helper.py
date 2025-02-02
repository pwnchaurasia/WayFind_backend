import os
import hashlib
import hmac
import random
from datetime import datetime, timezone, timedelta
from fastapi import  Request, status
from fastapi.responses import JSONResponse

import jwt
from fastapi.exceptions import RequestValidationError

from utils import app_logger
from utils.redis_helper import RedisHelper


SECRET_KEY = os.getenv('SECRET_KEY')
HASH_SECRET = os.getenv('HASH_SECRET')
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15)
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30)


def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])  # Extract field name
        errors.append({
            "field": field,
            "message": error["msg"]
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation failed. Please check your input.",
            "errors": errors
        },
    )


def generate_otp(identifier, otp_type="mobile_verification"):
    """
        :param identifier: can be mobile number or email
        :param type: Type of OTP (e.g., 'mobile_verification', 'email_verification', 'password_reset').
        :return: otp
    """
    try:
        redis_client = RedisHelper()
        otp = str(random.randint(100000, 999999))
        otp_key = f"otp:{otp_type}:{identifier}"
        redis_client.set_with_ttl(otp_key, otp, os.getenv("OTP_TTL"))  # Store OTP for 3 minutes
        return otp
    except Exception as e:
        app_logger.exceptionlogs(f"Error in generate_otp, Error: {e}")
        return None


def verify_otp(identifier, otp_input, otp_type="mobile_verification"):
    """
        Verify an OTP for a given identifier (phone/email).
        :param identifier: Can be a phone number or an email.
        :param otp_input: The OTP entered by the user.
        :param otp_type: Type of OTP verification.
        :return: True if valid, False otherwise.
    """
    try:
        redis_client = RedisHelper()
        otp_key = f"otp:{otp_type}:{identifier}"
        stored_otp = redis_client.get(otp_key)

        if stored_otp and stored_otp == otp_input:
            redis_client.delete(otp_key)  # OTP is valid, remove it
            return True
        return False
    except Exception as e:
        app_logger.exceptionlogs(f"Error in generate_otp, Error: {e}")
        return None


def hash_mobile_number(mobile_number):
    """
        Hashes mobile number using HMAC-SHA256
        :param mobile_number
    """
    return hmac.new(HASH_SECRET.encode(), str(mobile_number).encode(), hashlib.sha256).hexdigest()


def create_auth_token(user):
    """Generates an access token with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    data = {
        'user_id': user.id,
        'mobile': hash_mobile_number(user.phone_number),
        "exp": expire
    }
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user):
    """Generates a refresh token with longer expiration."""
    expire = datetime.now(timezone.utc) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
    data = {
        'user_id': user.id,
        'mobile': hash_mobile_number(user.phone_number),
        "exp": expire
    }

    return jwt.encode(data, SECRET_KEY, algorithm="HS256")