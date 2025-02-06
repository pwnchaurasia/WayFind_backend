from sqlalchemy.orm import Session

from db.models import Group
from db.schemas import CreateGroup
from utils import app_helper as helper
from utils import app_logger

logger = app_logger.createLogger("app")


class GroupService:

    @app_logger.functionlogs(log="app")
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
    def fetch_user_groups(user_id: int, db: Session):
        return db.query(Group).filter(Group.owner == user_id).all()
