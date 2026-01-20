"""
Live Ride API - Handles real-time ride features:
- Auto check-in at checkpoints
- Activity feed
- Location tracking
- SOS/Alert system
"""
import math
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from db.db_conn import get_db
from db.models import (
    Ride, RideParticipant, RideCheckpoint, RideActivity, UserLocation,
    AttendanceRecord, User, Organization
)
from db.schemas.activity import (
    CheckInRequest, LocationUpdateRequest, AlertRequest,
    ActivityResponse, ActivityFeedResponse, ActivityUser, ActivityCheckpoint,
    RiderLocationResponse, LiveRideDataResponse
)
from utils.dependencies import get_current_user
from utils.enums import RideStatus, CheckpointType, ActivityType, ParticipantRole
from utils.app_logger import createLogger

logger = createLogger("live_ride")
router = APIRouter(prefix="/rides", tags=["live-ride"])


# Constants
CHECKPOINT_RADIUS_DEFAULT = 100  # meters
EARTH_RADIUS_KM = 6371


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula"""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c * 1000  # Convert to meters


def find_nearest_checkpoint(lat: float, lon: float, checkpoints: list) -> tuple:
    """Find the nearest checkpoint to a location"""
    nearest = None
    min_distance = float('inf')

    for cp in checkpoints:
        distance = haversine_distance(lat, lon, cp.latitude, cp.longitude)
        if distance < min_distance:
            min_distance = distance
            nearest = cp

    return nearest, min_distance


def create_activity(
    db: Session,
    ride_id: UUID,
    activity_type: str,
    user_id: UUID = None,
    message: str = None,
    latitude: float = None,
    longitude: float = None,
    checkpoint_id: UUID = None,
    metadata_json: str = None
) -> RideActivity:
    """Helper to create and persist an activity"""
    activity = RideActivity(
        ride_id=ride_id,
        user_id=user_id,
        activity_type=activity_type,
        message=message,
        latitude=latitude,
        longitude=longitude,
        checkpoint_id=checkpoint_id,
        metadata_json=metadata_json
    )
    db.add(activity)
    db.flush()
    return activity


def format_activity_response(activity: RideActivity, db: Session) -> dict:
    """Format activity for API response"""
    user_data = None
    if activity.user_id:
        user = db.query(User).filter(User.id == activity.user_id).first()
        if user:
            user_data = {
                "id": str(user.id),
                "name": user.name,
                "profile_picture": user.profile_picture_url
            }

    checkpoint_data = None
    if activity.checkpoint_id:
        cp = db.query(RideCheckpoint).filter(RideCheckpoint.id == activity.checkpoint_id).first()
        if cp:
            checkpoint_data = {
                "id": str(cp.id),
                "type": cp.type.value if hasattr(cp.type, 'value') else str(cp.type),
                "address": cp.address
            }

    return {
        "id": str(activity.id),
        "activity_type": activity.activity_type,
        "message": activity.message,
        "user": user_data,
        "checkpoint": checkpoint_data,
        "latitude": activity.latitude,
        "longitude": activity.longitude,
        "created_at": activity.created_at.isoformat() if activity.created_at else None
    }


# ============================================
# CHECK-IN API
# ============================================

@router.post("/{ride_id}/checkin")
async def check_in_at_location(
    ride_id: UUID,
    request: CheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto check-in when user arrives at a checkpoint.
    - Detects nearest checkpoint within radius
    - Marks attendance automatically
    - Creates activity for the feed
    """
    try:
        # Verify ride exists and is active
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        if ride.status != RideStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail=f"Check-in only available for active rides. Current status: {ride.status}"
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

        # Get all checkpoints for this ride
        checkpoints = db.query(RideCheckpoint).filter(
            RideCheckpoint.ride_id == ride_id
        ).all()

        if not checkpoints:
            raise HTTPException(status_code=400, detail="No checkpoints defined for this ride")

        # Find nearest checkpoint
        nearest_cp, distance = find_nearest_checkpoint(
            request.latitude, request.longitude, checkpoints
        )

        if not nearest_cp:
            raise HTTPException(status_code=400, detail="Could not determine checkpoint")

        # Check if within radius
        radius = nearest_cp.radius_meters or CHECKPOINT_RADIUS_DEFAULT
        if distance > radius:
            return {
                "status": "not_at_checkpoint",
                "message": f"You are {int(distance)}m away from the nearest checkpoint ({nearest_cp.type.value}). Need to be within {radius}m.",
                "nearest_checkpoint": {
                    "type": nearest_cp.type.value,
                    "distance_meters": int(distance),
                    "required_radius": radius
                }
            }

        # Check if already checked in at this checkpoint
        existing = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride_id,
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.checkpoint_type == nearest_cp.type
        ).first()

        if existing:
            return {
                "status": "already_checked_in",
                "message": f"You already checked in at {nearest_cp.type.value}",
                "checked_in_at": existing.reached_at.isoformat() if existing.reached_at else None
            }

        # Create attendance record
        attendance = AttendanceRecord(
            ride_id=ride_id,
            user_id=current_user.id,
            checkpoint_type=nearest_cp.type,
            latitude=request.latitude,
            longitude=request.longitude,
            status='present',
            reached_at=datetime.now(timezone.utc)
        )
        db.add(attendance)

        # Determine activity type based on checkpoint
        activity_type_map = {
            CheckpointType.MEETUP: ActivityType.ARRIVED_MEETUP,
            CheckpointType.DESTINATION: ActivityType.REACHED_DESTINATION,
            CheckpointType.DISBURSEMENT: ActivityType.REACHED_HOME,
            CheckpointType.REFRESHMENT: ActivityType.CHECKED_IN_STOP,
        }
        activity_type = activity_type_map.get(nearest_cp.type, ActivityType.CHECKED_IN_STOP)

        # Create activity message
        checkpoint_label = nearest_cp.type.value.replace('_', ' ').title()
        message = f"{current_user.name or 'A rider'} arrived at {checkpoint_label}"

        # Create activity
        activity = create_activity(
            db=db,
            ride_id=ride_id,
            activity_type=activity_type.value,
            user_id=current_user.id,
            message=message,
            latitude=request.latitude,
            longitude=request.longitude,
            checkpoint_id=nearest_cp.id
        )

        db.commit()

        logger.info(f"User {current_user.id} checked in at {nearest_cp.type.value} for ride {ride_id}")

        return {
            "status": "success",
            "message": f"Checked in at {checkpoint_label}!",
            "checkpoint": {
                "type": nearest_cp.type.value,
                "address": nearest_cp.address
            },
            "activity": format_activity_response(activity, db)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error during check-in: {e}")
        raise HTTPException(status_code=500, detail="Check-in failed")


# ============================================
# ACTIVITY FEED API
# ============================================

@router.get("/{ride_id}/activities")
async def get_activity_feed(
    ride_id: UUID,
    limit: int = 50,
    before: Optional[str] = None,  # ISO timestamp for pagination
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get activity feed for a ride.
    Returns latest activities, supports pagination.
    """
    try:
        # Verify ride exists
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Build query
        query = db.query(RideActivity).filter(RideActivity.ride_id == ride_id)

        # Pagination: get activities before a timestamp
        if before:
            try:
                before_dt = datetime.fromisoformat(before.replace('Z', '+00:00'))
                query = query.filter(RideActivity.created_at < before_dt)
            except ValueError:
                pass

        # Order by newest first and limit
        activities = query.order_by(desc(RideActivity.created_at)).limit(limit + 1).all()

        # Check if there are more
        has_more = len(activities) > limit
        if has_more:
            activities = activities[:limit]

        # Format response
        activities_data = [format_activity_response(a, db) for a in activities]

        return {
            "status": "success",
            "activities": activities_data,
            "total": len(activities_data),
            "has_more": has_more
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activities")


# ============================================
# LOCATION UPDATE API
# ============================================

@router.post("/{ride_id}/location")
async def update_location(
    ride_id: UUID,
    request: LocationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's current location during active ride.
    Called periodically (every minute) when ride is active.
    """
    try:
        # Verify ride is active
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        if ride.status != RideStatus.ACTIVE:
            return {
                "status": "ignored",
                "message": "Location updates only accepted for active rides"
            }

        # Verify user is participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id,
            RideParticipant.is_deleted == False
        ).first()

        if not participant:
            raise HTTPException(status_code=403, detail="You are not a participant")

        # Create location record
        location = UserLocation(
            ride_id=ride_id,
            user_id=current_user.id,
            latitude=request.latitude,
            longitude=request.longitude,
            heading=request.heading,
            speed=request.speed,
            accuracy=request.accuracy
        )
        db.add(location)
        db.commit()

        # Check if near any checkpoint for auto check-in
        checkpoints = db.query(RideCheckpoint).filter(
            RideCheckpoint.ride_id == ride_id
        ).all()

        nearest_cp, distance = find_nearest_checkpoint(
            request.latitude, request.longitude, checkpoints
        )

        auto_checkin = None
        if nearest_cp:
            radius = nearest_cp.radius_meters or CHECKPOINT_RADIUS_DEFAULT
            if distance <= radius:
                # Check if already checked in
                existing = db.query(AttendanceRecord).filter(
                    AttendanceRecord.ride_id == ride_id,
                    AttendanceRecord.user_id == current_user.id,
                    AttendanceRecord.checkpoint_type == nearest_cp.type
                ).first()

                if not existing:
                    auto_checkin = {
                        "type": nearest_cp.type.value,
                        "should_checkin": True,
                        "distance": int(distance)
                    }

        return {
            "status": "success",
            "message": "Location updated",
            "auto_checkin_available": auto_checkin
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error updating location: {e}")
        raise HTTPException(status_code=500, detail="Location update failed")


# ============================================
# ALERT/SOS API
# ============================================

@router.post("/{ride_id}/alert")
async def send_alert(
    ride_id: UUID,
    request: AlertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send an alert to all ride participants.
    Types: sos_alert, low_fuel, breakdown, need_help
    """
    try:
        # Verify ride
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        if ride.status != RideStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Alerts only available for active rides")

        # Verify participant
        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == current_user.id,
            RideParticipant.is_deleted == False
        ).first()

        if not participant:
            raise HTTPException(status_code=403, detail="You are not a participant")

        # Validate alert type
        valid_types = ['sos_alert', 'low_fuel', 'breakdown', 'need_help']
        if request.alert_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid alert type. Valid: {valid_types}")

        # Create message based on type
        alert_messages = {
            'sos_alert': f"🚨 SOS! {current_user.name or 'A rider'} needs immediate help!",
            'low_fuel': f"⛽ {current_user.name or 'A rider'} is running low on fuel",
            'breakdown': f"🔧 {current_user.name or 'A rider'} has a breakdown",
            'need_help': f"🆘 {current_user.name or 'A rider'} needs assistance"
        }
        message = request.message or alert_messages.get(request.alert_type, "Alert sent")

        # Create activity
        activity = create_activity(
            db=db,
            ride_id=ride_id,
            activity_type=request.alert_type,
            user_id=current_user.id,
            message=message,
            latitude=request.latitude,
            longitude=request.longitude
        )

        db.commit()

        logger.warning(f"ALERT: {request.alert_type} from user {current_user.id} in ride {ride_id}")

        # TODO: Send push notifications to all participants

        return {
            "status": "success",
            "message": "Alert sent to all riders",
            "activity": format_activity_response(activity, db)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error sending alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to send alert")


# ============================================
# LIVE RIDE DATA API (Combined endpoint)
# ============================================

@router.get("/{ride_id}/live")
async def get_live_ride_data(
    ride_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all live ride data in one call:
    - Recent activities
    - All rider locations
    - Checkpoints
    - Current user's attendance status
    """
    try:
        # Verify ride
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Get recent activities (last 20)
        activities = db.query(RideActivity).filter(
            RideActivity.ride_id == ride_id
        ).order_by(desc(RideActivity.created_at)).limit(20).all()

        activities_data = [format_activity_response(a, db) for a in activities]

        # Get latest location for each participant
        # Subquery for latest location per user
        latest_locations_subq = db.query(
            UserLocation.user_id,
            func.max(UserLocation.recorded_at).label('max_time')
        ).filter(
            UserLocation.ride_id == ride_id
        ).group_by(UserLocation.user_id).subquery()

        rider_locations_data = []
        
        # Get all participants
        participants = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.is_deleted == False
        ).all()

        for p in participants:
            # Get latest location
            latest_loc = db.query(UserLocation).filter(
                UserLocation.ride_id == ride_id,
                UserLocation.user_id == p.user_id
            ).order_by(desc(UserLocation.recorded_at)).first()

            # Get user info
            user = db.query(User).filter(User.id == p.user_id).first()

            # Get attendance status at meetup
            attendance = db.query(AttendanceRecord).filter(
                AttendanceRecord.ride_id == ride_id,
                AttendanceRecord.user_id == p.user_id,
                AttendanceRecord.checkpoint_type == CheckpointType.MEETUP
            ).first()

            if latest_loc:
                rider_locations_data.append({
                    "user_id": str(p.user_id),
                    "name": user.name if user else None,
                    "profile_picture": user.profile_picture_url if user else None,
                    "latitude": latest_loc.latitude,
                    "longitude": latest_loc.longitude,
                    "heading": latest_loc.heading,
                    "speed": latest_loc.speed,
                    "last_updated": latest_loc.recorded_at.isoformat(),
                    "attendance_status": attendance.status if attendance else None
                })

        # Get checkpoints
        checkpoints = db.query(RideCheckpoint).filter(
            RideCheckpoint.ride_id == ride_id
        ).all()

        checkpoints_data = [{
            "id": str(cp.id),
            "type": cp.type.value if hasattr(cp.type, 'value') else str(cp.type),
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            "radius_meters": cp.radius_meters,
            "address": cp.address
        } for cp in checkpoints]

        # Get current user's attendance at all checkpoints
        my_attendance = {}
        my_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride_id,
            AttendanceRecord.user_id == current_user.id
        ).all()
        for record in my_records:
            cp_type = record.checkpoint_type.value if hasattr(record.checkpoint_type, 'value') else str(record.checkpoint_type)
            my_attendance[cp_type] = {
                "status": record.status,
                "reached_at": record.reached_at.isoformat() if record.reached_at else None
            }

        return {
            "status": "success",
            "ride_status": ride.status.value if hasattr(ride.status, 'value') else str(ride.status),
            "activities": activities_data,
            "rider_locations": rider_locations_data,
            "checkpoints": checkpoints_data,
            "my_attendance": my_attendance,
            "participants_count": len(participants)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching live data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch live ride data")
