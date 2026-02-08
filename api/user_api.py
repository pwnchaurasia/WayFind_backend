from fastapi import APIRouter, status, Depends, Request, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import User, DeviceInfo, UserRideInformation
from db.schemas import UserProfile, UserResponse, GroupResponse, LocationUpdate, CreateVehicle
from db.schemas.vehicle import VehicleResponse
from services.device_info_service import DeviceInfoService
from services.group_service import GroupService
from services.location_service import LocationService
from services.user_service import UserService
from services.user_vehicle_service import UserVehicleService
from utils import app_logger
from utils.dependencies import get_current_user
from utils import resp_msgs
from utils.storage import storage

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
            content={
                "status": "success",
                "message": "Profile Updated",
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
            content={
                "status": "success",
                "message": "Current User",
                "user": UserResponse.model_validate(current_user).model_dump(mode="json")},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while fetching user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app_logger.functionlogs(log="app")
@router.post("/me/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        success, url, error = await storage.upload_avatar(file)
        if not success:
             return JSONResponse(
                content={"status": "error", "message": error or "Failed to upload avatar"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Update user profile
        current_user.profile_picture_url = url
        db.commit()
        db.refresh(current_user)

        return JSONResponse(
            content={
                "status": "success",
                "message": "Avatar uploaded successfully",
                "avatar_url": url,
                "user": UserResponse.model_validate(current_user).model_dump(mode="json")
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.exception(f"Error uploading avatar: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app_logger.functionlogs(log="app")
@router.get("/me/location", status_code=status.HTTP_202_ACCEPTED)
def user_location(current_user = Depends(get_current_user)):
    try:
        location_service = LocationService()
        location = location_service.get_user_location(current_user.id)

        if location:
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Users location found",
                    "location": location.model_dump(mode="json")
                },
                status_code=status.HTTP_200_OK
            )
        else:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Location not found"
                },
                status_code=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while getting users location, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app_logger.functionlogs(log="app")
@router.put("/me/location")
def update_user_location(location_data: LocationUpdate,
                         current_user = Depends(get_current_user)):
    try:
        logger.info("Location updated")
        location_service = LocationService()
        success = location_service.update_user_location(current_user.id, location_data)
        if success:
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Location Updated",
                    "user": 'Location updated'},
                status_code=status.HTTP_200_OK
            )
        else:
            logger.debug(f"Not able to save users location {success}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Failed to update location"
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

    except Exception as e:
        app_logger.exceptionlogs(f"Error while fetching user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@router.get("/me/groups")
def user_groups(request:Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        user_group_memberships = GroupService.fetch_user_groups(db=db, user_id=current_user.id)

        groups = [GroupResponse.model_validate(membership.group).to_response(request=request) for membership in user_group_memberships]
        return JSONResponse(
            content={"status": "success",
                     "message": "User groups",
                     "groups": groups},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error while fetching user profile, Error: {e}")
        return JSONResponse(
            content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app_logger.functionlogs(log="app")
@router.post("/me/vehicles", status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    request: CreateVehicle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add vehicle to user's garage"""
    try:
        vehicle = UserRideInformation(
            user_id=current_user.id,
            make=request.make,
            model=request.model,
            year=request.year,
            license_plate=request.license_plate,
            is_primary=request.is_primary,
            is_pillion=request.is_pillion
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        
        logger.info(f"Vehicle created for user: {current_user.id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Vehicle added successfully",
                "vehicle": VehicleResponse.model_validate(vehicle).model_dump(mode="json")
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error creating vehicle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@app_logger.functionlogs(log="app")
@router.get("/me/vehicles", status_code=status.HTTP_200_OK)
async def get_user_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's vehicles"""
    try:
        vehicles = db.query(UserRideInformation).filter(
            UserRideInformation.user_id == current_user.id,
            UserRideInformation.is_deleted == False
        ).all()
        
        return JSONResponse(
            content={
                "status": "success",
                "vehicles": [VehicleResponse.model_validate(v).model_dump(mode="json") for v in vehicles]
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.exception(f"Error getting vehicles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@app_logger.functionlogs(log="app")
@router.put("/me/vehicles/{vehicle_id}", status_code=status.HTTP_200_OK)
async def update_vehicle(
    vehicle_id: str,
    request: CreateVehicle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update vehicle"""
    try:
        vehicle = db.query(UserRideInformation).filter(
            UserRideInformation.id == vehicle_id,
            UserRideInformation.is_deleted == False
        ).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        
        if vehicle.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own vehicles"
            )
        
        vehicle.make = request.make or vehicle.make
        vehicle.model = request.model or vehicle.model
        vehicle.year = request.year or vehicle.year
        vehicle.license_plate = request.license_plate or vehicle.license_plate
        vehicle.is_primary = request.is_primary if request.is_primary is not None else vehicle.is_primary
        vehicle.is_pillion = request.is_pillion if request.is_pillion is not None else vehicle.is_pillion
        
        db.commit()
        db.refresh(vehicle)
        
        logger.info(f"Vehicle updated: {vehicle_id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Vehicle updated successfully",
                "vehicle": VehicleResponse.model_validate(vehicle).model_dump(mode="json")
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.exception(f"Error updating vehicle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@app_logger.functionlogs(log="app")
@router.delete("/me/vehicles/{vehicle_id}", status_code=status.HTTP_200_OK)
async def delete_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete vehicle"""
    try:
        vehicle = db.query(UserRideInformation).filter(
            UserRideInformation.id == vehicle_id,
            UserRideInformation.is_deleted == False
        ).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
        
        if vehicle.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own vehicles"
            )
        
        vehicle.is_deleted = True
        db.commit()
        
        logger.info(f"Vehicle deleted: {vehicle_id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Vehicle deleted successfully"
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.exception(f"Error deleting vehicle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/me/device-info")
async def create_or_update_device_info(
        device_data: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        device_info = DeviceInfoService.update_device_info(
            db=db,
            user_id=current_user.id,
            device_data=device_data
        )

        return JSONResponse(
            content={
                "status": "success",
                "message": "Device info updated successfully",
                "device_id": str(device_info.id)
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to update device info: {str(e)}"
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("/me/device-info/last-active")
async def update_device_last_active(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        device = DeviceInfoService.get_current_device(db=db, user_id=current_user.id)
        if device:
            device.last_active_at = func.now()
            db.commit()

        return JSONResponse(
            content={
                "status": "success",
                "message": "Device last active updated"
            },
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to update last active: {str(e)}"
            },
            status_code=500
        )


@router.get("/me/devices")
async def get_user_devices(current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    try:
        devices = db.query(DeviceInfo).filter(
            DeviceInfo.user_id == current_user.id
        ).order_by(DeviceInfo.last_active_at.desc()).all()

        return JSONResponse(
            content={
                "status": "success",
                "devices": [device.__dict__ for device in devices]
            },
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to get devices: {str(e)}"
            },
            status_code=500
        )
