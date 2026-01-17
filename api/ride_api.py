import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from db.db_conn import get_db
from db.models import Ride, RideParticipant, RideCheckpoint, User, OrganizationMember, Organization, \
    UserRideInformation, AttendanceRecord
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

@router.post("/create", status_code=status.HTTP_201_CREATED)
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


@router.get("/list")
async def list_rides_api(
        organization_id: Optional[UUID] = None,
        status: Optional[str] = None,
        include_completed: bool = False,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    List rides (API - Mobile)
    - By default returns only PLANNED and ACTIVE rides
    - Use include_completed=true to include COMPLETED rides
    - Use status param to filter by specific status (planned/active/completed)
    - Sorted by scheduled_date: upcoming rides first, then by date proximity
    """
    try:
        query = db.query(Ride)

        if organization_id:
            query = query.filter(Ride.organization_id == organization_id)

        # Status filtering
        if status:
            # If specific status requested, use that
            query = query.filter(Ride.status == status)
        elif not include_completed:
            # Default: exclude completed rides
            query = query.filter(Ride.status.in_([RideStatus.PLANNED, RideStatus.ACTIVE]))

        # Sort by scheduled_date
        # - Active rides first
        # - Then upcoming planned rides (nearest date first)
        # - Then completed rides (most recent first) if included
        from sqlalchemy import case, desc, asc, nullslast
        
        # Custom sort: ACTIVE first, then by scheduled_date ascending (upcoming first)
        # For completed rides, we want most recent first (descending)
        rides = query.order_by(
            # Active rides come first
            case(
                (Ride.status == RideStatus.ACTIVE, 0),
                (Ride.status == RideStatus.PLANNED, 1),
                (Ride.status == RideStatus.COMPLETED, 2),
                else_=3
            ),
            # For non-completed: ascending (nearest upcoming first)
            # For completed: we still want older at bottom
            nullslast(Ride.scheduled_date.asc())
        ).all()

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
            "rides": rides_data,
            "total": len(rides_data)
        }

    except Exception as e:
        logger.exception(f"Error listing rides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch rides"
        )


@router.put("/{ride_id}")
async def update_ride_api(
        ride_id: UUID,
        ride_data: UpdateRide,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update ride (API - Mobile) - only for non-completed rides"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )

        # Check if ride is completed - completed rides cannot be edited
        if ride.status == RideStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed rides cannot be edited"
            )

        # Verify user is admin of organization
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_(
                [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization admins can update rides"
            )

        # Update only provided fields
        if ride_data.name is not None:
            ride.name = ride_data.name
        if ride_data.max_riders is not None:
            ride.max_riders = ride_data.max_riders
        if ride_data.requires_payment is not None:
            ride.requires_payment = ride_data.requires_payment
        if ride_data.amount is not None:
            ride.amount = ride_data.amount
        if ride_data.status is not None:
            # Don't allow changing from completed to other status
            if ride.status != RideStatus.COMPLETED:
                ride.status = RideStatus(ride_data.status)

        db.commit()
        db.refresh(ride)

        logger.info(f"Ride updated: {ride.name} by {current_user.id}")

        return {
            "status": "success",
            "message": "Ride updated successfully",
            "ride": RideResponse.model_validate(ride).model_dump(mode='json')
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error updating ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ride"
        )


@router.get("/{ride_id}")
async def get_ride_api(
        request: Request,
        ride_id: UUID,
        db: Session = Depends(get_db)
):
    """Get ride details (API - Mobile) - supports both authenticated and unauthenticated"""
    try:
        # Get current user from Authorization header
        from utils.app_helper import verify_user_from_token
        
        current_user = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            if token:
                is_verified, msg, user = verify_user_from_token(token, db)
                if is_verified and user:
                    current_user = user
        
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return {
                "status": "error",
                "message": "Ride not found"
            }

        # Get organization info
        organization = db.query(Organization).filter(Organization.id == ride.organization_id).first()
        
        # Get checkpoints
        checkpoints = db.query(RideCheckpoint).filter(
            RideCheckpoint.ride_id == ride_id
        ).order_by(RideCheckpoint.type).all()
        
        checkpoints_data = []
        for cp in checkpoints:
            checkpoints_data.append({
                "id": str(cp.id),
                "type": cp.type.value if hasattr(cp.type, 'value') else str(cp.type),
                "latitude": cp.latitude,
                "longitude": cp.longitude,
                "address": cp.address,
                "radius_meters": cp.radius_meters
            })

        # Check if current user is admin FIRST (need this for participant data)
        is_admin = False
        if current_user:
            membership = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == ride.organization_id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
                OrganizationMember.is_active == True,
                OrganizationMember.is_deleted == False
            ).first()
            is_admin = membership is not None or current_user.role == UserRole.SUPER_ADMIN

        # Get participants with user and vehicle info (exclude deleted)
        participants = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.is_deleted == False
        ).all()

        # Get attendance records for this ride (meetup checkpoint)
        attendance_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride_id,
            AttendanceRecord.checkpoint_type == 'meetup'
        ).all()
        attendance_lookup = {str(a.user_id): a.status for a in attendance_records}

        participants_data = []
        for p in participants:
            p_dict = RideParticipantResponse.model_validate(p).model_dump(mode='json')
            
            # Add user info - more details for admins
            user = db.query(User).filter(User.id == p.user_id).first()
            if user:
                user_info = {
                    "id": str(user.id),
                    "name": user.name,
                    "profile_picture": user.profile_picture_url
                }
                # Admins get full contact info
                if is_admin:
                    user_info["phone_number"] = user.phone_number
                    user_info["email"] = user.email
                p_dict['user'] = user_info
            
            # Add vehicle info
            if p.vehicle_info_id:
                vehicle = db.query(UserRideInformation).filter(
                    UserRideInformation.id == p.vehicle_info_id
                ).first()
                if vehicle:
                    p_dict['vehicle'] = {
                        "id": str(vehicle.id),
                        "make": vehicle.make,
                        "model": vehicle.model,
                        "year": vehicle.year,
                        "license_plate": vehicle.license_plate
                    }
            
            # Add attendance status
            p_dict['attendance_status'] = attendance_lookup.get(str(p.user_id))
            
            participants_data.append(p_dict)
        
        # Check if current user is a participant
        is_participant = False
        my_vehicle = None
        
        if current_user:
            my_record = next((p for p in participants if str(p.user_id) == str(current_user.id)), None)
            if my_record:
                is_participant = True
                if my_record.vehicle_info_id:
                    vehicle = db.query(UserRideInformation).filter(
                        UserRideInformation.id == my_record.vehicle_info_id
                    ).first()
                    if vehicle:
                        my_vehicle = {
                            "id": str(vehicle.id),
                            "make": vehicle.make,
                            "model": vehicle.model,
                            "year": vehicle.year,
                            "license_plate": vehicle.license_plate
                        }

        ride_dict = RideResponse.model_validate(ride).model_dump(mode='json')
        ride_dict['organization'] = {
            "id": str(organization.id) if organization else None,
            "name": organization.name if organization else "Unknown",
            "logo": organization.logo if organization else None
        }
        ride_dict['checkpoints'] = checkpoints_data
        ride_dict['participants'] = participants_data
        ride_dict['participants_count'] = len(participants)
        ride_dict['spots_left'] = ride.max_riders - len(participants)
        ride_dict['is_admin'] = is_admin
        ride_dict['is_participant'] = is_participant
        ride_dict['my_vehicle'] = my_vehicle

        return {
            "status": "success",
            "ride": ride_dict
        }

    except Exception as e:
        logger.exception(f"Error fetching ride: {e}")
        return {
            "status": "error",
            "message": "Failed to fetch ride"
        }


@router.post("/{ride_id}/join", name='join_ride')
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

        # Check if user has an existing record (including deleted/banned)
        existing = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id
        ).first()

        if existing:
            # Check if banned
            if existing.role == ParticipantRole.BANNED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are banned from this ride. Please contact the admin."
                )
            
            # Check if previously deleted (removed) - allow rejoin
            if existing.is_deleted:
                # Reactivate the participant
                existing.is_deleted = False
                existing.role = ParticipantRole.RIDER
                existing.vehicle_info_id = vehicle_info_id
                existing.has_paid = False if ride.requires_payment else True
                existing.paid_amount = 0.0
                db.commit()
                db.refresh(existing)
                
                logger.info(f"User {current_user.id} rejoined ride {ride_id}")
                
                return {
                    "status": "success",
                    "message": "Successfully rejoined ride",
                    "participant": RideParticipantResponse.model_validate(existing).model_dump(mode='json'),
                    "payment_required": ride.requires_payment,
                    "amount": ride.amount
                }
            
            # Already an active participant
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already joined this ride"
            )

        # Check capacity (exclude deleted participants)
        current_count = db.query(func.count(RideParticipant.id)).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.is_deleted == False
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
            role=ParticipantRole.RIDER,
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


@router.put("/{ride_id}/my-vehicle")
async def update_my_vehicle_api(
        ride_id: UUID,
        vehicle_info_id: UUID = Body(..., embed=True),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update participant's vehicle for a ride (Mobile API - Self only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Check if ride is still active/planned (can't change vehicle on completed ride)
        if ride.status == RideStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Cannot change vehicle for a completed ride")

        # Get current user's participation
        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id,
            RideParticipant.is_deleted == False
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="You are not a participant of this ride")

        if participant.role == ParticipantRole.BANNED:
            raise HTTPException(status_code=403, detail="You are banned from this ride")

        # Verify vehicle belongs to user
        vehicle = db.query(UserRideInformation).filter(
            UserRideInformation.id == vehicle_info_id,
            UserRideInformation.user_id == current_user.id
        ).first()

        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found or doesn't belong to you")

        # Update vehicle
        participant.vehicle_info_id = vehicle_info_id
        db.commit()
        db.refresh(participant)

        logger.info(f"User {current_user.id} updated vehicle for ride {ride_id}")

        return {
            "status": "success",
            "message": "Vehicle updated successfully",
            "vehicle": {
                "id": str(vehicle.id),
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "license_plate": vehicle.license_plate
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error updating vehicle: {e}")
        raise HTTPException(status_code=500, detail="Failed to update vehicle")


# ============================================
# PARTICIPANT MANAGEMENT API ENDPOINTS (Mobile)
# ============================================


@router.post("/{ride_id}/participants/{participant_id}/mark-payment")
async def mark_payment_api(
        ride_id: UUID,
        participant_id: UUID,
        amount: float = Body(..., embed=True),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Mark payment for participant (Mobile API - Admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Verify admin permission
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only admins can mark payments")

        # Get participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        # Toggle payment status
        participant.has_paid = not participant.has_paid
        if participant.has_paid:
            participant.paid_amount = amount
            participant.payment_date = datetime.now(timezone.utc)
        else:
            participant.paid_amount = 0
            participant.payment_date = None

        db.commit()

        logger.info(f"Payment {'marked' if participant.has_paid else 'unmarked'} for participant {participant.id}")

        return {
            "status": "success",
            "message": f"Payment {'confirmed' if participant.has_paid else 'unmarked'}",
            "has_paid": participant.has_paid,
            "paid_amount": participant.paid_amount
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error marking payment: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark payment")


@router.post("/{ride_id}/participants/{participant_id}/mark-attendance")
async def mark_attendance_api(
        ride_id: UUID,
        participant_id: UUID,
        status: str = Body(..., embed=True),  # 'present' or 'absent'
        checkpoint_type: str = Body("meetup", embed=True),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Mark attendance for participant (Mobile API - Admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Verify admin permission
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only admins can mark attendance")

        # Get participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        # Check/create attendance record
        existing = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride_id,
            AttendanceRecord.user_id == participant.user_id,
            AttendanceRecord.checkpoint_type == checkpoint_type
        ).first()

        if existing:
            existing.status = status
            existing.marked_by = current_user.id
            existing.marked_at = datetime.now(timezone.utc)
        else:
            attendance = AttendanceRecord(
                ride_id=ride_id,
                user_id=participant.user_id,
                checkpoint_type=checkpoint_type,
                status=status,
                marked_by=current_user.id,
                marked_at=datetime.now(timezone.utc)
            )
            db.add(attendance)

        db.commit()

        logger.info(f"Attendance marked: {status} for user {participant.user_id}")

        return {
            "status": "success",
            "message": f"Marked as {status}",
            "attendance_status": status
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error marking attendance: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark attendance")


@router.delete("/{ride_id}/participants/{participant_id}")
async def remove_participant_api(
        ride_id: UUID,
        participant_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Remove participant from ride (Mobile API - Admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Verify admin permission
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only admins can remove participants")

        # Get participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        # Store user_id before deletion for logging
        user_id = participant.user_id

        # Soft delete - mark as deleted instead of removing
        participant.is_deleted = True
        db.commit()

        logger.info(f"Participant {user_id} soft-deleted from ride {ride_id}")

        return {
            "status": "success",
            "message": "Participant removed from ride"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error removing participant: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove participant")


@router.post("/{ride_id}/participants/{participant_id}/toggle-ban")
async def toggle_participant_ban_api(
        ride_id: UUID,
        participant_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Toggle ban status for participant (Mobile API - Admin only)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Verify admin permission
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()

        if not membership and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only admins can ban/unban participants")

        # Get participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        # Toggle ban status (using is_active field, or we could add a new field)
        # For now, we'll use a soft approach - change role to 'banned'
        from utils.enums import ParticipantRole
        
        if participant.role == ParticipantRole.BANNED:
            participant.role = ParticipantRole.RIDER
            is_banned = False
        else:
            participant.role = ParticipantRole.BANNED
            is_banned = True

        db.commit()

        logger.info(f"Participant {participant.user_id} {'banned' if is_banned else 'unbanned'} from ride {ride_id}")

        return {
            "status": "success",
            "message": f"Participant {'banned' if is_banned else 'unbanned'}",
            "is_banned": is_banned
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error toggling ban: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ban status")


@router.post("{ride_id}/mark-payment", name="mark_payment_web")
async def mark_payment_web(
        request: Request,
        ride_id: UUID,
        participant_id: str = Form(...),
        amount: str = Form(...),
        current_user: User = Depends(get_current_user_web),
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
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant not found"
            )

        participant.has_paid = True
        participant.paid_amount = amount
        participant.payment_date = datetime.now(timezone.utc)

        db.commit()

        logger.info(f"Payment marked for participant {participant.id}")

        return RedirectResponse(
            url=request.url_for('org_ride_detail_page', org_id=str(ride.organization_id), ride_id=ride.id),
            status_code=303
        )

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
        new_vehicle_make: Optional[str] = Form(None),
        new_vehicle_model: Optional[str] = Form(None),
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
        if vehicle_info_id == 'new':
            user_ride_information = UserRideInformation(
                user_id=current_user.id,
                make=new_vehicle_make,
                model=new_vehicle_model,
                is_pillion=False
            )
            db.add(user_ride_information)
            db.commit()
            vehicle_info_id = str(user_ride_information.id)
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


@router.post("/{ride_id}/mark-attendance", name="mark_attendance_web")
async def mark_attendance_web(
        request: Request,
        ride_id: UUID,
        participant_id: UUID = Form(...),
        status: str = Form(...),  # 'present' or 'absent'
        reason: Optional[str] = Form(None),
        checkpoint_type: str = Form("meetup"),  # meetup, destination, disbursement
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Mark attendance for participant (Web)"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Check permission
        PermissionDependency.require_org_admin(ride.organization_id)

        # Validate ride is active
        if ride.status != RideStatus.ACTIVE:
            # TODO: Flash message "Can only mark attendance for active rides"
            return RedirectResponse(
                url=request.url_for('ride_detail_page', org_id=ride.organization_id, ride_id=ride_id),
                status_code=303
            )

        # Get participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.id == participant_id,
            RideParticipant.ride_id == ride_id
        ).first()

        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        # Check if attendance already exists
        existing = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride_id,
            AttendanceRecord.user_id == participant.user_id,
            AttendanceRecord.checkpoint_type == checkpoint_type
        ).first()

        if existing:
            # Update existing
            existing.status = status
            existing.marked_by = current_user.id
            existing.marked_at = datetime.now(timezone.utc)
            if status == 'absent' and reason:
                existing.reason = reason
        else:
            # Create new
            attendance = AttendanceRecord(
                ride_id=ride_id,
                user_id=participant.user_id,
                checkpoint_type=checkpoint_type,
                status=status,
                marked_by=current_user.id,
                marked_at=datetime.now(timezone.utc),
                reason=reason if status == 'absent' else None
            )
            db.add(attendance)

        db.commit()

        logger.info(f"Attendance marked: {status} for user {participant.user_id} by {current_user.id}")

        return RedirectResponse(
            url=request.url_for('org_ride_detail_page', org_id=ride.organization_id, ride_id=ride_id),
            status_code=303
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error marking attendance: {e}")
        return RedirectResponse(
            url=request.url_for('org_ride_detail_page', org_id=ride.organization_id, ride_id=ride_id),
            status_code=303
        )