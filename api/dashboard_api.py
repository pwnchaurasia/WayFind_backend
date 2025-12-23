from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.db_conn import get_db
from db.models import User, Ride, AttendanceRecord, RideParticipant, OrganizationMember, Organization
from services.organization_service import OrganizationService
from utils import app_logger, RideStatus, UserRole, OrganizationRole
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

    # Route to different dashboards based on role
    if current_user.role == UserRole.SUPER_ADMIN:
        return super_admin_dashboard(request, current_user, db)

        # Check if user is org admin
    is_org_admin = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
        OrganizationMember.is_active == True,
        OrganizationMember.is_deleted == False
    ).first()

    if is_org_admin:
        return org_admin_dashboard(request, current_user, db)

    return rider_dashboard(request, current_user, db)


def super_admin_dashboard(request: Request, current_user, db: Session):
    """Super admin dashboard - see everything"""
    # Your existing code
    total_organizations = OrganizationService.get_organizations_count(db, is_active=True)
    total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    active_rides = db.query(func.count(Ride.id)).filter(Ride.status == RideStatus.ACTIVE).scalar() or 0
    completed_rides = db.query(func.count(Ride.id)).filter(Ride.status == RideStatus.COMPLETED).scalar() or 0
    total_distance = db.query(func.sum(AttendanceRecord.distance_traveled_km)).scalar() or 0

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
            "created_at": org.created_at.strftime("%Y-%m-%d")
        })

    return jinja_templates.TemplateResponse(
        "dashboards/dashboard.html",
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
        }
    )


def org_admin_dashboard(request: Request, current_user, db: Session):
    """Organization admin dashboard - see their org analytics"""

    # Get user's organizations
    user_orgs = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.is_active == True,
        OrganizationMember.is_deleted == False
    ).all()

    orgs_data = []
    total_rides = 0
    total_members = 0
    total_participants = 0
    active_rides = 0
    upcoming_rides = 0

    for membership in user_orgs:
        org = membership.organization

        # Get org stats
        org_members = db.query(func.count(OrganizationMember.id)).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).scalar() or 0

        org_rides = db.query(func.count(Ride.id)).filter(
            Ride.organization_id == org.id
        ).scalar() or 0

        org_active_rides = db.query(func.count(Ride.id)).filter(
            Ride.organization_id == org.id,
            Ride.status == RideStatus.ACTIVE
        ).scalar() or 0

        org_upcoming_rides = db.query(func.count(Ride.id)).filter(
            Ride.organization_id == org.id,
            Ride.status == RideStatus.PLANNED
        ).scalar() or 0

        # Get unique participants (not org members)
        org_participants = db.query(func.count(func.distinct(RideParticipant.user_id))).join(
            Ride
        ).filter(
            Ride.organization_id == org.id,
            ~RideParticipant.user_id.in_(
                db.query(OrganizationMember.user_id).filter(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.is_deleted == False
                )
            )
        ).scalar() or 0

        # New members this month
        from datetime import datetime, timedelta
        month_ago = datetime.now() - timedelta(days=30)
        new_members = db.query(func.count(OrganizationMember.id)).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.created_at >= month_ago,
            OrganizationMember.is_deleted == False
        ).scalar() or 0

        # Repeat riders (joined 2+ rides)
        repeat_riders = db.query(RideParticipant.user_id).join(
            Ride
        ).filter(
            Ride.organization_id == org.id
        ).group_by(
            RideParticipant.user_id
        ).having(
            func.count(RideParticipant.id) >= 2
        ).count()

        orgs_data.append({
            "id": str(org.id),
            "name": org.name,
            "description": org.description,
            "logo": org.logo,
            "role": membership.role.value,
            "members_count": org_members,
            "rides_count": org_rides,
            "active_rides": org_active_rides,
            "upcoming_rides": org_upcoming_rides,
            "participants_count": org_participants,
            "new_members_this_month": new_members,
            "repeat_riders": repeat_riders
        })

        total_rides += org_rides
        total_members += org_members
        total_participants += org_participants
        active_rides += org_active_rides
        upcoming_rides += org_upcoming_rides

    return jinja_templates.TemplateResponse(
        "dashboards/org_admin_dashboard.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "dashboard",
            "organizations": orgs_data,
            "total_rides": total_rides,
            "total_members": total_members,
            "total_participants": total_participants,
            "active_rides": active_rides,
            "upcoming_rides": upcoming_rides
        }
    )


def rider_dashboard(request: Request, current_user, db: Session):
    """Normal rider dashboard - see their personal stats"""

    # Total rides joined
    total_rides = db.query(func.count(RideParticipant.id)).filter(
        RideParticipant.user_id == current_user.id
    ).scalar() or 0

    # Completed rides
    completed_rides = db.query(func.count(RideParticipant.id)).join(
        Ride
    ).filter(
        RideParticipant.user_id == current_user.id,
        Ride.status == RideStatus.COMPLETED
    ).scalar() or 0

    # Upcoming rides
    upcoming_rides_query = db.query(Ride).join(
        RideParticipant
    ).filter(
        RideParticipant.user_id == current_user.id,
        Ride.status.in_([RideStatus.PLANNED])
    ).order_by(Ride.scheduled_date).limit(5).all()

    upcoming_rides = []
    for ride in upcoming_rides_query:
        org = db.query(Organization).filter(Organization.id == ride.organization_id).first()
        upcoming_rides.append({
            "id": str(ride.id),
            "name": ride.name,
            "organization_name": org.name if org else "Unknown",
            "organization_id": str(org.id) if org else None,
            "scheduled_date": ride.scheduled_date.strftime("%Y-%m-%d %H:%M") if ride.scheduled_date else "TBD",
            "status": ride.status.value,
            "requires_payment": ride.requires_payment,
            "amount": ride.amount
        })

    # Organizations/groups joined
    organizations = db.query(Organization).join(
        Ride
    ).join(
        RideParticipant
    ).filter(
        RideParticipant.user_id == current_user.id
    ).distinct().all()

    orgs_data = []
    for org in organizations:
        org_rides_count = db.query(func.count(RideParticipant.id)).join(
            Ride
        ).filter(
            RideParticipant.user_id == current_user.id,
            Ride.organization_id == org.id
        ).scalar() or 0

        orgs_data.append({
            "id": str(org.id),
            "name": org.name,
            "logo": org.logo,
            "rides_joined": org_rides_count
        })

    # Recent ride history
    recent_rides_query = db.query(Ride).join(
        RideParticipant
    ).filter(
        RideParticipant.user_id == current_user.id,
        Ride.status == RideStatus.COMPLETED
    ).order_by(Ride.ended_at.desc()).limit(5).all()

    recent_rides = []
    for ride in recent_rides_query:
        org = db.query(Organization).filter(Organization.id == ride.organization_id).first()

        # Check attendance
        attendance = db.query(AttendanceRecord).filter(
            AttendanceRecord.ride_id == ride.id,
            AttendanceRecord.user_id == current_user.id
        ).count()

        recent_rides.append({
            "id": str(ride.id),
            "name": ride.name,
            "organization_name": org.name if org else "Unknown",
            "organization_id": str(org.id) if org else None,
            "completed_date": ride.ended_at.strftime("%Y-%m-%d") if ride.ended_at else "N/A",
            "attendance": "Present" if attendance > 0 else "Absent"
        })

    # Payment pending
    payment_pending = db.query(func.count(RideParticipant.id)).join(
        Ride
    ).filter(
        RideParticipant.user_id == current_user.id,
        Ride.requires_payment == True,
        RideParticipant.has_paid == False,
        Ride.status != RideStatus.COMPLETED
    ).scalar() or 0

    return jinja_templates.TemplateResponse(
        "dashboards/rider_dashboard.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "dashboard",
            "total_rides": total_rides,
            "completed_rides": completed_rides,
            "upcoming_rides": upcoming_rides,
            "organizations": orgs_data,
            "recent_rides": recent_rides,
            "payment_pending": payment_pending,
            "groups_joined": len(orgs_data)
        }
    )