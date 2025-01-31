import contextvars
from fastapi import Depends, HTTPException, status, Request


_current_user = contextvars.ContextVar("current_user", default=None)

def set_current_user(user):
    _current_user.set(user)

def get_current_user():
    return _current_user.get()

async def auth_dependency(request: Request):
    # Example: parse Authorization header, decode JWT
    # user = ...
    # TODO : need to check user here using the auth token of user, JWT
    user = True
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    set_current_user(user)  # store in the context var
    return user
