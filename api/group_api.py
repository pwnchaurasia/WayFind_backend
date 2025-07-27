from datetime import datetime

from fastapi import APIRouter, status, Request
from fastapi.params import Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from db.db_conn import get_db

from db.schemas import CreateGroup, GroupResponse, UserResponse, GroupMemberResponse
from services.group_service import GroupService
from utils import app_logger, resp_msgs, GroupUserType
from utils.dependencies import get_current_user
from utils.validation import Validator

router = APIRouter(prefix="/groups", tags=["groups"])

logger = app_logger.createLogger("app")


@app_logger.functionlogs(log="app")
@router.post("/", status_code=status.HTTP_200_OK)
def create_group(request: Request, group_data: CreateGroup,
                 db: Session = Depends(get_db),
                 current_user = Depends(get_current_user)):
    try:
        is_valid = Validator.validate_group_creation(user_id=current_user.id, db=db)
        if not is_valid:
            logger.debug(f"User {current_user} has reached max group creation.")
            return JSONResponse(content={"status": "error", "message": resp_msgs.MAX_GROUP_CREATION_REACHED},
                         status_code=status.HTTP_400_BAD_REQUEST)

        is_group_created, group = GroupService.create_group(user_id=current_user.id, group_data=group_data, db=db)
        logger.debug(f"Group: {group}")
        if not is_group_created:
            logger.error(f"Group creation failed for user {current_user}")
            return JSONResponse(content={"status": "error", "message": resp_msgs.GROUP_NOT_CREATED},
                                status_code=status.HTTP_400_BAD_REQUEST)
        user_added, group_member = GroupService.add_user_to_group(db=db, user_id=current_user.id,
                                                                  group_id=group.id,
                                                                  role=GroupUserType.ADMIN)
        logger.debug(f"User {group_member.user_id} added to group, {group.name} {group.id}")
        return JSONResponse(
            content={"status": "success",
                     "message": resp_msgs.GROUP_CREATED,
                     "group": GroupResponse.model_validate(group).to_response(request=request)},
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error creating group, Error: {e}")
        return JSONResponse(content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app_logger.functionlogs(log="app")
@router.post("/join/{code}", name="join_group_with_code")
def join_group_with_code(request:Request, code: str, db:Session = Depends(get_db), current_user = Depends(get_current_user)):
    logger.debug(f"code: {code}, user: {current_user}")
    try:
        # Todo: fetch group from code
        group = GroupService.fetch_group_from_code(db=db, code=code)
        if not group:
            return JSONResponse(content={"status": "error", "message": resp_msgs.INVALID_JOIN_LINK},
                                status_code=status.HTTP_400_BAD_REQUEST)

        already_a_member = Validator.user_already_in_group(db=db,
                                                           user_id=current_user.id,
                                                           group_id=group.id)
        if already_a_member:
            return JSONResponse(
                content={"status": "success",
                         "message": resp_msgs.ALREADY_MEMBER_OF_GROUP,
                         "data": GroupResponse.model_validate(group).to_response(request=request)},
                                status_code=status.HTTP_200_OK)

        user_added, group_member = GroupService.add_user_to_group(db=db,
                                                                  user_id=current_user.id,
                                                                  group_id=group.id,
                                                                  role=GroupUserType.MEMBER)
        logger.debug(f"User {group_member.user_id} added to group, {group.name} {group.id} "
                     f": group_member {group_member}")

        if not user_added:
            return JSONResponse(content={"status": "error", "message": resp_msgs.INVALID_JOIN_LINK},
                                status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(
            content={"status": "success", "message": resp_msgs.ADDED_TO_GROUP},
        status_code=status.HTTP_201_CREATED)

    except Exception as e:
        app_logger.exceptionlogs(f"Error joining group via join code, Error: {e}")
        return JSONResponse(content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.patch("/{group_id}/refresh-join-link", status_code=status.HTTP_200_OK, )
def refresh_group_join_link(request: Request, group_id: str,
                            db: Session = Depends(get_db),
                            current_user = Depends(get_current_user)):
    try:
        group = GroupService.get_group_by_id(db=db, group_id=group_id)
        can_update_join_link = Validator.can_update_join_link(db=db, user_id=current_user.id, group_id=group_id)
        if not can_update_join_link:
            return JSONResponse(content={"status": "error", "message": resp_msgs.CANT_UPDATE_GROUP_JOIN_LINK},
                                status_code=status.HTTP_400_BAD_REQUEST)

        is_updated , group = GroupService.update_group_join_link(db=db, group_id=group.id)
        if not is_updated:
            return JSONResponse(content={"status": "error", "message": resp_msgs.CANT_UPDATE_GROUP_JOIN_LINK},
                                status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(content={"status": "success",
                                     "message": resp_msgs.GROUP_JOIN_LINK_UPDATED,
                                     "data": GroupResponse.model_validate(group).to_response(request=request)},
                                status_code=status.HTTP_202_ACCEPTED)
    except Exception as e:
        app_logger.exceptionlogs(f"Error in refresh_group_join_link, Error: {e}")
        return JSONResponse(content={"status": "error", "message": resp_msgs.STATUS_500_MSG},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/{group_id}/users")
def fetch_group_users(request:Request, group_id: str, db: Session = Depends(get_db)):
    try:
        group_members = GroupService.fetch_group_users(db=db, group_id=group_id)
        #TODO in future will send last date time in this too
        users = []
        for members in group_members:
            user_dict = UserResponse.model_validate(members.user).model_dump(mode="json")

            user_dict.update({
                "role": members.role,
                "is_member_active": members.is_active,
                "lastSeen": datetime.now()
            })

            group_member = GroupMemberResponse.model_validate(user_dict)
            users.append(group_member.model_dump(mode="json"))

        return JSONResponse(
            content={"status": "success",
                     "message": "User groups",
                     "users": users},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error in fetch group users {e}")
        return JSONResponse(
            content={"status": "error",
                     "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/{group_id}/")
def fetch_group_users(request:Request, group_id: str, db: Session = Depends(get_db)):
    try:
        group = GroupService.get_group_by_id(db=db, group_id=group_id)

        group_info = GroupResponse.model_validate(group).model_dump(mode="json")
        return JSONResponse(
            content={"status": "success",
                     "message": "Group Info",
                     "group": group_info},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        app_logger.exceptionlogs(f"Error in fetch group users {e}")
        return JSONResponse(
            content={"status": "error",
                     "message": resp_msgs.STATUS_500_MSG},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)