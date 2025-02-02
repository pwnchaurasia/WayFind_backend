from fastapi import APIRouter, status
from fastapi.params import Depends
from sqlalchemy.orm import Session

from db.db_conn import get_db
from utils import app_logger


router = APIRouter(prefix="/auth", tags=["auth"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def update_user_profile(request, db: Session = Depends(get_db)):
    pass