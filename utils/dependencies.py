
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db.db_conn import get_db
from db.models import User
from utils.app_helper import verify_user_from_token, hash_mobile_number

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Example: parse Authorization header, decode JWT
    # user = ...
    # TODO : need to check user here using the auth token of user, JWT
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_user_from_token(token)
    if not payload:
        raise credentials_exception

    # ✅ Extract user ID and verify user exists
    user = db.query(User).filter(User.id == payload.get("user_id", None)).first()
    if user is None:
        raise credentials_exception

    if hash_mobile_number(str(user.phone_number)) != payload.get('mobile_number', None):
        raise credentials_exception

    return user
