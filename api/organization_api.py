import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, and_, distinct, case
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from starlette.responses import RedirectResponse

from db.db_conn import get_db
from db.models import OrganizationMember, User, RideParticipant, Organization, Ride, RideCheckpoint, AttendanceRecord
from db.schemas import OrganizationListResponse, UpdateOrganization
from db.schemas.organization import (
    CreateOrganization, AddOrganizationMember, OrganizationResponse,
    OrganizationMemberResponse
)
from services.member_service import MemberService
from services.organization_service import OrganizationService
from utils import app_logger, resp_msgs, RideStatus, CheckpointType
from utils.dependencies import get_current_user, get_current_user_web
from utils.enums import OrganizationRole, UserRole, RideType
from utils.permissions import PermissionChecker, PermissionDependency
from utils.storage import storage
from utils.templates import jinja_templates

router = APIRouter(prefix="/organizations", tags=["organizations"])
logger = app_logger.createLogger("app")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify")


def verify_super_admin(current_user: User = Depends(get_current_user)):
    """Verify user is super admin"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can access this resource"
        )
    return current_user


def verify_organization_admin(current_user: User = Depends(get_current_user)):
    """Verify user can manage organization"""
    if current_user.role != UserRole.SUPER_ADMIN:
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


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_organization(
        request: Request,
        org_data: CreateOrganization,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Create new organization (super admin only)"""
    try:
        is_created, organization, error = OrganizationService.create_organization(db, org_data)

        if not is_created:
            return {
                "status": "error",
                "message": error or "Failed to create organization"
            }

        members_count = OrganizationService.get_members_count(db, organization.id)
        org_response = OrganizationResponse.model_validate(organization)
        org_dict = org_response.model_dump(mode='json')
        org_dict['members_count'] = members_count

        return {
            "status": "success",
            "message": "Organization created successfully",
            "organization": org_dict
        }

    except Exception as e:
        logger.exception(f"Error creating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("", response_model=dict)
async def get_all_organizations(
        request: Request,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get organizations based on user role:
    - Super Admin: Can see ALL organizations
    - Normal User: Can only see organizations they are a member of
    
    This is a production security measure to prevent data leakage.
    """
    try:
        # Super Admin can see all organizations
        if current_user.role == UserRole.SUPER_ADMIN:
            organizations = OrganizationService.get_all_organizations(db, skip, limit, is_active)
        else:
            # Normal users can only see organizations they belong to
            user_org_memberships = db.query(OrganizationMember).filter(
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.is_active == True
            ).all()
            
            user_org_ids = [m.organization_id for m in user_org_memberships]
            
            if not user_org_ids:
                # User is not a member of any organization
                return {
                    "status": "success",
                    "organizations": [],
                    "total": 0
                }
            
            # Get only user's organizations
            query = db.query(Organization).filter(
                Organization.id.in_(user_org_ids)
            )
            
            if is_active is not None:
                query = query.filter(Organization.is_active == is_active)
            
            organizations = query.offset(skip).limit(limit).all()

        orgs_with_count = []
        for org in organizations:
            members_count = OrganizationService.get_members_count(db, org.id)
            org_response = OrganizationListResponse.model_validate(org)
            org_dict = org_response.model_dump(mode='json')
            org_dict['members_count'] = members_count
            
            # Add user's role in this org for frontend to determine UI
            if current_user.role != UserRole.SUPER_ADMIN:
                user_membership = db.query(OrganizationMember).filter(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.user_id == current_user.id,
                    OrganizationMember.is_active == True
                ).first()
                org_dict['user_role'] = user_membership.role.value if user_membership else None
            else:
                org_dict['user_role'] = 'super_admin'
            
            orgs_with_count.append(org_dict)

        total_count = len(orgs_with_count) if current_user.role != UserRole.SUPER_ADMIN else OrganizationService.get_organizations_count(db, is_active)

        return {
            "status": "success",
            "organizations": orgs_with_count,
            "total": total_count,
            "is_super_admin": current_user.role == UserRole.SUPER_ADMIN
        }

    except Exception as e:
        logger.exception(f"Error getting organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{org_id}", response_model=dict)
async def get_organization(
        request: Request,
        org_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get organization by ID"""
    try:
        organization = OrganizationService.get_organization_by_id(db, org_id)

        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        members_count = OrganizationService.get_members_count(db, org_id)
        org_response = OrganizationResponse.model_validate(organization)
        org_dict = org_response.model_dump(mode='json')
        org_dict['members_count'] = members_count

        return {
            "status": "success",
            "organization": org_dict
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.put("/{org_id}", response_model=dict)
async def update_organization(
        request: Request,
        org_id: UUID,
        org_data: UpdateOrganization,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Update organization (super admin only)"""
    try:
        is_updated, organization, error = OrganizationService.update_organization(db, org_id, org_data)

        if not is_updated:
            return {
                "status": "error",
                "message": error or "Failed to update organization"
            }

        members_count = OrganizationService.get_members_count(db, org_id)
        org_response = OrganizationResponse.model_validate(organization)
        org_dict = org_response.model_dump(mode='json')
        org_dict['members_count'] = members_count

        return {
            "status": "success",
            "message": "Organization updated successfully",
            "organization": org_dict
        }

    except Exception as e:
        logger.exception(f"Error updating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.patch("/{org_id}/toggle-status", response_model=dict)
async def toggle_organization_status(
        request: Request,
        org_id: UUID,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Toggle organization active status (super admin only)"""
    try:
        is_toggled, organization, error = OrganizationService.toggle_organization_status(db, org_id)

        if not is_toggled:
            return {
                "status": "error",
                "message": error or "Failed to toggle organization status"
            }

        return {
            "status": "success",
            "message": f"Organization {'activated' if organization.is_active else 'deactivated'} successfully",
            "is_active": organization.is_active
        }

    except Exception as e:
        logger.exception(f"Error toggling organization status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.delete("/{org_id}", response_model=dict)
async def delete_organization(
        request: Request,
        org_id: UUID,
        hard_delete: bool = False,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Delete organization (super admin only)"""
    try:
        if hard_delete:
            is_deleted, error = OrganizationService.hard_delete_organization(db, org_id)
        else:
            is_deleted, error = OrganizationService.delete_organization(db, org_id)

        if not is_deleted:
            return {
                "status": "error",
                "message": error or "Failed to delete organization"
            }

        return {
            "status": "success",
            "message": "Organization deleted successfully"
        }

    except Exception as e:
        logger.exception(f"Error deleting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


# Member Management Endpoints

@router.post("/{org_id}/members", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_member_to_organization(
        request: Request,
        org_id: UUID,
        member_data: AddOrganizationMember,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Add member to organization (super admin only)"""
    try:
        is_added, member, error = OrganizationService.add_member_to_organization(db, org_id, member_data)

        if not is_added:
            return {
                "status": "error",
                "message": error or "Failed to add member"
            }

        return {
            "status": "success",
            "message": "Member added successfully",
            "member": OrganizationMemberResponse.model_validate(member).model_dump(mode='json')
        }

    except Exception as e:
        logger.exception(f"Error adding member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{org_id}/members", name='get_organization_members')
async def get_organization_members(
        request: Request,
        org_id: UUID,
        db: Session = Depends(get_db)
):
    """Get organization members with user details - supports both web and mobile"""
    try:
        # Check if this is an API request (has Authorization header) or web request (has cookies)
        auth_header = request.headers.get("authorization", "")
        accept_header = request.headers.get("accept", "")
        
        # If Authorization header is present, treat as API/mobile request
        is_api_request = bool(auth_header and auth_header.startswith("Bearer "))
        
        logger.info(f"Members API - Auth header present: {bool(auth_header)}, Accept: {accept_header[:50]}, is_api: {is_api_request}")
        
        # Get current user based on request type
        if is_api_request:
            # Mobile/API request - get token from Authorization header
            from utils.app_helper import verify_user_from_token
            
            token = auth_header.replace("Bearer ", "")
            
            if not token:
                return {"status": "error", "message": "Authentication required"}
            
            is_verified, msg, current_user = verify_user_from_token(token, db)
            if not is_verified or not current_user:
                return {"status": "error", "message": msg or "Authentication required"}
        else:
            # Web request - get token from cookie
            access_token = request.cookies.get("access_token")
            if not access_token:
                return RedirectResponse(url=request.url_for('login_page'))
            
            from utils.app_helper import verify_user_from_token
            is_verified, msg, current_user = verify_user_from_token(access_token, db)
            if not is_verified or not current_user:
                return RedirectResponse(url=request.url_for('login_page'))
        
        members = OrganizationService.get_organization_members(db, org_id, is_active)
        
        # Check if current user is org admin (to show sensitive data like phone)
        user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)
        is_admin = user_role in [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN] if user_role else False
        is_super_admin = current_user.role == UserRole.SUPER_ADMIN
        can_see_sensitive = is_admin or is_super_admin

        members_data = []
        for member in members:
            # Get user details
            user = db.query(User).filter(User.id == member.user_id).first()
            
            member_dict = {
                "id": str(member.id),
                "organization_id": str(member.organization_id),
                "user_id": str(member.user_id),
                "role": member.role.value if hasattr(member.role, 'value') else member.role,
                "is_active": member.is_active,
                "created_at": member.created_at.isoformat() if member.created_at else None,
                "updated_at": member.updated_at.isoformat() if member.updated_at else None,
                # User details
                "name": user.name if user else None,
                "email": user.email if user else None,
                "profile_picture": user.profile_picture if user else None,
            }
            
            # Only include sensitive info for admins
            if can_see_sensitive:
                member_dict["phone_number"] = user.phone_number if user else None
            
            members_data.append(member_dict)
        
        # Sort alphabetically by name, then by role priority
        role_priority = {"founder": 0, "co_founder": 1, "admin": 2}
        members_data.sort(key=lambda m: (role_priority.get(m.get("role"), 99), m.get("name", "").lower()))

        return {
            "status": "success",
            "members": members_data,
            "is_admin": can_see_sensitive
        }

    except Exception as e:
        logger.exception(f"Error getting members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{org_id}/all-people", name='organization_all_people_page')
async def organization_all_people_page(
        request: Request,
        org_id: UUID,
        current_user: User = Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """
    Show ALL people page (HTML)
    Access: Only org admins
    """
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # PermissionDependency.require_org_admin(org_id)

    # Get organization
    organization = db.query(Organization).filter(Organization.id == org_id).first()

    # Get all people
    result = OrganizationService.get_all_organization_people(db, org_id)


    user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

    return jinja_templates.TemplateResponse(
        "organization/organization_all_people.html",  # New template
        {
            "request": request,
            "user": current_user,
            "active_page": "organizations",
            "organization": {
                "id": str(organization.id),
                "name": organization.name
            },
            "org_members": result["org_members"],
            "ride_participants": result["ride_participants"],
            "total_count": result["total_count"],
            "user_role": user_role.value if user_role else None
        }
    )


@router.put("/{org_id}/members/{user_id}/role", response_model=dict)
async def update_member_role(
        request: Request,
        org_id: UUID,
        user_id: UUID,
        new_role: str,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Update member role (super admin only)"""
    try:
        is_updated, member, error = OrganizationService.update_member_role(db, org_id, user_id, new_role)

        if not is_updated:
            return {
                "status": "error",
                "message": error or "Failed to update member role"
            }

        return {
            "status": "success",
            "message": "Member role updated successfully",
            "member": OrganizationMemberResponse.model_validate(member).model_dump(mode='json')
        }

    except Exception as e:
        logger.exception(f"Error updating member role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.delete("/{org_id}/members/{user_id}", response_model=dict)
async def remove_member_from_organization(
        request: Request,
        org_id: UUID,
        user_id: UUID,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Remove member from organization (super admin only)"""
    try:
        is_removed, error = OrganizationService.remove_member_from_organization(db, org_id, user_id)

        if not is_removed:
            return {
                "status": "error",
                "message": error or "Failed to remove member"
            }

        return {
            "status": "success",
            "message": "Member removed successfully"
        }

    except Exception as e:
        logger.exception(f"Error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/create", name="create_organization_web")
async def create_organization_web(
        request: Request,
        name: str = Form(...),
        description: str = Form(None),
        logo: UploadFile = File(None),
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Create organization from web form"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # Check if user is super admin
    from utils.enums import UserRole
    if current_user.role != UserRole.SUPER_ADMIN:
        return RedirectResponse(
            url=request.url_for('dashboard_page'),
            status_code=303
        )

    try:
        logo_url = None

        # Upload logo if provided
        if logo and logo.filename:
            is_uploaded, logo_url, error = await storage.upload_logo(logo)
            if not is_uploaded:
                logger.error(f"Logo upload failed: {error}")

        org_data = CreateOrganization(
            name=name,
            description=description,
            logo=logo_url
        )
        is_created, organization, error = OrganizationService.create_organization(db, org_data)

        if not is_created:
            logger.error(f"Failed to create organization: {error}")

        return RedirectResponse(
            url=request.url_for('dashboard_page'),
            status_code=303
        )

    except Exception as e:
        logger.exception(f"Error creating organization: {e}")
        return RedirectResponse(
            url=request.url_for('dashboard_page'),
            status_code=303
        )


@router.post("/organizations/{org_id}/toggle", name="toggle_organization_web")
async def toggle_organization_web(
        request: Request,
        org_id: str,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Toggle organization status"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    from utils.enums import UserRole
    from uuid import UUID

    if current_user.role != UserRole.SUPER_ADMIN:
        return RedirectResponse(url=request.url_for('dashboard_page'), status_code=303)

    try:
        OrganizationService.toggle_organization_status(db, UUID(org_id))
    except Exception as e:
        logger.exception(f"Error toggling organization: {e}")

    return RedirectResponse(url=request.url_for('dashboard_page'), status_code=303)


@router.post("/organizations/{org_id}/delete", name="delete_organization_web")
async def delete_organization_web(
        request: Request,
        org_id: str,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Delete organization"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    from utils.enums import UserRole
    from uuid import UUID

    if current_user.role != UserRole.SUPER_ADMIN:
        return RedirectResponse(url=request.url_for('dashboard_page'), status_code=303)

    try:
        OrganizationService.delete_organization(db, UUID(org_id))
    except Exception as e:
        logger.exception(f"Error deleting organization: {e}")

    return RedirectResponse(url=request.url_for('dashboard_page'), status_code=303)


@router.get("/{org_id}/detail", name="organization_detail_page")
async def organization_detail_page(
        request: Request,
        org_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Organization detail page with members and analytics"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # Get organization
    organization = OrganizationService.get_organization_by_id(db, org_id)
    if not organization:
        return RedirectResponse(url=request.url_for('dashboard_page'))

    # Get current user's role in org (if member)
    user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

    # Get all members
    members = MemberService.get_organization_members(db, org_id)
    members_data = []

    for member in members:
        user = member.user
        members_data.append({
            "id": str(member.id),
            "user_id": str(member.user_id),
            "name": user.name or "No Name",
            "email": user.email or "N/A",
            "phone": user.phone_number or "N/A",
            "role": member.role.value,
            "is_active": member.is_active,
            "created_at": member.created_at.strftime("%Y-%m-%d")
        })

    org_member_user_ids = [m['user_id'] for m in members_data]

    ride_participants_query = (
        db.query(
            User.id.label('user_id'),
            User.name,
            User.phone_number,
            User.email,
            func.count(distinct(RideParticipant.ride_id)).label('total_rides_registered'),  # All rides (any status)
            func.count(distinct(
                case(
                    (Ride.status == RideStatus.COMPLETED, RideParticipant.ride_id),
                    else_=None
                )
            )).label('total_completed_rides'),  # Only COMPLETED rides
            func.count(distinct(
                case(
                    (
                        and_(
                            Ride.status == RideStatus.COMPLETED,
                            AttendanceRecord.status == 'present'
                        ),
                        AttendanceRecord.ride_id
                    ),
                    else_=None
                )
            )).label('total_rides_attended')  # Only COMPLETED + marked present
        )
        .join(RideParticipant, User.id == RideParticipant.user_id)
        .join(Ride, RideParticipant.ride_id == Ride.id)
        .outerjoin(
            AttendanceRecord,
            and_(
                AttendanceRecord.user_id == User.id,
                AttendanceRecord.ride_id == Ride.id,
                AttendanceRecord.checkpoint_type == 'meetup'
            )
        )
        .filter(
            Ride.organization_id == org_id,
            ~User.id.in_(org_member_user_ids)  # Exclude org members
        )
        .group_by(User.id, User.name, User.phone_number, User.email)
        .all()
    )

    # Format ride participants data
    ride_participants_data = []
    for p in ride_participants_query:
        attendance_rate = 0
        if p.total_completed_rides > 0:  # Only calculate if there are COMPLETED rides
            attendance_rate = round((p.total_rides_attended / p.total_completed_rides) * 100, 1)

        ride_participants_data.append({
            "user_id": str(p.user_id),
            "name": p.name or "No Name",
            "phone": p.phone_number or "N/A",
            "email": p.email or "N/A",
            "total_rides_registered": p.total_rides_registered,  # All rides (PLANNED + ACTIVE + COMPLETED)
            "total_completed_rides": p.total_completed_rides,  # Only COMPLETED
            "total_rides_attended": p.total_rides_attended,  # Only COMPLETED + present
            "attendance_rate": attendance_rate,  # (attended / completed) * 100
        })


    # Get stats
    active_rides = db.query(func.count(Ride.id)).filter(
        Ride.organization_id == org_id,
        Ride.status == RideStatus.ACTIVE
    ).scalar() or 0

    completed_rides = db.query(func.count(Ride.id)).filter(
        Ride.organization_id == org_id,
        Ride.status == RideStatus.COMPLETED
    ).scalar() or 0

    total_rides = db.query(func.count(Ride.id)).filter(
        Ride.organization_id == org_id
    ).scalar() or 0

    return jinja_templates.TemplateResponse(
        "organization/organization_detail.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "dashboard",
            "organization": {
                "id": str(organization.id),
                "name": organization.name,
                "description": organization.description or "No description",
                "logo": organization.logo,
                "is_active": organization.is_active,
                "created_at": organization.created_at.strftime("%Y-%m-%d")
            },
            "members": members_data,
            "members_count": len(members_data),
            "ride_participants": ride_participants_data,  # NEW
            "ride_participants_count": len(ride_participants_data),  # NEW
            "active_rides": active_rides,
            "total_rides": total_rides,
            "completed_rides": completed_rides,
            "user_role": user_role.value if user_role else None
        }
    )


@router.get("/{org_id}/rides/{ride_id}", name="org_ride_detail_page")
async def org_ride_detail_page(
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
    target_checkpoint = 'meetup'
    # Get participants
    participants = (
        db.query(RideParticipant)
        .options(
            joinedload(RideParticipant.user),  # Fetches User details
            joinedload(RideParticipant.vehicle_info),  # Fetches Vehicle details
        ).outerjoin(
            AttendanceRecord,
            and_(
                RideParticipant.user_id == AttendanceRecord.user_id,
                RideParticipant.ride_id == AttendanceRecord.ride_id,
                AttendanceRecord.checkpoint_type == target_checkpoint
            )
        ).options(
            contains_eager(RideParticipant.attendance_records)
        ).filter(
            RideParticipant.ride_id == ride_id
        ).order_by(RideParticipant.role)
        .all()
    )

    checkpoints = db.query(RideCheckpoint).filter(RideCheckpoint.ride_id == ride_id).all()

    checkpoint_data = {
        'meetup': None,
        'destination': None,
        'disbursement': None,
        'refreshments': []
    }

    for cp in checkpoints:
        cp_dict = {
            'id': str(cp.id),
            'type': cp.type.value,
            'latitude': cp.latitude,
            'longitude': cp.longitude,
            'address': cp.address,
            'google_maps_url': f"https://www.google.com/maps?q={cp.latitude},{cp.longitude}"
        }

        if cp.type == CheckpointType.MEETUP:
            checkpoint_data['meetup'] = cp_dict
        elif cp.type == CheckpointType.DESTINATION:
            checkpoint_data['destination'] = cp_dict
        elif cp.type == CheckpointType.DISBURSEMENT:
            checkpoint_data['disbursement'] = cp_dict
        elif cp.type == CheckpointType.REFRESHMENT:
            checkpoint_data['refreshments'].append(cp_dict)

    participants_data = []
    for p in participants:
        user = p.user
        participants_data.append({
            "id": str(p.id),
            "user_id": str(p.user_id),
            "user_name": user.name if user else "Unknown",
            "user_phone": user.phone_number if user else "N/A",
            "role": p.role.value,
            "has_paid": p.has_paid,
            "paid_amount": p.paid_amount,
            "vehicle_info": f"{p.vehicle_info.make} // {p.vehicle_info.model}" if p.vehicle_info else None,
            "payment_date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "registered_at": p.registered_at.strftime("%Y-%m-%d"),
            "attendance_records": p.attendance_records
        })

    # Get user role
    user_role = MemberService.get_user_role_in_org(db, org_id, current_user.id)

    # Generate share link
    share_link = f"{request.url_for('join_ride_page', ride_id=str(ride_id))}"

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
                "share_link": share_link,
                "checkpoints": checkpoint_data,
                "has_checkpoints": len(checkpoints) > 0,
            },
            "participants": participants_data,
            "user_role": user_role.value if user_role else None
        }
    )


@router.get("/{org_id}/rides", name="organization_rides_page")
async def organization_rides_page(
        request: Request,
        org_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Organization rides page - supports both HTML (web) and JSON (mobile)
    Uses Authorization header to detect API requests
    """
    # Check if this is an API request (has Authorization header) or web request
    auth_header = request.headers.get("authorization", "")
    accept_header = request.headers.get("accept", "")
    
    # If Authorization header is present, treat as API/mobile request
    is_api_request = bool(auth_header and auth_header.startswith("Bearer "))
    
    logger.info(f"Rides API - Auth header present: {bool(auth_header)}, Accept: {accept_header[:50]}, is_api: {is_api_request}")

    # For API requests, verify token from Authorization header
    if is_api_request:
        from utils.app_helper import verify_user_from_token
        
        token = auth_header.replace("Bearer ", "")
        
        if not token:
            return {"status": "error", "message": "Authentication required"}
        
        is_verified, msg, current_user = verify_user_from_token(token, db)
        if not is_verified or not current_user:
            return {"status": "error", "message": msg or "Authentication required"}
    else:
        # Web request - get token from cookie
        access_token = request.cookies.get("access_token")
        if not access_token:
            return RedirectResponse(url=request.url_for('login_page'))
        
        from utils.app_helper import verify_user_from_token
        is_verified, msg, current_user = verify_user_from_token(access_token, db)
        if not is_verified or not current_user:
            return RedirectResponse(url=request.url_for('login_page'))

    # Get organization
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        if is_api_request:
            return {"status": "error", "message": "Organization not found"}
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
    all_rides = []

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
            "ride_type": ride.ride_type.value if ride.ride_type else None,
            "scheduled_date": ride.scheduled_date.strftime("%Y-%m-%d") if ride.scheduled_date else None,
            "created_at": ride.created_at.strftime("%Y-%m-%d"),
            "started_at": ride.started_at.strftime("%Y-%m-%d %H:%M") if ride.started_at else None
        }

        all_rides.append(ride_data)

        if ride.status == RideStatus.PLANNED:
            upcoming_rides.append(ride_data)
        elif ride.status == RideStatus.ACTIVE:
            active_rides.append(ride_data)
        else:
            past_rides.append(ride_data)

    # Return JSON for mobile
    if is_api_request:
        return {
            "status": "success",
            "rides": all_rides,
            "upcoming_rides": upcoming_rides,
            "active_rides": active_rides,
            "past_rides": past_rides,
            "organization": {
                "id": str(organization.id),
                "name": organization.name
            },
            "user_role": user_role.value if user_role else None
        }

    # Return HTML for web
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
            "user_role": user_role.value if user_role else None,
            "ride_types": [e.value for e in RideType],
        }
    )



@router.get("/{org_id}/rides/{ride_id}/checkpoints/add", name="add_checkpoints_page")
async def add_checkpoints_page(
        request: Request,
        org_id: UUID,
        ride_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Add checkpoints page"""
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    organization = db.query(Organization).filter(Organization.id == org_id).first()

    google_maps_key = os.getenv("GOOGLE_MAP_API_KEY")


    return jinja_templates.TemplateResponse(
        "ride/add_checkpoints.html",
        {
            "request": request,
            "user": current_user,
            "organization": {"id": str(org_id), "name": organization.name},
            "ride": {"id": str(ride_id), "name": ride.name},
            "google_maps_key": google_maps_key
        }
    )
