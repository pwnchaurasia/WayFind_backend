from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.db_conn import get_db
from db.models import User, OrganizationMember, Ride, RideParticipant
from utils.enums import UserRole, OrganizationRole
from utils.dependencies import get_current_user, get_current_user_web


class PermissionChecker:
    """Permission checking utility functions"""

    @staticmethod
    def is_super_admin(user: User) -> bool:
        return user.role == UserRole.SUPER_ADMIN

    @staticmethod
    def get_user_org_role(db: Session, org_id: UUID, user_id: UUID) -> Optional[OrganizationRole]:
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()
        return member.role if member else None

    @staticmethod
    def is_org_admin(db: Session, org_id: UUID, user: User) -> bool:
        if PermissionChecker.is_super_admin(user):
            return True
        role = PermissionChecker.get_user_org_role(db, org_id, user.id)
        return role in [OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]

    @staticmethod
    def is_org_founder(db: Session, org_id: UUID, user: User) -> bool:
        if PermissionChecker.is_super_admin(user):
            return True
        role = PermissionChecker.get_user_org_role(db, org_id, user.id)
        return role == OrganizationRole.FOUNDER

    @staticmethod
    def can_view_ride(db: Session, ride_id: UUID, user: User) -> bool:
        if PermissionChecker.is_super_admin(user):
            return True

        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return False

        if PermissionChecker.is_org_admin(db, ride.organization_id, user):
            return True

        participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride_id,
            RideParticipant.user_id == user.id
        ).first()

        return participant is not None

    @staticmethod
    def can_manage_ride(db: Session, ride_id: UUID, user: User) -> bool:
        if PermissionChecker.is_super_admin(user):
            return True

        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            return False

        return PermissionChecker.is_org_admin(db, ride.organization_id, user)


class PermissionDependency:
    """FastAPI dependencies for API routes (raises 403)"""

    @staticmethod
    def require_org_admin(org_id: UUID):
        def _check(
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)
        ) -> User:
            if not PermissionChecker.is_org_admin(db, org_id, current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization admins can perform this action"
                )
            return current_user

        return _check

    @staticmethod
    def require_org_founder(org_id: UUID):
        def _check(
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)
        ) -> User:
            if not PermissionChecker.is_org_founder(db, org_id, current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization founder can perform this action"
                )
            return current_user

        return _check

    @staticmethod
    def require_ride_manage(ride_id: UUID):
        def _check(
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)
        ) -> User:
            if not PermissionChecker.can_manage_ride(db, ride_id, current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization admins can manage rides"
                )
            return current_user

        return _check


class WebPermissionDependency:
    """FastAPI dependencies for Web routes (redirects)"""

    @staticmethod
    def require_org_admin_web(org_id: UUID):
        async def _check(
                request: Request,
                current_user=Depends(get_current_user_web),
                db: Session = Depends(get_db)
        ):
            if not current_user:
                return RedirectResponse(url=request.url_for('login_page'))

            if not PermissionChecker.is_org_admin(db, org_id, current_user):
                return RedirectResponse(url=request.url_for('dashboard_page'))

            return current_user

        return _check