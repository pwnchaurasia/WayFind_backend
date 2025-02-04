import os
import hashlib
import hmac
import random
from datetime import datetime, timezone, timedelta
from fastapi import Request, status, HTTPException, Depends
from fastapi.responses import JSONResponse

import jwt
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from db.db_conn import get_db
from db.models import User
from utils import app_logger
from utils.redis_helper import RedisHelper


SECRET_KEY = os.getenv('SECRET_KEY')
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15)
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30)



# def get_current_user():
#     """Retrieve authenticated user from context"""
#     user = user_context.get()
#     if not user:
#         raise Exception("User not authenticated")
#     return user
#

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
    hash_secret = os.getenv('HASH_SECRET')
    return hmac.new(hash_secret.encode(), str(mobile_number).encode(), hashlib.sha256).hexdigest()


def create_auth_token(user):
    """Generates an access token with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    data = {
        'user_id': user.id,
        'mobile_number': hash_mobile_number(user.phone_number),
        "exp": expire
    }
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user):
    """Generates a refresh token with longer expiration."""
    expire = datetime.now(timezone.utc) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
    data = {
        'user_id': user.id,
        'mobile_number': hash_mobile_number(user.phone_number),
        "exp": expire
    }

    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def decode_jwt(token: str):
    """Decodes and verifies JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        exp = payload.get("exp")

        if not exp or datetime.now(timezone.utc) > datetime.fromtimestamp(exp, tz=timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def verify_user_from_token(token: str, db):
    """Verifies user from JWT token"""
    is_verified = False
    user = None
    try:
        payload = decode_jwt(token)
        user_id = payload.get("user_id")
        hashed_mobile = payload.get("mobile_number")

        user = db.query(User).filter(User.id == user_id).first()

        if not user or hash_mobile_number(user.phone_number) != hashed_mobile:
            raise HTTPException(status_code=401, detail="Invalid user authentication")
        is_verified = True

    except Exception as e:
        app_logger.exceptionlogs(f"Error in verify user from token, Error: {e}")

    return is_verified, user