from fastapi import HTTPException

from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import User
from db.schemas import UserProfile, UserResponse
from services.user_service import UserService
from utils import app_logger
from utils.dependencies import get_current_user
from utils import resp_msgs

router = APIRouter(prefix="/users", tags=["users"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.put("/me", status_code=status.HTTP_202_ACCEPTED)
def update_user_profile(user_profile_data: UserProfile,
                              db: Session = Depends(get_db),
                              current_user = Depends(get_current_user)):
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            return JSONResponse(
                content={ "status": "error", "message": resp_msgs.USER_NOT_FOUND },
                status_code=status.HTTP_404_NOT_FOUND
            )

        user = UserService.update_user_data(db=db, user=user, user_profile_data=user_profile_data)
        if not user:
            return JSONResponse(
                content={"status": "error", "message": resp_msgs.PROFILE_NOT_UPDATED},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        return JSONResponse(
            content={"status": "success", "message": "Profile Updated",
                     "user": UserResponse.model_validate(user).model_dump(mode="json")},
            status_code=status.HTTP_202_ACCEPTED
        )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while updating user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app_logger.functionlogs(log="app")
@router.get("/me", status_code=status.HTTP_202_ACCEPTED)
def user_profile(current_user = Depends(get_current_user)):
    try:
        return JSONResponse(
            content={"status": "success", "message": "Profile Updated",
                     "user": UserResponse.model_validate(current_user).model_dump(mode="json")},
            status_code=status.HTTP_202_ACCEPTED
        )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while fetching user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )