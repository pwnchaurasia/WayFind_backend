from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/users", tags=["users"])



@router.get("/")
async def root():
    return {"message": "Hello World"}


