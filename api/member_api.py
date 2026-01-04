from uuid import UUID

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from db.models import User, OrganizationMember
from db.schemas.organization import InviteMember, UpdateMemberRole
from sqlalchemy.orm import Session
from utils.dependencies import get_current_user_web

from db.db_conn import get_db
from services.member_service import MemberService
from services.organization_service import OrganizationService
from utils.app_logger import createLogger
from utils.templates import jinja_templates

logger = createLogger("member_routes")
router = APIRouter(prefix="/organizations", tags=["members"])


@router.get("/{org_id}/members/manage", name="organization_members_page_manage")
async def organization_members_page(
        request: Request,
        org_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Organization members management page"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    # Get organization
    organization = OrganizationService.get_organization_by_id(db, org_id)
    if not organization:
        return RedirectResponse(url=request.url_for('dashboard_page'))

    # Get current user's role in org
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

    return jinja_templates.TemplateResponse(
        "organization_members.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "organizations",
            "organization": {
                "id": str(organization.id),
                "name": organization.name,
                "description": organization.description
            },
            "members": members_data,
            "user_role": user_role.value if user_role else None
        }
    )


@router.post("/{org_id}/members/invite", name="invite_member_web")
async def invite_member_web(
        request: Request,
        org_id: UUID,
        name: str = Form(...),
        email: str = Form(...),
        phone_number: str = Form(...),
        role: str = Form(...),
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Invite member to organization"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        member_data = InviteMember(
            name=name,
            email=email,
            phone_number=phone_number,
            role=role
        )

        is_invited, member, temp_password, error = MemberService.invite_member(
            db, org_id, member_data, current_user.id
        )

        if not is_invited:
            logger.error(f"Failed to invite member: {error}")
        else:
            # TODO: Send email with temporary password
            if temp_password:
                logger.info(f"Temporary password for {email}: {temp_password}")
                # In production, send this via email

        return RedirectResponse(
            url=request.url_for('organization_detail_page', org_id=str(org_id)),
            status_code=303
        )

    except Exception as e:
        logger.exception(f"Error inviting member: {e}")
        return RedirectResponse(
            url=request.url_for('organization_detail_page', org_id=str(org_id)),
            status_code=303
        )


@router.post("/{org_id}/members/{member_id}/toggle", name="toggle_member_web")
async def toggle_member_web(
        request: Request,
        org_id: UUID,
        member_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Toggle member status"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        MemberService.toggle_member_status(db, org_id, member_id, current_user.id)
    except Exception as e:
        logger.exception(f"Error toggling member: {e}")

    return RedirectResponse(
        url=request.url_for('organization_detail_page', org_id=str(org_id)),
        status_code=303
    )


@router.post("/{org_id}/members/{member_id}/remove", name="remove_member_web")
async def remove_member_web(
        request: Request,
        org_id: UUID,
        member_id: UUID,
        current_user=Depends(get_current_user_web),
        db: Session = Depends(get_db)
):
    """Remove member from organization"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    try:
        MemberService.remove_member(db, org_id, member_id, current_user.id)
    except Exception as e:
        logger.exception(f"Error removing member: {e}")

    return RedirectResponse(
        url=request.url_for('organization_members_page_manage', org_id=str(org_id)),
        status_code=303
    )