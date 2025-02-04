from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from db.db_conn import get_db
from db.models import User
from db.schemas import UserRegistration, OTPVerification
from utils import app_logger, error_msgs
from utils.app_helper import generate_otp, verify_otp, create_refresh_token, create_auth_token, verify_user_from_token

router = APIRouter(prefix="/auth", tags=["auth"])

logger = app_logger.createLogger("app")



@router.get("/", name="root")
async def root():
    return {"message": "Hello World"}

@app_logger.functionlogs(log="app")
@router.post("/request-otp", status_code=status.HTTP_200_OK, name="request-otp")
async def request_user(request: UserRegistration):
    try:
        if request.phone_number:
            otp = generate_otp(identifier=request.phone_number, otp_type="mobile_verification")
            if not otp:
                return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Please try again!!."})
            # TODO : remove OTP from here. its just temporary for testing
            return {"msg": "Otp sent to your mobile number. Please verify Using it", "temp_otp": f"{otp}"}
    except Exception as e:
        app_logger.exceptionlogs(f"Error in register user, Error: {e}")
        return {
                "msg": error_msgs.STATUS_500_MSG,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }


@app_logger.functionlogs(log="app")
@router.post("/verify-otp", status_code=status.HTTP_200_OK, name="verify-otp")
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
                auth_token = create_auth_token(user)
                refresh_token = create_refresh_token(user)
                return {
                    "access_token": auth_token,
                    "refresh_token": refresh_token,
                    "is_profile_complete": user.is_profile_complete
                }
            except Exception as e:
                app_logger.exceptionlogs(f"Error while finding or creating the user, Error {e}")
                return HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "error", "message": "Invalid OTP. Please try again"}
                )
        else:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Invalid OTP. Please try again"}
            )
    else:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Please provide mobile number and OTP"}
        )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify-otp")

@router.post("/refresh")
def refresh_access_token(refresh_token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Verify refresh token and issue new access token and refresh token"""
    try:
        is_verified, user = verify_user_from_token(refresh_token, db=db)
        if not is_verified:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # sending a fresh access and refresh token so that, user never logs out.
        auth_token = create_auth_token(user)
        refresh_token = create_refresh_token(user)

        return {"access_token": auth_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except Exception as e:
        app_logger.exceptionlogs(f"Error in refresh access token, Error {e}")
        return {"access_token": "", "refresh_token": "", "token_type": "bearer"}