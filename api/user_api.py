from fastapi import HTTPException

from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session

from db.db_conn import get_db
from db.models import User
from db.schemas import UserProfile, UserResponse
from utils import app_logger
from utils.dependencies import get_current_user


router = APIRouter(prefix="/users", tags=["users"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.put("/me", status_code=status.HTTP_202_ACCEPTED)
def update_user_profile(profile_data: UserProfile,
                              db: Session = Depends(get_db),
                              current_user = Depends(get_current_user)):
    msg = "Something went wrong!!!"
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        update_fields = profile_data.model_dump(exclude_unset=True)

        # Update fields dynamically
        for key, value in update_fields.items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)  # Refresh to get updated data
        msg = "Profile updated"
        return {"message": msg, "user": UserResponse.model_validate(user)}
    except HTTPException as he:
        app_logger.exceptionlogs(f"Error while updating user profile, HttpException Error: {he}")
        raise he
    except Exception as e:
        app_logger.exceptionlogs(f"Error while updating user profile, Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
