from fastapi import HTTPException

from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import User
from db.schemas import UserProfile, UserResponse
from utils import app_logger
from utils.dependencies import get_current_user
from utils import error_msgs

router = APIRouter(prefix="/users", tags=["users"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.put("/me", status_code=status.HTTP_202_ACCEPTED)
def update_user_profile(profile_data: UserProfile,
                              db: Session = Depends(get_db),
                              current_user = Depends(get_current_user)):
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            return JSONResponse(
                content={ "status": "error", "message": "Use Not found" },
                status_code=status.HTTP_404_NOT_FOUND
            )

        update_fields = profile_data.model_dump(exclude_unset=True)

        # Update fields dynamically
        for key, value in update_fields.items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)  # Refresh to get updated data

        return JSONResponse(
            content={"status": "success", "message": "Profile Updated",
                     "user": UserResponse.model_validate(user).model_dump()},
            status_code=status.HTTP_202_ACCEPTED
        )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while updating user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": error_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app_logger.functionlogs(log="app")
@router.get("/me", status_code=status.HTTP_202_ACCEPTED)
def user_profile(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        return JSONResponse(
            content={"status": "success", "message": "Profile Updated",
                     "user": UserResponse.model_validate(current_user).model_dump()},
            status_code=status.HTTP_202_ACCEPTED
        )

    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": error_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )