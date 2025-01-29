from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from utils import User
from utils.conn import get_db
from utils import error_msgs
from utils.schemas import UserRegistration

router = APIRouter(prefix="/users", tags=["users"])



@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.post("/register")
async def register_user(request:UserRegistration, db: Session = Depends(get_db)):
    print(request.phone_number)
    existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists."
        )
    try:
        new_user = User(phone_number=request.phone_number)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {"msg": "User registered successfully", "user_id": new_user.id}
    except Exception as e:
        return {
                "msg": error_msgs.STATUS_500_MSG,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR
        }