import time
import secrets
import string
import os
import hashlib
import hmac
import random
from datetime import datetime, timezone, timedelta
from fastapi import Request, status, HTTPException, Depends
from fastapi.responses import JSONResponse

from jose import jwt
from fastapi.exceptions import RequestValidationError

from db.models import User
from services.user_service import UserService
from utils import app_logger
from utils.redis_helper import RedisHelper
from utils.security import get_password_hash

SECRET_KEY = os.getenv('SECRET_KEY')
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15)
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30)

logger = app_logger.createLogger("app")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    errors = []
    if not body:
        model = request.scope["route"].body_field.type_
        expected_fields = list(model.model_fields.keys())
        errors = [{"field": field, "message": f"Field '{field}' is required but was not provided."} for field in
                  expected_fields]
    else:
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


@app_logger.functionlogs(log="app")
def create_auth_token(user):
    """Generates an access token with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    data = {
        'user_id': str(user.id),
        'mobile_number': hash_mobile_number(user.phone_number),
        "exp": expire
    }
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

@app_logger.functionlogs(log="app")
def create_refresh_token(user):
    """Generates a refresh token with longer expiration."""
    expire = datetime.now(timezone.utc) + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
    data = {
        'user_id': str(user.id),
        'mobile_number': hash_mobile_number(user.phone_number),
        "exp": expire
    }

    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

@app_logger.functionlogs(log="app")
def decode_jwt(token: str):
    """Decodes and verifies JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        exp = payload.get("exp")

        if not exp or datetime.now(timezone.utc) > datetime.fromtimestamp(exp, tz=timezone.utc):
            logger.debug("Token expired. time exceeded")
            return False, "Token Expired. Please login again.", {}

        return True, "Token valid", payload

    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return False, "Token Expired. Please login again.", {}

    except jwt.InvalidTokenError:
        logger.debug("Token expired")
        return False, "Wrong token. Please login gain.", {}


@app_logger.functionlogs(log="app")
def verify_user_from_token(token: str, db):
    """Verifies user from JWT token"""
    is_verified = False
    user = None
    try:
        is_decoded, msg, payload = decode_jwt(token)
        if not is_decoded:
            return is_verified, msg, user

        user_id = payload.get("user_id")
        hashed_mobile = payload.get("mobile_number")

        user = UserService.get_user_by_id(user_id, db)

        if not user or hash_mobile_number(user.phone_number) != hashed_mobile:
            logger.debug("not user or mobile hash doesnt match")
            return is_verified, "Mobile hash doesn't match", user
        is_verified = True
        return is_verified, "User verified", user
    except Exception as e:
        app_logger.exceptionlogs(f"Error in verify user from token, Error: {e}")
        return False, "Error occurred", None




def generate_random_group_code():
    """
        Generate a 40-character unique string using:
        - A high-precision epoch timestamp (milliseconds).
        - Random characters for added randomness.
        - Ensures uniqueness without DB checks.
        """
    timestamp = str(int(time.time() * 1000))  # Get epoch time in milliseconds
    random_part = ''.join(secrets.choice(string.ascii_letters) for _ in range(40 - len(timestamp)))

    return random_part + timestamp

def hash_password(password: str):
    return get_password_hash(password=password)

def is_safe_url(url: str) -> bool:
    # 1. Must start with /
    # 2. Must NOT start with // (to prevent protocol-relative redirects)
    return url.startswith("/") and not url.startswith("//") if url else None