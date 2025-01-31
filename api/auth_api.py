from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from utils import User
from utils import app_logger
from utils.conn import get_db
from utils import error_msgs
from utils.schemas import UserRegistration, OTPVerification

router = APIRouter(prefix="/auth", tags=["auth"])

logger = app_logger.createLogger("app")



@router.get("/")
async def root():
    return {"message": "Hello World"}

@app_logger.functionlogs(log="app")
@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def register_user(request:UserRegistration):
    try:

        return {"msg": "User registered successfully", "user_id": new_user.id}
    except Exception as e:
        app_logger.exceptionlogs(f"Error in register user, Error: {e}")
        return {
                "msg": error_msgs.STATUS_500_MSG,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }


@app_logger.functionlogs(log="app")
@router.post("/verify-otp")
async def verify_otp(request: OTPVerification, db: Session = Depends(get_db)):
    # Check OTP from DB/Cache (Assume it's always 123456 for demo)
    if request.otp != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Invalid OTP"}
        )

    # TODO: verify OTP and mobile number from cache and check if its expired
    # TODO: if passed, create user if not exists or just re enable them
    existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists."
        )
    try:
        new_user = User(phone_number=request.phone_number)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        print(f"Exception here error: {e}")

    # Check if user exists → Login, else Register
    user_exists = False  # Assume user does not exist
    if user_exists:
        return {"status": "success", "message": "User logged in", "user_id": 123}
    else:
        return {"status": "success", "message": "User registered", "user_id": 456}