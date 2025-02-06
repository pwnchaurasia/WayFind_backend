from db.models import Group
from utils import app_logger

logger = app_logger.createLogger("app")


class Validator:

    @staticmethod
    @app_logger.functionlogs(log="log")
    def validate_group_creation(user):
        try:
            if not user.user_setting:
                logger.warning(f"user {user.id} has no user settings. denying group creation.")
                return False
            user_setting = user.user_setting
            max_group_creation = user_setting.max_group_creation
            owned_groups = len(user.owned_groups)
            if owned_groups >= max_group_creation:
                return False
            return True
        except Exception as e:
            app_logger.exceptionlogs(f"Error in validate_group_creation Error: {e} for user {user.id}")
