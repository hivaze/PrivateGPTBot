import typing
from datetime import datetime

from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import settings
from app.database.db_service import UserEntity, Role
from app.database.tokens_service import has_tokens_package, init_tokens_package


def _get_user_by_id(session: Session,
                    user_id: int) -> UserEntity:
    result = session.scalars(select(UserEntity).where(UserEntity.user_id == user_id))
    return result.first()


def _get_user_by_name(session: Session,
                      user_name: str) -> UserEntity:
    result = session.scalars(select(UserEntity).where(UserEntity.user_name == user_name))
    return result.first()


def _check_user_exists(session: Session, user_id: int) -> bool:
    return bool(_get_user_by_id(session, user_id))


def _create_user_kwargs(session: Session, **kwargs) -> UserEntity:
    user_entity = UserEntity(**kwargs,
                             role=Role.DEFAULT, joined_at=datetime.now())
    session.add(user_entity)
    return user_entity


def _create_user_tg(session: Session, tg_user: User) -> UserEntity:
    user_entity = UserEntity(user_id=tg_user.id, user_name=tg_user.username,
                             first_name=tg_user.first_name, language_code=tg_user.language_code,
                             role=Role.DEFAULT, joined_at=datetime.now())
    session.add(user_entity)
    return user_entity


def ban_username(session: Session, user_name: str) -> bool:
    user = _get_user_by_name(session, user_name)
    if user is not None:
        user.ban = True
        return True
    else:
        return False


def get_or_create_user(session: Session, tg_user: User) -> UserEntity:
    user = _get_user_by_id(session, tg_user.id)
    if user is not None:
        if user.user_name != tg_user.username:
            user.user_name = tg_user.username
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
        if user.language_code != tg_user.language_code:
            user.language_code = tg_user.language_code
        return user
    else:
        return _create_user_tg(session, tg_user)


def get_all_users(session: Session, with_banned=False) -> typing.List[UserEntity]:
    if with_banned:
        users = session.scalars(select(UserEntity)).all()
    else:
        users = session.scalars(select(UserEntity).where(UserEntity.ban != True)).all()
    return users


def get_user_model(user: UserEntity):
    if user.role == Role.PRIVILEGED:
        return settings.config.models.privileged
    return settings.config.models.default


def check_user_access(session: Session, tg_user: User) -> bool:
    user = _get_user_by_id(session, tg_user.id)
    if user is not None:
        if user.ban:
            return False
    if not settings.config.global_mode:
        return tg_user.username in settings.config.white_list_users or check_is_admin(tg_user)
    else:
        return True


def check_is_admin(tg_user: User) -> bool:
    return tg_user.username in settings.config.admins


# ------- Aiogram FSM section -------


class UserState(StatesGroup):
    menu = State()
    custom_pers_setup = State()
    communication = State()
    admin_message = State()


async def reset_user_state(session: Session, tg_user, state):
    user = get_or_create_user(session, tg_user)

    if not has_tokens_package(session, tg_user.id):
        init_tokens_package(session, user)

    await state.reset_data()
    await UserState.menu.set()

    return user
