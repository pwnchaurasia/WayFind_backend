from fastapi import APIRouter, status
from fastapi.params import Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import Group
from db.schemas import CreateGroup
from utils import app_logger, resp_msgs
from utils.dependencies import get_current_user
from utils.app_helper import generate_random_group_code

router = APIRouter(prefix="/groups", tags=["groups"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.post("/", status_code=status.HTTP_200_OK)
def create_group(group_data: CreateGroup, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        # TODO check, if user has reach max group creation limit
        

        group = Group(**group_data.model_dump())
        group.code = generate_random_group_code()
        db.add(group)
        db.commit()
    except Exception as e:
        app_logger.exceptionlogs(f"Error creating group, Error: {e}")
        return JSONResponse(content={"status": "error", "message": resp_msgs.STATUS_500_MSG}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
