
from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse

from db.db_conn import get_db
from utils import UserRole

from utils.app_helper import verify_user_from_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify-otp")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Example: parse Authorization header, decode JWT
    # user = ...
    # TODO : need to check user here using the auth token of user, JWT

    is_verified, msg, user = verify_user_from_token(token, db=db)
    if not is_verified:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=msg,
        headers={"WWW-Authenticate": "Bearer"},
    )

    return user


async def get_current_user_web(
        request: Request,  # Add request parameter
        access_token: str = Cookie(None),
        db: Session = Depends(get_db)
):
    """Get current user from cookie (for web pages)"""
    if not access_token:
        return None

    is_verified, msg, user = verify_user_from_token(access_token, db=db)
    if not is_verified:
        return None

    return user


async def verify_super_admin(
        access_token: str = Cookie(None),
        db: Session = Depends(get_db)
):
    """Verify user is super admin"""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    is_verified, msg, user = verify_user_from_token(access_token, db=db)
    if not is_verified or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can perform this action"
        )

    return user