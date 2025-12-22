from fastapi import APIRouter
from api import auth_api, user_api, group_api, organization_api, ride_api
api_router = APIRouter()


api_router.include_router(auth_api.router)
api_router.include_router(user_api.router)
api_router.include_router(group_api.router)
api_router.include_router(organization_api.router)
api_router.include_router(ride_api.router)
