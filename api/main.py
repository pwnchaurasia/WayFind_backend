from fastapi import APIRouter
from api import user_api
api_router = APIRouter()


api_router.include_router(user_api.router)