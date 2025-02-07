from sqlalchemy.orm import Session, joinedload

from db.models import Group, GroupMembership
from db.schemas import CreateGroup
from utils import app_helper as helper, GroupUserType
from utils import app_logger

logger = app_logger.createLogger("app")


class GroupService:

    @staticmethod
    def get_group_by_id(db:Session, group_id:int):
        return db.query(Group).filter(Group.id == group_id).first()


    @staticmethod
    def fetch_group_admins(db: Session, group_id: int):
        return db.query(GroupMembership).filter(
            GroupMembership.group_id==group_id,
            GroupMembership.role == GroupUserType.ADMIN
        ).all()

    @staticmethod
    def is_user_group_admin(db: Session, user_id:int, group_id:int):
        return db.query(GroupMembership).filter(GroupMembership.group_id == group_id,
                                         GroupMembership.user_id == user_id,
                                         GroupMembership.role == GroupUserType.ADMIN).all()

    @staticmethod
    def create_group(user_id: int, group_data: CreateGroup, db: Session):
        """

        :param user_id:
        :param group_data:
        :param db:
        :return: is_group_created, group instance or none
        """
        try:
            group = Group(**group_data.model_dump())
            group.code = helper.generate_random_group_code()
            group.owner = user_id
            db.add(group)
            db.commit()
            db.refresh(group)
            return True, group
        except Exception as e:
            app_logger.exceptionlogs(f"Error creating group, Error: {e}")
            return False, None

    @staticmethod
    def fetch_user_groups_created_by_user(user_id: int, db: Session):
        return db.query(Group).filter(Group.owner == user_id).all()

    @staticmethod
    def fetch_group_from_code(db: Session, code):
        return db.query(Group).filter(Group.code == code).first()

    @staticmethod
    def user_already_member_of_group(db:Session, user_id: int, group_id:int):
        return db.query(GroupMembership).filter(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id
        ).first()


    @staticmethod
    def add_user_to_group(db:Session, user_id: int, group_id: int, role=GroupUserType.MEMBER):
        try:
            group_member = GroupMembership(user_id=user_id, group_id=group_id, role=role)
            group_member.is_active = True
            db.add(group_member)
            db.commit()
            db.refresh(group_member)
            return True, group_member
        except Exception as e:
            app_logger.exceptionlogs(f"Error in add_user_to_group, Error: {e}")
            return False, None

    @staticmethod
    def update_group_join_link(db: Session, group_id: int):
        try:
            group = GroupService.get_group_by_id(db=db, group_id=group_id)
            if not group:
                logger.debug(f"Group not found for group id {group_id}")
                return False, None
            group.code = helper.generate_random_group_code()
            db.add(group)
            db.commit()
            db.refresh(group)
            return True, group
        except Exception as e:
            app_logger.exceptionlogs(f"Error while updating group join link Error, {e}")
            return False, None

    @staticmethod
    def fetch_user_groups(db: Session, user_id: str):
        try:
            memberships = db.query(GroupMembership).options(joinedload(GroupMembership.group)).filter(
                GroupMembership.user_id == user_id,
                GroupMembership.is_active == True
            ).all()
            return memberships
        except Exception as e:
            app_logger.exceptionlogs(f"Error while updating group join link Error, {e}")
            return None
