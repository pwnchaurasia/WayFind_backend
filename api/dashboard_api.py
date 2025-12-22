from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.db_conn import get_db
from db.models import User, Ride, AttendanceRecord, RideParticipant
from services.organization_service import OrganizationService
from utils import app_logger, RideStatus
from utils.dependencies import get_current_user_web
from utils.templates import jinja_templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = app_logger.createLogger("app")

@router.get("/", name="dashboard_page")
async def dashboard(
        request: Request,
        current_user = Depends(get_current_user_web),
        db: Session = Depends(get_db),
):
    """Render dashboard page"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # Get analytics data
    total_organizations = OrganizationService.get_organizations_count(db, is_active=True)
    total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    active_rides = db.query(func.count(Ride.id)).filter(Ride.status == RideStatus.ACTIVE).scalar() or 0

    completed_rides = db.query(func.count(Ride.id)).filter(Ride.status == RideStatus.COMPLETED).scalar() or 0
    total_distance = db.query(func.sum(AttendanceRecord.distance_traveled_km)).scalar() or 0

    avg_riders = db.query(func.avg(
        db.query(func.count(RideParticipant.id))
        .filter(RideParticipant.ride_id == Ride.id)
        .correlate(Ride)
        .scalar_subquery()
    )).scalar() or 0

    # Get all organizations with member counts
    organizations = OrganizationService.get_all_organizations(db, limit=100, is_active=None)
    orgs_data = []
    for org in organizations:
        members_count = OrganizationService.get_members_count(db, org.id)
        orgs_data.append({
            "id": str(org.id),
            "name": org.name,
            "description": org.description or "No description",
            "members_count": members_count,
            "is_active": org.is_active,
            "is_deleted": org.is_deleted,
            "created_at": org.created_at.strftime("%Y-%m-%d")
        })

    return jinja_templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "dashboard",
            "total_organizations": total_organizations,
            "total_users": total_users,
            "active_rides": active_rides,
            "organizations": orgs_data,
            "total_completed_rides": completed_rides,
            "total_distance_km": round(total_distance, 2),
            "avg_riders_per_ride": round(avg_riders, 1)
        }
    )
