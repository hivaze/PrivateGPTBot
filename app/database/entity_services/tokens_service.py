import enum
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import settings
from app.bot import tg_bot
from app.database.sql_db_service import TokensPackageEntity, UserEntity, Role
from app.utils.misc import parse_timedelta, strfdelta
from app.utils.tg_bot_utils import format_language_code

logger = logging.getLogger(__name__)


class TokensUsageStatus(enum.Enum):
    EXPIRED = "expired"
    NOT_ENOUGH = "not_enough"
    ALLOWED = "allowed"


def find_tokens_package(session: Session, user_id: int) -> TokensPackageEntity:
    packages = session.scalars(select(TokensPackageEntity).where(TokensPackageEntity.user_id == user_id)).all()
    packages.sort(
        key=lambda x: (x.left_tokens <= 0 or x.expires_at < datetime.now(), -x.expires_at.timestamp(), -x.left_tokens))
    return None if len(packages) == 0 else packages[0]


def find_all_tokens_packages(session: Session, user_id: int):
    return session.scalars(select(TokensPackageEntity)
                           .order_by(TokensPackageEntity.level.desc())
                           .where(TokensPackageEntity.user_id == user_id)
                           ).all()


def add_new_tokens_package(session: Session, user_id: int, package_name: str):
    package = settings.tokens_packages[package_name]
    created_at = datetime.now()
    expires_at = created_at + parse_timedelta(package.duration)
    tokens_package = TokensPackageEntity(created_at=created_at,
                                         expires_at=expires_at,
                                         level=package.level,
                                         package_name=package_name,
                                         left_tokens=package.tokens)
    tokens_package.user_id = user_id
    session.add(tokens_package)


def init_tokens_package(session: Session, user: UserEntity, package_name: str = None):
    if package_name is None:
        if user.role in [Role.PRIVILEGED]:
            package_name = list(settings.tokens_packages.keys())[-1]
        else:
            package_name = settings.config.tokens_packages.by_default
    add_new_tokens_package(session, user.user_id, package_name)
    return package_name


def has_tokens_package(session: Session, user_id: int) -> bool:
    tokens_package = find_tokens_package(session, user_id)
    return tokens_package is not None


def check_tokens(session: Session,
                 user_id: int = None):
    tokens_package = find_tokens_package(session, user_id)
    if tokens_package.expires_at > datetime.now():
        if tokens_package.left_tokens <= 0:
            return TokensUsageStatus.NOT_ENOUGH, tokens_package
        else:
            return TokensUsageStatus.ALLOWED, tokens_package
    else:
        return TokensUsageStatus.EXPIRED, tokens_package


def tokens_spending(tokens_package, tokens_count, model_config):
    tokens_count *= model_config.tokens_scale  # scaling depends on model
    left_tokens = tokens_package.left_tokens
    left_tokens = max(left_tokens - tokens_count, 0)
    tokens_package.left_tokens = left_tokens
    return left_tokens


async def tokens_barrier(session: Session,
                         user: UserEntity) -> bool:
    tokens_status, tokens_package = check_tokens(session, user.user_id)
    lc = format_language_code(user.language_code)
    if tokens_status != TokensUsageStatus.ALLOWED:
        if user.role != Role.PRIVILEGED and tokens_status != TokensUsageStatus.EXPIRED and not settings.config.free_mode and tokens_package.level == 0:
            till_regen_delta = tokens_package.expires_at - datetime.now()
            till_regen_delta = strfdelta(till_regen_delta, format=settings.messages.time_format[lc])
            await tg_bot.send_message(user.user_id, settings.messages.tokens.out_of_tokens[lc].format(
                till_regen_delta=till_regen_delta))
            return False
        else:
            package_name = init_tokens_package(session, user)
            await tg_bot.send_message(user.user_id,
                                      settings.messages.tokens.reset[lc].format(package_name=package_name.upper()))
            logger.info(f"Reinitializing '{user.user_name}' | '{user.user_id}' tokens package to {package_name.upper()}")
    return True
