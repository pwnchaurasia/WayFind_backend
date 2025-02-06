from fastapi import APIRouter, status
from fastapi.params import Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import Group
from db.schemas import CreateGroup, CreateGroupResponse
from services.group_service import GroupService
from utils import app_logger, resp_msgs
from utils.dependencies import get_current_user
from utils.app_helper import generate_random_group_code
from utils.validation import Validator

router = APIRouter(prefix="/groups", tags=["groups"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.post("/", status_code=status.HTTP_200_OK)
def create_group(group_data: CreateGroup, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        # TODO check, if user has reach max group creation limit
        is_valid = Validator.validate_group_creation(user_id=current_user.id, db=db)
        if not is_valid:
            logger.debug(f"User {current_user} has reached max group creation.")
            return JSONResponse(content={"status": "error", "message": resp_msgs.MAX_GROUP_CREATION_REACHED},
                         status_code=status.HTTP_400_BAD_REQUEST)

        is_group_created, group = GroupService.create_group(user_id=current_user.id, group_data=group_data, db=db)
        if not is_group_created:
            logger.error(f"Group creation failed for user {current_user}")
            return JSONResponse(content={"status": "error", "message": resp_msgs.GROUP_NOT_CREATED},
                                status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(
            content={"status": "success",
                     "message": resp_msgs.GROUP_NOT_CREATED,
                     "data": CreateGroupResponse.model_validate(group).model_dump()},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error creating group, Error: {e}")
        return JSONResponse(content={"status": "error", "message": resp_msgs.STATUS_500_MSG}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
