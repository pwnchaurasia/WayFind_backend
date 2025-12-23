from typing import Optional

from fastapi import APIRouter, Depends, status, Request, Response, Form
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, RedirectResponse

from db.db_conn import get_db
from db.models import User, UserRideInformation
from db.schemas import UserRegistration, OTPVerification
from services.user_service import UserService
from utils import app_logger, resp_msgs, UserRole
from utils.app_helper import generate_otp, verify_otp, create_refresh_token, create_auth_token, verify_user_from_token, \
    is_safe_url
from utils.templates import jinja_templates

router = APIRouter(prefix="/auth", tags=["auth"])
logger = app_logger.createLogger("app")


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
            content={
                "access_token": auth_token,
                "refresh_token": refresh_token,
                "is_profile_complete": user.is_profile_complete
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error while finding or creating the user, Error {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG}
        )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify-otp")

@app_logger.functionlogs(log="app")
@router.post("/refresh-token")
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


@app_logger.functionlogs(log="app")
@router.post("/verify")
def verify_access_token(access_token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Verify refresh token and issue new access token and refresh token"""
    try:
        is_verified, msg, user = verify_user_from_token(access_token, db=db)
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
            content={"status": "error", "messages": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@router.get("/login", name="login_page")
async def login_page(request: Request, forward_url: str = None):
    """Render login page"""
    return jinja_templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "forward_url": forward_url
        }
    )



@router.post("/login", status_code=status.HTTP_200_OK, name="login")
async def login(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
        phone_number: str = Form(...),
        password: str = Form(...),
        remember: bool = Form(False),
        forward_url: str = Form(None),
):
    try:
        user = UserService.get_user_by_phone_number(db=db, phone_number=phone_number)
        if not user:
            return jinja_templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "Invalid phone number or password"
                }
            )

        access_token = create_auth_token(user)
        refresh_token = create_refresh_token(user)

        target = (forward_url if is_safe_url(forward_url) else None) or request.url_for("dashboard_page")

        response = RedirectResponse(url=target, status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=86400 if remember else 3600,
            samesite="lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=604800,  # 7 days
            samesite="lax"
        )
        return response

    except Exception as e:
        logger.exception(f"Login error: {e}")
        return jinja_templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "An error occurred. Please try again."
            }
        )


@router.post("/logout", name="logout")
async def logout(request: Request, response: Response):
    """Handle logout"""
    response = RedirectResponse(url=request.url_for("login_page"), status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.get("/register", name="register_page")
async def register_page(request: Request, forward_url: str = None):
    """Show registration page"""
    return jinja_templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "forward_url": forward_url
        }
    )


@router.post("/register", name="register")
async def register(
        request: Request,
        name: str = Form(...),
        phone_number: str = Form(...),
        email: Optional[str] = Form(None),
        password: str = Form(...),
        vehicle_make: Optional[str] = Form(None),
        vehicle_model: Optional[str] = Form(None),
        forward_url: Optional[str] = Form(None),
        db: Session = Depends(get_db)
):
    """Process registration"""
    try:
        # Check if user exists
        existing = db.query(User).filter(User.phone_number == phone_number).first()
        if existing:
            return jinja_templates.TemplateResponse(
                "auth/register.html",
                {
                    "request": request,
                    "forward_url": forward_url,
                    "error": "Phone number already registered. Please login."
                }
            )

        # Create user
        from utils.app_helper import hash_password
        user = User(
            name=name,
            phone_number=phone_number,
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
            role=UserRole.NORMAL_USER
        )
        db.add(user)
        db.flush()

        # Create vehicle if provided
        if vehicle_make and vehicle_model:
            vehicle = UserRideInformation(
                user_id=user.id,
                make=vehicle_make,
                model=vehicle_model,
                is_primary=True
            )
            db.add(vehicle)

        db.commit()

        access_token = create_auth_token(user)
        refresh_token = create_refresh_token(user)

        # Redirect
        redirect_url = forward_url if forward_url else "/dashboard"
        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie("access_token", access_token, httponly=True, max_age=86400)

        return response

    except Exception as e:
        db.rollback()
        logger.exception(f"Registration error: {e}")
        return jinja_templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "forward_url": forward_url,
                "error": "Registration failed. Please try again."
            }
        )