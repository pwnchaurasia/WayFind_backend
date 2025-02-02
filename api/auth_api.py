from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from db.db_conn import get_db
from db.models import User
from db.schemas import UserRegistration, OTPVerification
from pubsub.rabbitMQ_producer import RabbitMQProducer
from utils import app_logger, error_msgs
from utils.app_helper import generate_otp, verify_otp

router = APIRouter(prefix="/auth", tags=["auth"])

logger = app_logger.createLogger("app")



@router.get("/")
async def root():
    return {"message": "Hello World"}

@app_logger.functionlogs(log="app")
@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_user(request: UserRegistration):
    try:
        if request.phone_number:
            otp = generate_otp(identifier=request.phone_number, otp_type="mobile_verification")
            if not otp:
                return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Please try again!!."})
            return {"msg": "Otp sent to your mobile number. Please verify Using it", "user_id": f"new_user.id {otp}"}
    except Exception as e:
        app_logger.exceptionlogs(f"Error in register user, Error: {e}")
        return {
                "msg": error_msgs.STATUS_500_MSG,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }


@app_logger.functionlogs(log="app")
@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_mobile_and_otp(request: OTPVerification, db: Session = Depends(get_db)):
    if request.phone_number and request.otp:
        is_verified = verify_otp(identifier=request.phone_number, otp_input=request.otp, otp_type="mobile_verification")
        if is_verified:

            try:
                user = db.query(User).filter(User.phone_number == request.phone_number).first()
                if not user:
                    user = User(phone_number=request.phone_number, is_phone_verified=True, is_active=True)
                else:
                    user.is_phone_verified = True
                    user.is_active = True
                db.add(user)
                db.commit()
                db.refresh(user)
            # TODO: generate auth token and refresh token

            except Exception as e:
                app_logger.exceptionlogs(f"Error while finding or creating the user, Error {e}")

            return {"access_token": "token", "refresh_token": "refresh"}
        else:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Invalid OTP. Please try again"}
            )

    # TODO: verify OTP and mobile number from cache and check if its expired
    # TODO: if passed, create user if not exists or just re enable them


    # Check if user exists → Login, else Register
    user_exists = False  # Assume user does not exist
    if user_exists:
        return {"status": "success", "message": "User logged in", "user_id": 123}
    else:
        return {"status": "success", "message": "User registered", "user_id": 456}