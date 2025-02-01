import os
import random

from utils import app_logger
from utils.redis_helper import RedisHelper


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
    redis_client = RedisHelper()
    otp_key = f"otp:{otp_type}:{identifier}"
    stored_otp = redis_client.get(otp_key)

    if stored_otp and stored_otp == otp_input:
        redis_client.delete(otp_key)  # OTP is valid, remove it
        return True
    return False
