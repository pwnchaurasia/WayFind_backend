from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db
from db.models import Organization, OrganizationMember, User
from db.schemas import (
    CreateOrganization, AddOrganizationMember, OrganizationResponse, 
    OrganizationMemberResponse
)
from services.user_service import UserService
from utils import app_logger, resp_msgs
from utils.app_helper import verify_user_from_token
from utils.enums import OrganizationRole, UserRole
from utils.dependencies import get_current_user


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


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_organization(
        request: Request,
        org_data: CreateOrganization,
        current_user: User = Depends(verify_super_admin),
        db: Session = Depends(get_db)
):
    """Create new organization (super admin only)"""
    try:
        organization = db.query(Organization).filter(
            Organization.name == org_data.name
        ).first()

        if organization:
            logger.info(f"Organization already exists: {organization.name}")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Organization already exists",
                    "organization": OrganizationResponse.model_validate(organization).model_dump(mode='json')
                },
                status_code=status.HTTP_200_OK
            )
        organization = Organization(
            name=org_data.name,
            description=org_data.description
        )
        db.add(organization)
        db.commit()
        db.refresh(organization)
        
        logger.info(f"Organization created: {organization.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Organization created.",
                "organization": OrganizationResponse.model_validate(organization).model_dump(mode='json')
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error creating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/", status_code=status.HTTP_200_OK)
async def list_organizations(
    current_user: User = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """List all organizations (super admin only)"""
    try:
        organizations = db.query(Organization).all()
        
        return JSONResponse(
            content={
                "status": "success",
                "organizations": [OrganizationResponse.model_validate(org).model_dump(mode='json') for org in organizations]
            }
        )
    except Exception as e:
        logger.exception(f"Error listing organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{organization_id}", status_code=status.HTTP_200_OK)
async def get_organization(
    organization_id: str,
    current_user: User = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        return JSONResponse(
            content={
                "status": "success",
                "organization": OrganizationResponse.model_validate(organization).model_dump(mode='json')
            }
        )
    except Exception as e:
        logger.exception(f"Error getting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.put("/{organization_id}", status_code=status.HTTP_200_OK)
async def update_organization(
    organization_id: str,
    request: CreateOrganization,
    current_user: User = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """Update organization (super admin only)"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        organization.name = request.name
        organization.description = request.description
        db.commit()
        db.refresh(organization)
        
        logger.info(f"Organization updated: {organization.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "organization": OrganizationResponse.from_orm(organization)}
        )
    except Exception as e:
        logger.exception(f"Error updating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.delete("/{organization_id}", status_code=status.HTTP_200_OK)
async def delete_organization(
    organization_id: str,
    current_user: User = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """Delete organization (super admin only)"""
    try:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        db.delete(organization)
        db.commit()
        
        logger.info(f"Organization deleted: {organization.name} by user: {current_user.id}")
        
        return JSONResponse(
            content={"status": "success", "message": "Organization deleted successfully"}
        )
    except Exception as e:
        logger.exception(f"Error deleting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.post("/{organization_id}/members", status_code=status.HTTP_201_CREATED)
async def add_organization_member(
    organization_id: str,
    request: AddOrganizationMember,
    current_user: User = Depends(verify_super_admin),
    db: Session = Depends(get_db)
):
    """Add member to organization (super admin only)"""
    try:
        # Verify organization exists
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Verify user exists
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user is already a member
        existing_member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == request.user_id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization"
            )
        
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=request.user_id,
            role=request.role
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        
        logger.info(f"Member added to organization: {organization.name} - user: {user.id}, role: {request.role}")
        
        return JSONResponse(
            content={
                "status": "success", 
                "member": OrganizationMemberResponse.from_orm(member)
            },
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(f"Error adding organization member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.get("/{organization_id}/members", status_code=status.HTTP_200_OK)
async def list_organization_members(
    organization_id: str,
    current_user: User = Depends(verify_user_from_token),
    db: Session = Depends(get_db)
):
    """List organization members"""
    try:
        # Verify organization exists and user has access
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        members = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active == True
        ).all()
        
        member_responses = []
        for member in members:
            member_response = OrganizationMemberResponse.from_orm(member)
            # Populate user info
            user = db.query(User).filter(User.id == member.user_id).first()
            if user:
                member_response.user = UserResponse.from_orm(user)
            member_responses.append(member_response)
        
        return JSONResponse(
            content={
                "status": "success",
                "members": member_responses
            }
        )
    except Exception as e:
        logger.exception(f"Error listing organization members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.put("/{organization_id}/members/{member_id}", status_code=status.HTTP_200_OK)
async def update_organization_member(
    organization_id: str,
    member_id: str,
    request: AddOrganizationMember,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Update organization member role (founder/co-founder only)"""
    try:
        # Verify organization exists
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Get member to update
        member = db.query(OrganizationMember).filter(OrganizationMember.id == member_id).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        # Verify current user is founder/co-founder of this organization
        current_user_member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER]),
            OrganizationMember.is_active == True
        ).first()
        
        if not current_user_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only founders and co-founders can update member roles"
            )
        
        # Only allow role updates, not user_id changes
        member.role = request.role
        db.commit()
        db.refresh(member)
        
        logger.info(f"Organization member role updated: {member.user_id} - new role: {request.role}")
        
        return JSONResponse(
            content={"status": "success", "member": OrganizationMemberResponse.from_orm(member)}
        )
    except Exception as e:
        logger.exception(f"Error updating organization member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )


@router.delete("/{organization_id}/members/{member_id}", status_code=status.HTTP_200_OK)
async def remove_organization_member(
    organization_id: str,
    member_id: str,
    current_user: User = Depends(verify_organization_admin),
    db: Session = Depends(get_db)
):
    """Remove member from organization"""
    try:
        # Verify organization exists
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Get member to remove
        member = db.query(OrganizationMember).filter(OrganizationMember.id == member_id).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        db.delete(member)
        db.commit()
        
        logger.info(f"Organization member removed: {member.user_id} from org: {organization_id}")
        
        return JSONResponse(
            content={"status": "success", "message": "Member removed successfully"}
        )
    except Exception as e:
        logger.exception(f"Error removing organization member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=resp_msgs.STATUS_500_MSG
        )
