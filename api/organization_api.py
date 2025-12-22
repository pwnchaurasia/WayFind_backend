from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from db.db_conn import get_db
from db.models import OrganizationMember, User
from db.schemas import OrganizationListResponse, UpdateOrganization
from db.schemas.organization import (
    CreateOrganization, AddOrganizationMember, OrganizationResponse,
    OrganizationMemberResponse
)
from services.organization_service import OrganizationService
from utils import app_logger, resp_msgs
from utils.dependencies import get_current_user, get_current_user_web
from utils.enums import OrganizationRole, UserRole
from utils.storage import storage

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
    """Get all organizations"""
    try:
        organizations = OrganizationService.get_all_organizations(db, skip, limit, is_active)

        orgs_with_count = []
        for org in organizations:
            members_count = OrganizationService.get_members_count(db, org.id)
            org_response = OrganizationListResponse.model_validate(org)
            org_dict = org_response.model_dump(mode='json')
            org_dict['members_count'] = members_count
            orgs_with_count.append(org_dict)

        return {
            "status": "success",
            "organizations": orgs_with_count,
            "total": OrganizationService.get_organizations_count(db, is_active)
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


@router.get("/{org_id}/members", response_model=dict)
async def get_organization_members(
        request: Request,
        org_id: UUID,
        is_active: Optional[bool] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get organization members"""
    try:
        members = OrganizationService.get_organization_members(db, org_id, is_active)

        return {
            "status": "success",
            "members": [
                OrganizationMemberResponse.model_validate(member).model_dump(mode='json')
                for member in members
            ]
        }

    except Exception as e:
        logger.exception(f"Error getting members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
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