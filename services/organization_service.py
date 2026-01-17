from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, literal
from db.models import Organization, OrganizationMember, User, RideParticipant, Ride
from db.schemas.organization import CreateOrganization, UpdateOrganization, AddOrganizationMember
from utils.enums import OrganizationRole
from utils.app_logger import createLogger

logger = createLogger("organization_service")


class OrganizationService:

    @staticmethod
    def get_organization_by_id(db: Session, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID"""
        try:
            return db.query(Organization).filter(Organization.id == org_id).first()
        except Exception as e:
            logger.exception(f"Error getting organization by id: {e}")
            return None

    @staticmethod
    def get_organization_by_name(db: Session, name: str) -> Optional[Organization]:
        """Get organization by name"""
        try:
            return db.query(Organization).filter(Organization.name == name).first()
        except Exception as e:
            logger.exception(f"Error getting organization by name: {e}")
            return None

    @staticmethod
    def get_all_organizations(
            db: Session,
            skip: int = 0,
            limit: int = 100,
            is_active: Optional[bool] = None
    ) -> List[Organization]:
        """Get all organizations with pagination"""
        try:
            query = db.query(Organization)

            if is_active is not None:
                query = query.filter(Organization.is_active == is_active)

            return query.offset(skip).limit(limit).all()
        except Exception as e:
            logger.exception(f"Error getting all organizations: {e}")
            return []

    @staticmethod
    def get_organizations_count(db: Session, is_active: Optional[bool] = None) -> int:
        """Get total count of organizations"""
        try:
            query = db.query(func.count(Organization.id))

            if is_active is not None:
                query = query.filter(Organization.is_active == is_active)

            return query.scalar() or 0
        except Exception as e:
            logger.exception(f"Error getting organizations count: {e}")
            return 0

    @staticmethod
    def create_organization(
            db: Session,
            org_data: CreateOrganization
    ) -> Tuple[bool, Optional[Organization], Optional[str]]:
        """Create new organization"""
        try:
            # Check if organization already exists
            existing_org = OrganizationService.get_organization_by_name(db, org_data.name)
            if existing_org:
                return False, existing_org, "Organization with this name already exists"

            # Create new organization
            organization = Organization(
                name=org_data.name,
                description=org_data.description,
                logo=org_data.logo
            )

            db.add(organization)
            db.commit()
            db.refresh(organization)

            logger.info(f"Organization created: {organization.name} (ID: {organization.id})")
            return True, organization, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error creating organization: {e}")
            return False, None, str(e)

    @staticmethod
    def update_organization(
            db: Session,
            org_id: UUID,
            org_data: UpdateOrganization
    ) -> Tuple[bool, Optional[Organization], Optional[str]]:
        """Update organization"""
        try:
            organization = OrganizationService.get_organization_by_id(db, org_id)
            if not organization:
                return False, None, "Organization not found"

            # Check if name is being updated and if it already exists
            if org_data.name and org_data.name != organization.name:
                existing_org = OrganizationService.get_organization_by_name(db, org_data.name)
                if existing_org:
                    return False, None, "Organization with this name already exists"

            # Update fields
            update_data = org_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(organization, field, value)

            db.commit()
            db.refresh(organization)

            logger.info(f"Organization updated: {organization.name} (ID: {organization.id})")
            return True, organization, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error updating organization: {e}")
            return False, None, str(e)

    @staticmethod
    def toggle_organization_status(
            db: Session,
            org_id: UUID
    ) -> Tuple[bool, Optional[Organization], Optional[str]]:
        """Toggle organization active status"""
        try:
            organization = OrganizationService.get_organization_by_id(db, org_id)
            if not organization:
                return False, None, "Organization not found"

            organization.is_active = not organization.is_active
            db.commit()
            db.refresh(organization)

            logger.info(f"Organization status toggled: {organization.name} - Active: {organization.is_active}")
            return True, organization, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error toggling organization status: {e}")
            return False, None, str(e)

    @staticmethod
    def delete_organization(
            db: Session,
            org_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Delete organization (soft delete by setting is_active=False)"""
        try:
            organization = OrganizationService.get_organization_by_id(db, org_id)
            if not organization:
                return False, "Organization not found"

            # Soft delete
            organization.is_active = False
            organization.is_deleted = True
            db.commit()

            logger.info(f"Organization soft deleted: {organization.name} (ID: {organization.id})")
            return True, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error deleting organization: {e}")
            return False, str(e)

    @staticmethod
    def hard_delete_organization(
            db: Session,
            org_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Hard delete organization (permanent deletion)"""
        try:
            organization = OrganizationService.get_organization_by_id(db, org_id)
            if not organization:
                return False, "Organization not found"

            db.delete(organization)
            db.commit()

            logger.info(f"Organization hard deleted: ID: {org_id}")
            return True, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error hard deleting organization: {e}")
            return False, str(e)

    # Member Management
    @staticmethod
    def add_member_to_organization(
            db: Session,
            org_id: UUID,
            member_data: AddOrganizationMember
    ) -> Tuple[bool, Optional[OrganizationMember], Optional[str]]:
        """Add member to organization"""
        try:
            # Check if organization exists
            organization = OrganizationService.get_organization_by_id(db, org_id)
            if not organization:
                return False, None, "Organization not found"

            # Check if user exists
            user = db.query(User).filter(User.id == member_data.user_id).first()
            if not user:
                return False, None, "User not found"

            # Check if user is already a member
            existing_member = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == member_data.user_id
            ).first()

            if existing_member:
                return False, existing_member, "User is already a member of this organization"

            # Create member
            member = OrganizationMember(
                organization_id=org_id,
                user_id=member_data.user_id,
                role=OrganizationRole(member_data.role)
            )

            db.add(member)
            db.commit()
            db.refresh(member)

            logger.info(f"Member added to organization: User {member_data.user_id} -> Org {org_id}")
            return True, member, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error adding member to organization: {e}")
            return False, None, str(e)

    @staticmethod
    def get_organization_members(
            db: Session,
            org_id: UUID,
            is_active: Optional[bool] = None
    ) -> List[OrganizationMember]:
        """Get all members of an organization"""
        try:
            query = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id
            )

            if is_active is not None:
                query = query.filter(OrganizationMember.is_active == is_active)

            return query.all()
        except Exception as e:
            logger.exception(f"Error getting organization members: {e}")
            return []

    @staticmethod
    def update_member_role(
            db: Session,
            org_id: UUID,
            user_id: UUID,
            new_role: str
    ) -> Tuple[bool, Optional[OrganizationMember], Optional[str]]:
        """Update member role in organization"""
        try:
            member = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            ).first()

            if not member:
                return False, None, "Member not found"

            member.role = OrganizationRole(new_role)
            db.commit()
            db.refresh(member)

            logger.info(f"Member role updated: User {user_id} in Org {org_id} -> {new_role}")
            return True, member, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error updating member role: {e}")
            return False, None, str(e)

    @staticmethod
    def remove_member_from_organization(
            db: Session,
            org_id: UUID,
            user_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Remove member from organization"""
        try:
            member = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            ).first()

            if not member:
                return False, "Member not found"

            db.delete(member)
            db.commit()

            logger.info(f"Member removed from organization: User {user_id} from Org {org_id}")
            return True, None

        except Exception as e:
            db.rollback()
            logger.exception(f"Error removing member from organization: {e}")
            return False, str(e)

    @staticmethod
    def get_members_count(db: Session, org_id: UUID) -> int:
        """Get count of members in an organization"""
        try:
            return db.query(func.count(OrganizationMember.id)).filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active == True
            ).scalar() or 0
        except Exception as e:
            logger.exception(f"Error getting members count: {e}")
            return 0

    @staticmethod
    def get_all_organization_people(
            db: Session,
            org_id: UUID,
            is_active: Optional[bool] = None
    ) -> dict:
        """
        Get ALL people associated with organization:
        - Official org members (Founder, Co-Founder, Admin)
        - Ride participants (people who joined any ride)
        """
        try:
            # 1. Get official org members
            org_members_query = db.query(
                User.id,
                User.name,
                User.phone_number,
                User.email,
                OrganizationMember.role,
                OrganizationMember.is_active,
                OrganizationMember.created_at,
                literal('org_member').label('member_type')
            ).join(
                OrganizationMember,
                User.id == OrganizationMember.user_id
            ).filter(
                OrganizationMember.organization_id == org_id
            )

            if is_active is not None:
                org_members_query = org_members_query.filter(
                    OrganizationMember.is_active == is_active
                )

            # 2. Get ride participants (who are NOT org members)
            ride_participants_query = db.query(
                User.id,
                User.name,
                User.phone_number,
                User.email,
                literal(None).label('role'),  # They don't have org role
                literal(True).label('is_active'),
                func.min(RideParticipant.registered_at).label('created_at'),
                literal('ride_participant').label('member_type')
            ).join(
                RideParticipant,
                User.id == RideParticipant.user_id
            ).join(
                Ride,
                RideParticipant.ride_id == Ride.id
            ).filter(
                Ride.organization_id == org_id,
                # Exclude users who are already org members
                ~User.id.in_(
                    db.query(OrganizationMember.user_id).filter(
                        OrganizationMember.organization_id == org_id
                    )
                )
            ).group_by(
                User.id,
                User.name,
                User.phone_number,
                User.email
            )

            # 3. Combine both queries
            all_people = org_members_query.union(ride_participants_query).all()

            # 4. Organize results
            org_members = []
            ride_participants = []

            for person in all_people:
                person_dict = {
                    "id": str(person.id),
                    "name": person.name,
                    "phone": person.phone_number,
                    "email": person.email,
                    "role": person.role.value if person.role else None,
                    "is_active": person.is_active,
                    "created_at": person.created_at.strftime("%Y-%m-%d"),
                    "member_type": person.member_type
                }

                if person.member_type == 'org_member':
                    org_members.append(person_dict)
                else:
                    ride_participants.append(person_dict)

            return {
                "org_members": org_members,
                "ride_participants": ride_participants,
                "total_count": len(all_people)
            }

        except Exception as e:
            logger.exception(f"Error getting organization people: {e}")
            return {
                "org_members": [],
                "ride_participants": [],
                "total_count": 0
            }