
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from utils import resp_msgs
from utils.app_helper import verify_user_from_token, hash_mobile_number

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
