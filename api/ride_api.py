from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import Ride, RideParticipant, RideCheckpoint, UserRideInformation, User
from db.schemas import (
    CreateRide, UpdateRide, RideResponse, CreateCheckpoint, 
    RideParticipantResponse, UpdateRideParticipant, CheckInRequest, CheckInResponse,
    AttendanceRecordResponse, JoinRide, RideJoinResponse, RideHistoryResponse
)
from services.user_service import UserService
from utils import app_logger, resp_msgs
from utils.app_helper import verify_user_from_token
from utils.enums import OrganizationRole, UserRole


router = APIRouter(prefix="/rides", tags=["rides"])
logger = app_logger.createLogger("app")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify")


def verify_organization_admin(current_user: User = Depends(verify_user_from_token)):
    """Verify user can manage rides for organization"""
    if current_user.role == UserRole.SUPER_ADMIN:
        return current_user
    
    # Check if user is admin of any organization
    from db.db_conn import get_db
    db = next(get_db())
    is_admin = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
        OrganizationMember.is_active == True
    ).first()
    db.close()
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can access this resource"
        )
    return current_user


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ride(
    request: CreateRide,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Create new ride (organization admin only)"""
    try:
        ride = Ride(
            organization_id=request.organization_id,
            name=request.name,
            max_riders=request.max_riders or 30,
            status="PLANNED"
        )
        db.add(ride)
        db.commit()
        db.refresh(ride)
        
        # Create checkpoints
        for checkpoint_data in request.checkpoints:
            checkpoint = RideCheckpoint(
                ride_id=ride.id,
                type=checkpoint_data.type,
                latitude=checkpoint_data.latitude,
                longitude=checkpoint_data.longitude,
                radius_meters=checkpoint_data.radius_meters or 50
            )
            db.add(checkpoint)
        
        db.commit()
        
        logger.info(f"Ride created: {ride.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "ride": RideResponse.from_orm(ride)},
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error creating ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/", status_code=status.HTTP_200_OK)
async def list_rides(
    organization_id: str = None,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """List rides - filtered by organization if provided"""
    try:
        query = db.query(Ride)
        
        if organization_id:
            # Verify user is member of this organization
            membership = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.is_active == True
            ).first()
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of this organization"
                )
            query = query.filter(Ride.organization_id == organization_id)
        
        rides = query.all()
        
        return JSONResponse(
            content={
                "status": "success",
                "rides": [RideResponse.from_orm(ride) for ride in rides]
            }
        )
    except Exception as e:
        logger.exception(f"Error listing rides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{ride_id}", status_code=status.HTTP_200_OK)
async def get_ride(
    ride_id: str,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """Get ride details"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Verify user has access to this ride's organization
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True
        ).first()
        
        is_admin = current_user.role == UserRole.SUPER_ADMIN or (
            membership and membership.role in [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]
        )
        
        ride_response = RideResponse.from_orm(ride)
        ride_response.checkpoints = [
            CheckpointResponse.from_orm(cp) for cp in ride.checkpoints
        ]
        
        # Include participants based on user role
        if is_admin:
            ride_response.participants = [
                RideParticipantResponse.from_orm(rp) for rp in ride.participants
            ]
        
        return JSONResponse(
            content={"status": "success", "ride": ride_response}
        )
    except Exception as e:
        logger.exception(f"Error getting ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.put("/{ride_id}", status_code=status.HTTP_200_OK)
async def update_ride(
    ride_id: str,
    request: UpdateRide,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Update ride (organization admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        if request.name:
            ride.name = request.name
        if request.status:
            ride.status = request.status
        if request.max_riders:
            ride.max_riders = request.max_riders
        
        db.commit()
        db.refresh(ride)
        
        logger.info(f"Ride updated: {ride.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "ride": RideResponse.from_orm(ride)}
        )
    except Exception as e:
        logger.exception(f"Error updating ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/{ride_id}/start", status_code=status.HTTP_200_OK)
async def start_ride(
    ride_id: str,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Start ride (organization admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        ride.status = "ACTIVE"
        db.commit()
        
        logger.info(f"Ride started: {ride.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "message": "Ride started successfully"}
        )
    except Exception as e:
        logger.exception(f"Error starting ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/{ride_id}/end", status_code=status.HTTP_200_OK)
async def end_ride(
    ride_id: str,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """End ride (organization admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        ride.status = "COMPLETED"
        db.commit()
        
        logger.info(f"Ride ended: {ride.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "message": "Ride ended successfully"}
        )
    except Exception as e:
        logger.exception(f"Error ending ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{ride_id}/participants", status_code=status.HTTP_200_OK)
async def list_ride_participants(
    ride_id: str,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """List ride participants"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Check if user has admin access to this ride
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True
        ).first()
        
        is_admin = current_user.role == UserRole.SUPER_ADMIN or (
            membership and membership.role in [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]
        )
        
        participants = db.query(RideParticipant).filter(RideParticipant.ride_id == ride_id).all()
        
        if is_admin:
            participant_responses = [
                RideParticipantResponse.from_orm(rp) for rp in participants
            ]
        else:
            # Non-admins see limited info
            participant_responses = []
            for rp in participants:
                participant_response = RideParticipantResponse.from_orm(rp)
                participant_response.user = None  # Hide user details
                participant_response.vehicle_info = None  # Hide vehicle info
                participant_responses.append(participant_response)
        
        return JSONResponse(
            content={
                "status": "success",
                "participants": participant_responses
            }
        )
    except Exception as e:
        logger.exception(f"Error listing ride participants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/{ride_id}/participants", status_code=status.HTTP_201_CREATED)
async def join_ride(
    ride_id: str,
    request: JoinRide,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """Join ride"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Check if ride has space
        current_participants = db.query(RideParticipant).filter(RideParticipant.ride_id == ride_id).count()
        if current_participants >= ride.max_riders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ride is full"
            )
        
        # Create user if doesn't exist
        user = UserService.get_user_by_phone_number(request.phone_number, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please register first."
            )
        
        # Create participant
        participant = RideParticipant(
            ride_id=ride_id,
            user_id=user.id,
            vehicle_info_id=request.vehicle_info_id,
            role="RIDER"
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        
        logger.info(f"User {user.id} joined ride {ride_id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "participant": RideParticipantResponse.from_orm(participant),
                "ride": RideResponse.from_orm(ride)
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error joining ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.put("/{ride_id}/participants/{participant_id}", status_code=status.HTTP_200_OK)
async def update_ride_participant(
    ride_id: str,
    participant_id: str,
    request: UpdateRideParticipant,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Update ride participant role (organization admin only)"""
    try:
        participant = db.query(RideParticipant).filter(RideParticipant.id == participant_id).first()
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant not found"
            )
        
        if participant.ride_id != ride_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Participant does not belong to this ride"
            )
        
        participant.role = request.role
        db.commit()
        
        logger.info(f"Participant {participant_id} role updated to {request.role}")
        
        return JSONResponse(
            content={"status": "success", "participant": RideParticipantResponse.from_orm(participant)}
        )
    except Exception as e:
        logger.exception(f"Error updating participant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/{ride_id}/checkin", status_code=status.HTTP_201_CREATED)
async def check_in(
    ride_id: str,
    request: CheckInRequest,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """Check in at checkpoint"""
    try:
        from datetime import datetime
        
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Find participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id
        ).first()
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not a participant of this ride"
            )
        
        # Create attendance record
        from db.models import AttendanceRecord
        attendance = AttendanceRecord(
            ride_id=ride_id,
            user_id=current_user.id,
            checkpoint_type=request.checkpoint_type,
            reached_at=datetime.now(),
            latitude=request.latitude,
            longitude=request.longitude
        )
        db.add(attendance)
        db.commit()
        
        logger.info(f"User {current_user.id} checked in at {request.checkpoint_type}")
        
        return JSONResponse(
            content={
                "status": "success",
                "attendance_record": AttendanceRecordResponse.from_orm(attendance)
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error checking in: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{ride_id}/join-link", status_code=status.HTTP_200_OK)
async def generate_join_link(
    ride_id: str,
    db: Session = Depends(get_db)
):
    """Generate join link for ride"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        join_url = f"https://yourapp.com/join-ride/{ride_id}"
        
        return JSONResponse(
            content={
                "status": "success",
                "join_url": join_url,
                "ride_name": ride.name
            }
        )
    except Exception as e:
        logger.exception(f"Error generating join link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/active", status_code=status.HTTP_200_OK)
async def get_active_rides(
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """Get user's active rides"""
    try:
        # Get rides where user is participant and ride is active
        active_rides = db.query(Ride).join(RideParticipant).filter(
            RideParticipant.user_id == current_user.id,
            Ride.status == "ACTIVE"
        ).all()
        
        return JSONResponse(
            content={
                "status": "success",
                "rides": [RideResponse.from_orm(ride) for ride in active_rides]
            }
        )
    except Exception as e:
        logger.exception(f"Error getting active rides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )
