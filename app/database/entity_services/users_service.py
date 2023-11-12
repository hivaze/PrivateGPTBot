import logging
import typing
from datetime import datetime

from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import settings
from app.database.sql_db_service import UserEntity, Role, UserSettingsEntity, ReferralLinkEntity
from app.database.entity_services.tokens_packages_service import init_tokens_package, find_tokens_package
from app.utils.tg_bot_utils import no_access_message

logger = logging.getLogger(__name__)


def get_user_by_id(session: Session,
                   user_id: int) -> UserEntity:
    result = session.scalars(select(UserEntity).where(UserEntity.user_id == user_id))
    return result.first()


def get_user_by_name(session: Session,
                     user_name: str) -> UserEntity:
    result = session.scalars(select(UserEntity).where(UserEntity.user_name == user_name))
    return result.first()


def _check_user_exists(session: Session, user_id: int) -> bool:
    return bool(get_user_by_id(session, user_id))


def _create_user_kwargs(session: Session, **kwargs) -> UserEntity:
    user_entity = UserEntity(**kwargs,
                             role=Role.DEFAULT, joined_at=datetime.now())
    session.add(user_entity)
    return user_entity


def _create_user_tg(session: Session, tg_user: User, referral_code: str = None) -> UserEntity:
    logger.info(f"Creating new user in DB with id {tg_user.id}")
    # TODO: Add referral link search
    user_entity = UserEntity(user_id=tg_user.id,
                             user_name=tg_user.username,
                             first_name=tg_user.first_name,
                             language_code=tg_user.language_code,
                             ban=not settings.config.global_mode and not check_is_admin(tg_user.username),
                             role=Role.DEFAULT,
                             joined_at=datetime.now())
    user_entity.settings = UserSettingsEntity()
    user_entity.referral_link = ReferralLinkEntity()
    session.add(user_entity)
    init_tokens_package(session, user_entity, package_name=settings.config.tokens_packages.as_first)
    session.commit()
    return user_entity


def set_ban_userid(session: Session, user_id: int, ban_state: bool) -> bool:
    user = get_user_by_id(session, user_id)
    if user is not None:
        user.ban = ban_state
        return True
    else:
        return False


def get_or_create_user(session: Session, tg_user: User) -> UserEntity:
    user = get_user_by_id(session, tg_user.id)
    if user is not None:
        if user.settings is None:
            user.settings = UserSettingsEntity()
        if user.referral_link is None:
            user.referral_link = ReferralLinkEntity()
        if find_tokens_package(session, tg_user.id) is None:
            init_tokens_package(session, user)
        if user.user_name != tg_user.username:
            user.user_name = tg_user.username
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
        if user.language_code != tg_user.language_code:
            user.language_code = tg_user.language_code
        session.commit()
        return user
    else:
        return _create_user_tg(session, tg_user)


def get_all_users(session: Session):
    return session.query(UserEntity).all()


def get_users_with_filters(session, ban_status=False, global_messages_status=True):
    users_with_settings = session.query(UserEntity).\
        join(UserSettingsEntity, UserEntity.user_id == UserSettingsEntity.user_id).\
        filter((UserEntity.ban == ban_status) & (UserSettingsEntity.allow_global_messages == global_messages_status)).all()

    return users_with_settings


def check_is_admin(user_name) -> bool:
    return user_name in settings.config.admins


def access_check(fn: typing.Callable):

    async def inner(*args, **kwargs):
        message = kwargs.get('message')
        session = kwargs.get('session')
        tg_user = message.from_user
        user = get_or_create_user(session, tg_user)
        if not user.ban:
            kwargs.update({'user': user})
            await fn(*args, **kwargs)
        else:
            await no_access_message(tg_user, message)
            logger.warning(f"User '{tg_user.username}' | '{tg_user.id}' without access tries to use the bot!")

    return inner

