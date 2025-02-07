from sqlalchemy.orm import Session

from db.models import Group
from services.group_service import GroupService
from services.user_service import UserService
from utils import app_logger

logger = app_logger.createLogger("app")


class Validator:

    @staticmethod
    @app_logger.functionlogs(log="log")
    def validate_group_creation(db: Session, user_id:int):
        try:
            user_setting = UserService.get_user_setting_by_user_id(user_id=user_id, db=db)
            if not user_setting:
                logger.warning(f"user {user_id} has no user settings. denying group creation.")
                return False
            max_group_creation = user_setting.max_group_creation
            user_groups = GroupService.fetch_user_groups_created_by_user(user_id=user_id, db=db)
            owned_groups = len(user_groups)
            if owned_groups >= max_group_creation:
                return False
            return True
        except Exception as e:
            app_logger.exceptionlogs(f"Error in validate_group_creation Error: {e} for user {user_id}")
            return False

    @staticmethod
    def user_already_in_group(db: Session, user_id:int, group_id: int):
        try:
            return GroupService.user_already_member_of_group(db=db, user_id=user_id, group_id=group_id)
        except Exception as e:
            app_logger.exceptionlogs(f"User already member of group {e}")
            return True

    @staticmethod
    def is_group_owner(db: Session, user_id: int, group_id: int) -> bool:
        group = GroupService.get_group_by_id(db=db, group_id=group_id)
        if group and group.owner == user_id:
            return True
        return False

    @staticmethod
    def can_update_join_link(db: Session, user_id: int, group_id: int):
        try:
            group_admins = GroupService.is_user_group_admin(db=db, user_id=user_id, group_id=group_id)
            if not group_admins:
                return False
            return True
        except Exception as e:
            app_logger.exceptionlogs(f"Error in can_update_join_link {e}")
            return False

