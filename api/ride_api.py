from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
from datetime import datetime

from db.db_conn import get_db
from db.models import Ride, RideParticipant, RideCheckpoint, User, OrganizationMember, Organization
from db.schemas.ride import (
    CreateRide, UpdateRide, RideResponse,
    RideParticipantResponse, MarkPaymentRequest
)
from utils.dependencies import get_current_user, get_current_user_web
from utils.enums import OrganizationRole, UserRole, RideStatus
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


@router.post("/api/{ride_id}/join")
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


@router.post("/api/{ride_id}/mark-payment")
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

@router.get("/{org_id}/rides", name="organization_rides_page")
async def organization_rides_page(
        request: Request,
        org_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Organization rides page (Web)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # Get organization
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        return RedirectResponse(url=request.url_for('dashboard_page'))

    # Get user role
    from services.member_service import MemberService
    user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

    # Get all rides for this organization
    rides = db.query(Ride).filter(Ride.organization_id == org_id).order_by(Ride.created_at.desc()).all()

    # Categorize rides
    upcoming_rides = []
    active_rides = []
    past_rides = []

    for ride in rides:
        participants_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride.id
        ).scalar() or 0

        paid_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride.id,
            RideParticipant.has_paid == True
        ).scalar() or 0

        ride_data = {
            "id": str(ride.id),
            "name": ride.name,
            "status": ride.status.value,
            "max_riders": ride.max_riders,
            "participants_count": participants_count,
            "spots_left": ride.max_riders - participants_count,
            "requires_payment": ride.requires_payment,
            "amount": ride.amount,
            "paid_count": paid_count,
            "created_at": ride.created_at.strftime("%Y-%m-%d"),
            "started_at": ride.started_at.strftime("%Y-%m-%d %H:%M") if ride.started_at else None
        }

        if ride.status == RideStatus.PLANNED:
            upcoming_rides.append(ride_data)
        elif ride.status == RideStatus.ACTIVE:
            active_rides.append(ride_data)
        else:
            past_rides.append(ride_data)

    return jinja_templates.TemplateResponse(
        "organization/organization_rides.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "organizations",
            "organization": {
                "id": str(organization.id),
                "name": organization.name
            },
            "upcoming_rides": upcoming_rides,
            "active_rides": active_rides,
            "past_rides": past_rides,
            "user_role": user_role.value if user_role else None
        }
    )


@router.post("/{org_id}/rides/create", name="create_ride_web")
async def create_ride_web(
        request: Request,
        org_id: UUID,
        name: str = Form(...),
        max_riders: int = Form(30),
        requires_payment: bool = Form(False),
        amount: float = Form(0.0),
        # Checkpoints (we'll handle these as JSON or separate forms)
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
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

        # Create ride
        ride = Ride(
            organization_id=org_id,
            name=name,
            max_riders=max_riders,
            requires_payment=requires_payment,
            amount=amount,
            status=RideStatus.PLANNED
        )
        db.add(ride)
        db.commit()

        logger.info(f"Ride created via web: {ride.name}")

        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=str(org_id)),
            status_code=303
        )

    except Exception as e:
        logger.exception(f"Error creating ride: {e}")
        return RedirectResponse(
            url=request.url_for('organization_rides_page', org_id=str(org_id)),
            status_code=303
        )


@router.get("/{org_id}/rides/{ride_id}", name="ride_detail_page")
async def ride_detail_page(
        request: Request,
        org_id: UUID,
        ride_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Ride detail page (Web)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        return RedirectResponse(url=request.url_for('organization_rides_page', org_id=str(org_id)))

    organization = db.query(Organization).filter(Organization.id == org_id).first()

    # Get participants
    participants = db.query(RideParticipant).filter(
        RideParticipant.ride_id == ride_id
    ).all()

    participants_data = []
    for p in participants:
        user = db.query(User).filter(User.id == p.user_id).first()
        participants_data.append({
            "id": str(p.id),
            "user_id": str(p.user_id),
            "user_name": user.name if user else "Unknown",
            "user_phone": user.phone_number if user else "N/A",
            "role": p.role.value,
            "has_paid": p.has_paid,
            "paid_amount": p.paid_amount,
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "registered_at": p.registered_at.strftime("%Y-%m-%d")
        })

    # Get user role
    from services.member_service import MemberService
    user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

    # Generate share link
    share_link = f"{request.base_url}join-ride/{str(ride_id)}"

    return jinja_templates.TemplateResponse(
        "ride/ride_detail.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "organizations",
            "organization": {
                "id": str(organization.id),
                "name": organization.name
            },
            "ride": {
                "id": str(ride.id),
                "name": ride.name,
                "status": ride.status.value,
                "max_riders": ride.max_riders,
                "participants_count": len(participants),
                "spots_left": ride.max_riders - len(participants),
                "requires_payment": ride.requires_payment,
                "amount": ride.amount,
                "created_at": ride.created_at.strftime("%Y-%m-%d"),
                "started_at": ride.started_at.strftime("%Y-%m-%d %H:%M") if ride.started_at else None,
                "share_link": share_link
            },
            "participants": participants_data,
            "user_role": user_role.value if user_role else None
        }
    )