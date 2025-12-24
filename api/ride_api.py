import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
from datetime import datetime

from db.db_conn import get_db
from db.models import Ride, RideParticipant, RideCheckpoint, User, OrganizationMember, Organization, UserRideInformation
from db.schemas.ride import (
    CreateRide, UpdateRide, RideResponse,
    RideParticipantResponse, MarkPaymentRequest
)
from utils import ParticipantRole, RideType, CheckpointType
from utils.dependencies import get_current_user, get_current_user_web
from utils.enums import OrganizationRole, UserRole, RideStatus
from utils.permissions import PermissionChecker, PermissionDependency
from utils.templates import jinja_templates
from utils.app_logger import createLogger

logger = createLogger("ride_routes")
router = APIRouter(prefix="/rides", tags=["rides"])


# API Endpoints (for Mobile App)

@router.post("/api/create", status_code=status.HTTP_201_CREATED)
async def create_ride_api(
        ride_data: CreateRide,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Create ride (API - Mobile)"""
    try:
        # Verify user is admin of organization
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride_data.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_(
                [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization admins can create rides"
            )

        # Create ride
        ride = Ride(
            organization_id=ride_data.organization_id,
            name=ride_data.name,
            max_riders=ride_data.max_riders,
            requires_payment=ride_data.requires_payment,
            amount=ride_data.amount,
            status=RideStatus.PLANNED
        )
        db.add(ride)
        db.flush()

        # Create checkpoints
        for cp_data in ride_data.checkpoints:
            checkpoint = RideCheckpoint(
                ride_id=ride.id,
                type=cp_data.type,
                latitude=cp_data.latitude,
                longitude=cp_data.longitude,
                radius_meters=cp_data.radius_meters
            )
            db.add(checkpoint)

        db.commit()
        db.refresh(ride)

        logger.info(f"Ride created: {ride.name} by {current_user.id}")

        return {
            "status": "success",
            "message": "Ride created successfully",
            "ride": RideResponse.model_validate(ride).model_dump(mode='json')
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error creating ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ride"
        )


@router.get("/api/list")
async def list_rides_api(
        organization_id: Optional[UUID] = None,
        status: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """List rides (API - Mobile)"""
    try:
        query = db.query(Ride)

        if organization_id:
            query = query.filter(Ride.organization_id == organization_id)

        if status:
            query = query.filter(Ride.status == status)

        rides = query.order_by(Ride.created_at.desc()).all()

        rides_data = []
        for ride in rides:
            participants_count = db.query(func.count(RideParticipant.id)).filter(
                RideParticipant.ride_id == ride.id
            ).scalar() or 0

            ride_dict = RideResponse.model_validate(ride).model_dump(mode='json')
            ride_dict['participants_count'] = participants_count
            ride_dict['spots_left'] = ride.max_riders - participants_count
            rides_data.append(ride_dict)

        return {
            "status": "success",
            "rides": rides_data
        }

    except Exception as e:
        logger.exception(f"Error listing rides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch rides"
        )


@router.get("/api/{ride_id}")
async def get_ride_api(
        ride_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get ride details (API - Mobile)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )

        # Get participants
        participants = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id
        ).all()

        participants_data = []
        for p in participants:
            p_dict = RideParticipantResponse.model_validate(p).model_dump(mode='json')
            # Add user info
            user = db.query(User).filter(User.id == p.user_id).first()
            if user:
                p_dict['user_name'] = user.name
                p_dict['user_phone'] = user.phone_number
            participants_data.append(p_dict)

        ride_dict = RideResponse.model_validate(ride).model_dump(mode='json')
        ride_dict['participants'] = participants_data
        ride_dict['participants_count'] = len(participants)
        ride_dict['spots_left'] = ride.max_riders - len(participants)

        return {
            "status": "success",
            "ride": ride_dict
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch ride"
        )


@router.get("/{ride_id}/join", name='join_ride')
async def join_ride_api(
        ride_id: UUID,
        vehicle_info_id: Optional[UUID] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Join ride (API - Mobile)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )

        # Check if already joined
        existing = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already joined this ride"
            )

        # Check capacity
        current_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride_id
        ).scalar() or 0

        if current_count >= ride.max_riders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ride is full"
            )

        # Create participant
        participant = RideParticipant(
            ride_id=ride_id,
            user_id=current_user.id,
            vehicle_info_id=vehicle_info_id,
            role="rider",
            has_paid=False if ride.requires_payment else True,
            paid_amount=0.0
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)

        logger.info(f"User {current_user.id} joined ride {ride_id}")

        return {
            "status": "success",
            "message": "Successfully joined ride",
            "participant": RideParticipantResponse.model_validate(participant).model_dump(mode='json'),
            "payment_required": ride.requires_payment,
            "amount": ride.amount
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error joining ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join ride"
        )


@router.post("{ride_id}/mark-payment")
async def mark_payment_api(
        ride_id: UUID,
        payment_data: MarkPaymentRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Mark payment for participant (Admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )

        # Verify admin
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_(
                [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can mark payments"
            )

        # Update participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == payment_data.participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant not found"
            )

        participant.has_paid = True
        participant.paid_amount = payment_data.amount
        participant.payment_date = datetime.utcnow()

        db.commit()

        logger.info(f"Payment marked for participant {participant.id}")

        return {
            "status": "success",
            "message": "Payment marked successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error marking payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark payment"
        )


# Web Routes (for Dashboard)
@router.post("/{org_id}/rides/create", name="create_ride_web")
async def create_ride_web(
        request: Request,
        org_id: UUID,
        name: str = Form(...),
        max_riders: int = Form(30),
        scheduled_date: str = Form(...),
        requires_payment: bool = Form(False),
        amount: float = Form(0.0),
        # Checkpoints (we'll handle these as JSON or separate forms)
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db),
        ride_type: str = Form(...),
):
    """Create ride (Web)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        # Verify admin
        from services.member_service import MemberService
        user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

        if not user_role and current_user.role != UserRole.SUPER_ADMIN:
            return RedirectResponse(
                url=request.url_for('organization_detail_page', org_id=str(org_id)),
                status_code=303
            )

        scheduled_dt = datetime.fromisoformat(scheduled_date)
        now = datetime.now()


        # Create ride
        ride = Ride(
            organization_id=org_id,
            name=name,
            max_riders=max_riders,
            scheduled_date=scheduled_dt,
            requires_payment=requires_payment,
            amount=amount,
            status=RideStatus.PLANNED,
            ride_type=RideType(ride_type)
        )
        db.add(ride)
        db.commit()

        logger.info(f"Ride created via web: {ride.name}")

        return RedirectResponse(
            url=request.url_for('add_checkpoints_page', org_id=str(org_id)),
            status_code=303
        )

    except Exception as e:
        logger.exception(f"Error creating ride: {e}")
        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=str(org_id)),
            status_code=303
        )


@router.get("/join/{ride_id}", name='join_ride_page')
async def join_ride_page(
        request: Request,
        ride_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Smart join ride handler - works for both web and mobile
    1. Check if user is authenticated
    2. If not -> redirect to login with forward_url
    3. If yes -> show join form
    """
    try:
        # Get ride details
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return jinja_templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Ride not found",
                    "message": "This ride doesn't exist or has been deleted."
                }
            )

        organization = db.query(Organization).filter(Organization.id == ride.organization_id).first()

        # Check if user is authenticated
        access_token = request.cookies.get("access_token")

        if not access_token:
            # Not authenticated - redirect to login with forward_url
            next_path = request.url_for('join_ride_page', ride_id=ride_id).path
            login_url = request.url_for('login_page').include_query_params(forward_url=next_path)
            return RedirectResponse(url=str(login_url), status_code=302)

        # User is authenticated - verify token
        from utils.app_helper import verify_user_from_token
        is_verified, msg, current_user = verify_user_from_token(access_token, db)

        if not is_verified or not current_user:
            # Invalid token - redirect to login
            next_path = request.url_for('join_ride_page', ride_id=ride_id).path
            login_url = request.url_for('login_page').include_query_params(forward_url=next_path)
            return RedirectResponse(url=str(login_url), status_code=302)

        # Check if already joined
        existing = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id
        ).first()

        if existing:
            # Already joined - redirect to ride detail
            ride_detail_url = request.url_for(
                'ride_detail_page',
                org_id=ride.organization_id,
                ride_id=ride_id
            ).include_query_params(message="already_joined")
            return RedirectResponse(url=str(ride_detail_url), status_code=302)

        # Check capacity
        current_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride_id
        ).scalar() or 0

        if current_count >= ride.max_riders:
            return jinja_templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Ride is Full",
                    "message": "This ride has reached maximum capacity."
                }
            )

        # Get user's vehicles
        vehicles = db.query(UserRideInformation).filter(
            UserRideInformation.user_id == current_user.id
        ).all()

        # Show join form
        return jinja_templates.TemplateResponse(
            "ride/join_ride.html",
            {
                "request": request,
                "user": current_user,
                "ride": {
                    "id": str(ride.id),
                    "name": ride.name,
                    "organization_name": organization.name,
                    "max_riders": ride.max_riders,
                    "participants_count": current_count,
                    "spots_left": ride.max_riders - current_count,
                    "requires_payment": ride.requires_payment,
                    "amount": ride.amount
                },
                "vehicles": [
                    {
                        "id": str(v.id),
                        "make": v.make,
                        "model": v.model,
                        "license_plate": v.license_plate or "N/A"
                    } for v in vehicles
                ]
            }
        )

    except Exception as e:
        logger.exception(f"Error in join ride page: {e}")
        return jinja_templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Something went wrong",
                "message": "Please try again later."
            }
        )

@router.post("/join/{ride_id}/confirm", name='confirm_join_ride')
async def confirm_join_ride(
        request: Request,
        ride_id: UUID,
        vehicle_info_id: Optional[str] = Form(None),
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Confirm joining ride after filling form"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Check if already joined
        existing = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id
        ).first()

        if existing:
            return RedirectResponse(
                url=f"/v1/organizations/{ride.organization_id}/rides/{ride_id}",
                status_code=303
            )

        # Check capacity
        current_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride_id
        ).scalar() or 0

        if current_count >= ride.max_riders:
            return jinja_templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Ride is Full",
                    "message": "Sorry, this ride filled up while you were joining."
                }
            )

        # Create participant
        participant = RideParticipant(
            ride_id=ride_id,
            user_id=current_user.id,
            vehicle_info_id=UUID(vehicle_info_id) if vehicle_info_id and vehicle_info_id != "none" else None,
            role=ParticipantRole.RIDER,
            has_paid=False if ride.requires_payment else True,
            paid_amount=0.0
        )
        db.add(participant)
        db.commit()

        logger.info(f"User {current_user.id} joined ride {ride_id}")

        # Redirect to ride detail with success message
        return RedirectResponse(
            url=f"/v1/organizations/{ride.organization_id}/rides/{ride_id}?message=joined_successfully",
            status_code=303
        )

    except Exception as e:
        db.rollback()
        logger.exception(f"Error confirming join: {e}")
        return jinja_templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to join ride",
                "message": "Please try again."
            }
        )

@router.post("/{ride_id}/checkpoints/add")
async def add_checkpoint_api(
        ride_id: UUID,
        checkpoint_data: dict = Body(...),
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Add single checkpoint"""
    checkpoint = RideCheckpoint(
        ride_id=ride_id,
        type=CheckpointType(checkpoint_data['type']),
        latitude=checkpoint_data['latitude'],
        longitude=checkpoint_data['longitude'],
        address=checkpoint_data.get('address')
    )
    db.add(checkpoint)
    db.commit()
    return {"status": "success"}


@router.post("/{ride_id}/finalize")
async def finalize_ride_web(
        ride_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Change ride status from DRAFT to PLANNED"""
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    ride.status = RideStatus.PLANNED
    db.commit()
    return {"status": "success"}


@router.post("/join/{ride_id}/confirm", name="confirm_join_ride")
async def confirm_join_ride(
        request: Request,
        ride_id: UUID,
        vehicle_info_id: Optional[str] = Form(None),
        new_vehicle_make: Optional[str] = Form(None),
        new_vehicle_model: Optional[str] = Form(None),
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Existing user join ride"""
    try:
        # Create new vehicle if provided
        final_vehicle_id = None
        if new_vehicle_make and new_vehicle_model:
            vehicle = UserRideInformation(
                user_id=current_user.id,
                make=new_vehicle_make,
                model=new_vehicle_model,
                is_primary=False
            )
            db.add(vehicle)
            db.flush()
            final_vehicle_id = vehicle.id
        elif vehicle_info_id:
            final_vehicle_id = UUID(vehicle_info_id)

        # Join ride
        participant = RideParticipant(
            ride_id=ride_id,
            user_id=current_user.id,
            vehicle_info_id=final_vehicle_id,
            role=ParticipantRole.RIDER,
            has_paid=False
        )
        db.add(participant)
        db.commit()

        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        return RedirectResponse(url=f"/v1/organizations/{ride.organization_id}/rides/{ride_id}", status_code=303)

    except Exception as e:
        db.rollback()
        return RedirectResponse(url=f"/v1/rides/join/{ride_id}", status_code=303)


@router.post("/{ride_id}/start", name="start_ride_web")
async def start_ride_web(
        request: Request,
        ride_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Start ride (Web form)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return RedirectResponse(
                url=request.url_for('organization_rides_page', org_id=ride.organization_id),
                status_code=303
            )

        # Check permission
        PermissionDependency.require_org_admin(ride.organization_id)

        # Validate state
        if ride.status != RideStatus.PLANNED:
            # TODO: Add flash message
            return RedirectResponse(
                url=request.url_for('organization_rides_page', org_id=ride.organization_id),
                status_code=303
            )

        # Check checkpoints
        checkpoints_count = db.query(func.count(RideCheckpoint.id)).filter(
            RideCheckpoint.ride_id == ride_id
        ).scalar() or 0

        if checkpoints_count < 3:
            # TODO: Add flash message "Add checkpoints first"
            return RedirectResponse(
                url=request.url_for('organization_rides_page', org_id=ride.organization_id),
                status_code=303
            )

        # Start ride
        ride.status = RideStatus.ACTIVE
        ride.started_at = datetime.utcnow()
        db.commit()

        logger.info(f"Ride {ride_id} started by {current_user.id}")

        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=ride.organization_id),
            status_code=303
        )

    except Exception as e:
        db.rollback()
        logger.exception(f"Error starting ride: {e}")
        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=ride.organization_id),
            status_code=303
        )


@router.post("/{ride_id}/end", name="end_ride_web")
async def end_ride_web(
        request: Request,
        ride_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """End ride (Web form)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return RedirectResponse(
                url=request.url_for('organization_rides_page', org_id=ride.organization_id),
                status_code=303
            )

        # Check permission
        PermissionDependency.require_org_admin(ride.organization_id)

        # Validate state
        if ride.status != RideStatus.ACTIVE:
            return RedirectResponse(
                url=request.url_for('organization_rides_page', org_id=ride.organization_id),
                status_code=303
            )

        # End ride
        ride.status = RideStatus.COMPLETED
        ride.ended_at = datetime.utcnow()
        db.commit()

        logger.info(f"Ride {ride_id} ended by {current_user.id}")

        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=ride.organization_id),
            status_code=303
        )

    except Exception as e:
        db.rollback()
        logger.exception(f"Error ending ride: {e}")
        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=ride.organization_id),
            status_code=303
        )