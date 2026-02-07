"""
Intercom API - Universal Intercom endpoints for LiveKit audio communication
Enables Lead Rider to broadcast audio to all participants during active rides.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from db.db_conn import get_db
from db.models import (
    Ride, RideParticipant, User, OrganizationMember, RideActivity
)
from services.livekit_service import livekit_service
from utils.dependencies import get_current_user
from utils.enums import RideStatus, ParticipantRole, OrganizationRole, ActivityType
from utils.app_logger import createLogger

logger = createLogger("intercom")
router = APIRouter(prefix="/rides", tags=["intercom"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class SetLeadRequest(BaseModel):
    user_id: str  # UUID of the user to become Lead


class IntercomTokenResponse(BaseModel):
    status: str
    token: str
    livekit_url: str
    room_name: str
    is_lead: bool
    lead_info: Optional[dict] = None


class IntercomStatusResponse(BaseModel):
    status: str
    is_available: bool
    ride_status: str
    lead: Optional[dict] = None
    participants_connected: int = 0


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_org_admin(db: Session, user_id: UUID, organization_id: UUID) -> bool:
    """Check if user is an admin of the organization"""
    member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == user_id,
        OrganizationMember.is_deleted == False,
        OrganizationMember.is_active == True
    ).first()
    
    if not member:
        return False
    
    admin_roles = [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]
    return member.role in admin_roles


def get_ride_lead(db: Session, ride_id: UUID) -> Optional[RideParticipant]:
    """Get the current Lead participant for a ride"""
    return db.query(RideParticipant).filter(
        RideParticipant.ride_id == ride_id,
        RideParticipant.role == ParticipantRole.LEAD,
        RideParticipant.is_deleted == False
    ).first()


def create_activity(db: Session, ride_id: UUID, activity_type: str, user_id: UUID, message: str):
    """Create an activity entry for the feed"""
    activity = RideActivity(
        ride_id=ride_id,
        user_id=user_id,
        activity_type=activity_type,
        message=message
    )
    db.add(activity)
    return activity


# ============================================
# INTERCOM TOKEN ENDPOINT
# ============================================

@router.get("/{ride_id}/intercom/token")
async def get_intercom_token(
    ride_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get LiveKit token to connect to the ride's intercom room.
    
    Returns different permissions based on user role:
    - Lead: Can publish (broadcast) and subscribe (listen)
    - Others: Can only subscribe (listen)
    """
    try:
        # Verify ride exists
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        # Check ride is active (intercom only available during active ride)
        if ride.status != RideStatus.ACTIVE:
            raise HTTPException(
                status_code=400, 
                detail=f"Intercom only available for active rides. Current status: {ride.status.value}"
            )
        
        # Verify user is a participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id,
            RideParticipant.is_deleted == False
        ).first()
        
        if not participant:
            raise HTTPException(status_code=403, detail="You are not a participant of this ride")
        
        if participant.role == ParticipantRole.BANNED:
            raise HTTPException(status_code=403, detail="You are banned from this ride")
        
        # Check if user is the Lead
        is_lead = participant.role == ParticipantRole.LEAD
        
        # Generate token
        token = livekit_service.generate_token(
            ride_id=ride_id,
            user_id=current_user.id,
            user_name=current_user.name or "Rider",
            is_lead=is_lead
        )
        
        if not token:
            raise HTTPException(status_code=500, detail="Failed to generate intercom token")
        
        # Get Lead info for response
        lead_info = None
        if not is_lead:
            lead_participant = get_ride_lead(db, ride_id)
            if lead_participant:
                lead_user = db.query(User).filter(User.id == lead_participant.user_id).first()
                if lead_user:
                    lead_info = {
                        "id": str(lead_user.id),
                        "name": lead_user.name,
                        "profile_picture": lead_user.profile_picture_url
                    }
        
        return {
            "status": "success",
            "token": token,
            "livekit_url": livekit_service.get_livekit_url(),
            "room_name": livekit_service.get_room_name(ride_id),
            "is_lead": is_lead,
            "lead_info": lead_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting intercom token: {e}")
        raise HTTPException(status_code=500, detail="Failed to get intercom token")


# ============================================
# INTERCOM STATUS ENDPOINT
# ============================================

@router.get("/{ride_id}/intercom/status")
async def get_intercom_status(
    ride_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current intercom status for a ride.
    Shows if intercom is available and who is the Lead.
    """
    try:
        # Verify ride exists
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        # Check if intercom is available (ride must be active)
        is_available = ride.status == RideStatus.ACTIVE
        
        # Get Lead info
        lead_info = None
        lead_participant = get_ride_lead(db, ride_id)
        if lead_participant:
            lead_user = db.query(User).filter(User.id == lead_participant.user_id).first()
            if lead_user:
                lead_info = {
                    "id": str(lead_user.id),
                    "name": lead_user.name,
                    "profile_picture": lead_user.profile_picture_url
                }
        
        
        # Get real-time participants from LiveKit
        participants = await livekit_service.list_room_participants(ride_id)
        
        # Find who is talking (publishing audio)
        active_speakers = []
        for p in participants:
            for t in p.get("tracks", []):
                # Check for active microphone
                if t.get("source") == "Source.MICROPHONE" and not t.get("muted"):
                    active_speakers.append(p.get("name"))

        return {
            "status": "success",
            "is_available": is_available,
            "ride_status": ride.status.value,
            "lead": lead_info,
            "participants_connected": len(participants),
            "active_speakers": active_speakers,
            "debug_info": participants  # Full debug info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting intercom status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get intercom status")


# ============================================
# SET LEAD ENDPOINT (Admin only)
# ============================================

@router.post("/{ride_id}/set-lead")
async def set_ride_lead(
    ride_id: UUID,
    request: SetLeadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set a participant as the Lead for this ride.
    Only Organization Admins can assign Lead.
    
    The Lead can broadcast audio to all participants.
    Previous Lead (if any) will be demoted to Rider.
    """
    try:
        # Verify ride exists
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        # Verify requester is an organization admin
        if not is_org_admin(db, current_user.id, ride.organization_id):
            raise HTTPException(
                status_code=403, 
                detail="Only organization admins can assign Lead"
            )
        
        # Parse target user ID
        try:
            target_user_id = UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Verify target user is a participant
        target_participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == target_user_id,
            RideParticipant.is_deleted == False
        ).first()
        
        if not target_participant:
            raise HTTPException(
                status_code=404, 
                detail="Target user is not a participant of this ride"
            )
        
        if target_participant.role == ParticipantRole.BANNED:
            raise HTTPException(
                status_code=400, 
                detail="Cannot assign banned user as Lead"
            )
        
        # Get target user for activity message
        target_user = db.query(User).filter(User.id == target_user_id).first()
        
        # Demote current Lead if exists
        current_lead = get_ride_lead(db, ride_id)
        if current_lead and current_lead.user_id != target_user_id:
            current_lead.role = ParticipantRole.RIDER
            logger.info(f"Demoted previous Lead {current_lead.user_id} to Rider")
        
        # Promote target to Lead
        target_participant.role = ParticipantRole.LEAD
        
        # Create activity
        create_activity(
            db=db,
            ride_id=ride_id,
            activity_type="lead_assigned",
            user_id=current_user.id,
            message=f"{target_user.name or 'A rider'} is now the Lead"
        )
        
        db.commit()
        
        logger.info(f"User {target_user_id} set as Lead for ride {ride_id} by {current_user.id}")
        
        return {
            "status": "success",
            "message": f"{target_user.name or 'User'} is now the Lead",
            "lead": {
                "id": str(target_user_id),
                "name": target_user.name,
                "profile_picture": target_user.profile_picture_url if target_user else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error setting ride lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to set lead")


# ============================================
# REMOVE LEAD ENDPOINT (Admin only)
# ============================================

@router.post("/{ride_id}/remove-lead")
async def remove_ride_lead(
    ride_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove the current Lead (demote to Rider).
    Only Organization Admins can do this.
    """
    try:
        # Verify ride exists
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        # Verify requester is an organization admin
        if not is_org_admin(db, current_user.id, ride.organization_id):
            raise HTTPException(
                status_code=403, 
                detail="Only organization admins can remove Lead"
            )
        
        # Get current Lead
        current_lead = get_ride_lead(db, ride_id)
        if not current_lead:
            return {
                "status": "success",
                "message": "No Lead currently assigned"
            }
        
        # Get user info for activity
        lead_user = db.query(User).filter(User.id == current_lead.user_id).first()
        
        # Demote to Rider
        current_lead.role = ParticipantRole.RIDER
        
        # Create activity
        create_activity(
            db=db,
            ride_id=ride_id,
            activity_type="lead_removed",
            user_id=current_user.id,
            message=f"{lead_user.name or 'The Lead'} is no longer the Lead"
        )
        
        db.commit()
        
        logger.info(f"Lead {current_lead.user_id} removed from ride {ride_id}")
        
        return {
            "status": "success",
            "message": f"{lead_user.name or 'User'} is no longer the Lead"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error removing lead: {e}")

# ============================================
# DEBUG LEAK ENDPOINT
# ============================================

@router.get("/{ride_id}/live/debug")
async def debug_livekit_room(
    ride_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to see raw LiveKit room state.
    Shows all participants and their active tracks (audio/video).
    """
    try:
        # Get real-time participants from LiveKit
        participants = await livekit_service.list_room_participants(ride_id)
        
        return {
            "status": "success",
            "ride_id": str(ride_id),
            "room_name": livekit_service.get_room_name(ride_id),
            "participant_count": len(participants),
            "participants": participants
        }
    except Exception as e:
        logger.exception(f"Error debugging LiveKit room: {e}")
        raise HTTPException(status_code=500, detail=str(e))
