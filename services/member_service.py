from typing import List, Optional, Tuple
from uuid import UUID
import secrets
import string
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from db.models import Organization, OrganizationMember, User
from db.schemas.organization import InviteMember, UpdateMemberRole
from services.organization_service import OrganizationService
from services.user_service import UserService
from utils.email_service import EmailService
from utils.enums import OrganizationRole, UserRole
from utils.app_logger import createLogger
from utils.app_helper import hash_password

logger = createLogger("member_service")


class MemberService:

    @staticmethod
    def generate_temporary_password(length: int = 12) -> str:
        """Generate a random temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def can_manage_member(
            manager_role: OrganizationRole,
            target_role: OrganizationRole
    ) -> bool:
        """Check if manager can manage target member"""
        role_hierarchy = {
            OrganizationRole.FOUNDER: 3,
            OrganizationRole.CO_FOUNDER: 2,
            OrganizationRole.ADMIN: 1
        }
        return role_hierarchy.get(manager_role, 0) > role_hierarchy.get(target_role, 0)

    @staticmethod
    def get_member_by_id(
            db: Session,
            member_id: UUID
    ) -> Optional[OrganizationMember]:
        """Get member by ID"""
        try:
            return db.query(OrganizationMember).filter(
                OrganizationMember.id == member_id,
                OrganizationMember.is_deleted == False
            ).first()
        except Exception as e:
            logger.exception(f"Error getting member: {e}")
            return None

    @staticmethod
    def get_organization_members(
            db: Session,
            org_id: UUID,
            is_active: Optional[bool] = None
    ) -> List[OrganizationMember]:
        """Get all members of an organization"""
        try:
            query = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_deleted == False
            )

            if is_active is not None:
                query = query.filter(OrganizationMember.is_active == is_active)

            return query.all()
        except Exception as e:
            logger.exception(f"Error getting organization members: {e}")
            return []

    @staticmethod
    def get_user_role_in_org(
            db: Session,
            org_id: UUID,
            user_id: UUID
    ) -> Optional[OrganizationRole]:
        """Get user's role in organization"""
        try:
            member = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_deleted == False,
                OrganizationMember.is_active == True
            ).first()

            return member.role if member else None
        except Exception as e:
            logger.exception(f"Error getting user role: {e}")
            return None

    @staticmethod
    def invite_member(
            db: Session,
            org_id: UUID,
            member_data: InviteMember,
            inviter_id: UUID
    ) -> Tuple[bool, Optional[OrganizationMember], Optional[str], Optional[str]]:
        """
        Invite member to organization
        Returns: (success, member, temporary_password, error)
        """
        try:
            # Check if organization exists
            org = OrganizationService.get_organization_by_id(db=db, org_id=org_id)
            if not org:
                return False, None, None, "Organization not found"

            # Get inviter user to check if super admin
            inviter = UserService.get_user_by_id(db=db, user_id=inviter_id)
            if not inviter:
                return False, None, None, "Inviter not found"

            is_super_admin = inviter.role == UserRole.SUPER_ADMIN

            # Check inviter's role in organization (skip if super admin)
            if not is_super_admin:
                inviter_role = MemberService.get_user_role_in_org(db, org_id, inviter_id)
                if not inviter_role:
                    return False, None, None, "You are not a member of this organization"

                # Check if inviter can add this role
                target_role = OrganizationRole(member_data.role)
                if not MemberService.can_manage_member(inviter_role, target_role):
                    return False, None, None, f"You cannot add {member_data.role} members"

            target_role = OrganizationRole(member_data.role)

            # Check if user already exists
            user = db.query(User).filter(
                (User.email == member_data.email) | (User.phone_number == member_data.phone_number)
            ).first()

            temp_password = None

            if user:
                # Check if already a member
                existing_member = db.query(OrganizationMember).filter(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.user_id == user.id
                ).first()

                if existing_member and not existing_member.is_deleted:
                    return False, None, None, "User is already a member"

                if existing_member and existing_member.is_deleted:
                    # Reactivate deleted member
                    existing_member.is_deleted = False
                    existing_member.is_active = True
                    existing_member.role = target_role
                    db.commit()
                    db.refresh(existing_member)
                    return True, existing_member, None, None
            else:
                # Create new user
                temp_password = MemberService.generate_temporary_password()

                user = User(
                    name=member_data.name,
                    email=member_data.email,
                    phone_number=member_data.phone_number,
                    hashed_password=hash_password(temp_password),
                    role=UserRole.NORMAL_USER,
                    is_active=False,  # Will be activated after first login
                    is_email_verified=False,
                    is_phone_verified=False
                )

                db.add(user)
                db.flush()  # Get user.id

            # Create organization member
            member = OrganizationMember(
                organization_id=org_id,
                user_id=user.id,
                role=target_role,
                is_active=False
            )

            db.add(member)
            db.commit()
            db.refresh(member)

            logger.info(f"Member invited: {member_data.email} to org {org_id} as {member_data.role}")

            if temp_password:
                is_sent, error = EmailService.send_invitation_email(
                    to_email=member_data.email,
                    user_name=member_data.name,
                    organization_name=org.name,
                    temp_password=temp_password,
                    role=member_data.role
                )

                if not is_sent:
                    logger.error(f"Failed to send invitation email: {error}")

            # Return temp password only if new user created
            return_password = temp_password if temp_password else None
            return True, member, return_password, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error inviting member: {e}")
            return False, None, None, str(e)

    @staticmethod
    def update_member_role(
            db: Session,
            org_id: UUID,
            member_id: UUID,
            new_role: str,
            updater_id: UUID
    ) -> Tuple[bool, Optional[OrganizationMember], Optional[str]]:
        """Update member's role"""
        try:
            # Get updater's role
            updater_role = MemberService.get_user_role_in_org(db, org_id, updater_id)
            if not updater_role:
                return False, None, "You are not authorized"

            # Get target member
            member = db.query(OrganizationMember).filter(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_deleted == False
            ).first()

            if not member:
                return False, None, "Member not found"

            # Check if updater can manage this member
            if not MemberService.can_manage_member(updater_role, member.role):
                return False, None, "You cannot manage this member"

            # Check if updater can assign new role
            target_role = OrganizationRole(new_role)
            if not MemberService.can_manage_member(updater_role, target_role):
                return False, None, f"You cannot assign {new_role} role"

            # Update role
            member.role = target_role
            db.commit()
            db.refresh(member)

            logger.info(f"Member role updated: {member_id} to {new_role}")
            return True, member, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error updating member role: {e}")
            return False, None, str(e)

    @staticmethod
    def toggle_member_status(
            db: Session,
            org_id: UUID,
            member_id: UUID,
            updater_id: UUID
    ) -> Tuple[bool, Optional[OrganizationMember], Optional[str]]:
        """Toggle member active status"""
        try:

            updater = UserService.get_user_by_id(db=db, user_id=updater_id)

            if not updater:
                return False, None, None, "Inviter not found"

            is_super_admin = updater.role == UserRole.SUPER_ADMIN
            updater_role = MemberService.get_user_role_in_org(db, org_id, updater_id)
            if not is_super_admin and not updater_role:
                return False, None, "You are not authorized"

            # Get target member
            member = db.query(OrganizationMember).filter(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_deleted == False
            ).first()

            if not member:
                return False, None, "Member not found"


            # Only founder can manage co-founders and other founders
            if not is_super_admin and not MemberService.can_manage_member(updater_role, member.role):
                return False, None, "You cannot manage this member"

            # Toggle status
            member.is_active = not member.is_active
            db.commit()
            db.refresh(member)

            logger.info(f"Member status toggled: {member_id} - Active: {member.is_active}")
            return True, member, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error toggling member status: {e}")
            return False, None, str(e)

    @staticmethod
    def remove_member(
            db: Session,
            org_id: UUID,
            member_id: UUID,
            remover_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Remove member from organization (soft delete)"""
        try:
            # Get remover's role
            remover_role = MemberService.get_user_role_in_org(db, org_id, remover_id)
            if not remover_role:
                return False, "You are not authorized"

            # Get target member
            member = db.query(OrganizationMember).filter(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == org_id,
            ).first()


            if not member:
                return False, "Member not found"


            # Only founder can remove co-founders and other founders
            if not MemberService.can_manage_member(remover_role, member.role):
                return False, "You cannot remove this member"

            if member.is_deleted:
                return True, "Member is already deleted"

            # Soft delete
            member.is_deleted = True
            member.is_active = False
            db.commit()

            logger.info(f"Member removed: {member_id} from org {org_id}")
            return True, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error removing member: {e}")
            return False, str(e)

    @staticmethod
    def get_members_count(db: Session, org_id: UUID) -> int:
        """Get active members count"""
        try:
            return db.query(func.count(OrganizationMember.id)).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active == True,
                OrganizationMember.is_deleted == False
            ).scalar() or 0
        except Exception as e:
            logger.exception(f"Error getting members count: {e}")
            return 0