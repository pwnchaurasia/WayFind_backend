from pyexpat.errors import messages

from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import User
from db.schemas import UserRegistration, OTPVerification
from services.user_service import UserService
from utils import app_logger, resp_msgs
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
                return JSONResponse(
                    content={"status": "error", "message": resp_msgs.STATUS_404_MSG},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            # TODO : remove OTP from here. its just temporary for testing
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Otp sent to your mobile number. Please verify Using it",
                    "temp_otp": f"{otp}"
                },
                status_code=status.HTTP_201_CREATED
            )
    except Exception as e:
        app_logger.exceptionlogs(f"Error in register user, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app_logger.functionlogs(log="app")
@router.post("/verify-otp", status_code=status.HTTP_200_OK, name="verify-otp")
async def verify_mobile_and_otp(request: OTPVerification, db: Session = Depends(get_db)):

    if not request.phone_number or not request.otp:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Please provide mobile number and OTP"}
        )

    is_verified = verify_otp(identifier=request.phone_number, otp_input=request.otp, otp_type="mobile_verification")

    if not is_verified:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": resp_msgs.INVALID_OTP}
        )

    try:
        user = UserService.create_user_by_phone_number(phone_number=request.phone_number, db=db)
        if not user:
            logger.debug(f"Not able to create user get_or_create_user_by_phone_number")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": "error", "message": resp_msgs.INVALID_OTP}
            )


        auth_token = create_auth_token(user)
        refresh_token = create_refresh_token(user)
        return JSONResponse(
            content={"access_token": auth_token, "refresh_token": refresh_token,
                     "is_profile_complete": user.is_profile_complete},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error while finding or creating the user, Error {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG}
        )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify-otp")

@app_logger.functionlogs(log="app")
@router.post("/refresh")
def refresh_access_token(refresh_token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Verify refresh token and issue new access token and refresh token"""
    try:
        is_verified, msg, user = verify_user_from_token(refresh_token, db=db)
        if not is_verified:
            return JSONResponse(content={"status": "error", "message": msg}, status_code=status.HTTP_401_UNAUTHORIZED)

        # sending a fresh access and refresh token so that, user never logs out.
        auth_token = create_auth_token(user)
        refresh_token = create_refresh_token(user)

        return JSONResponse(
            content={
                "status": "success",
                "access_token": auth_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error in refresh access token, Error {e}")
        return JSONResponse(
            content={ "status":"error","messages": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )