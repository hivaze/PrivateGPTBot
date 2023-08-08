import enum
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import settings
from app.database.db_service import TokensPackageEntity, UserEntity, Role
from app.utils.general import parse_timedelta


class TokensUsageStatus(enum.Enum):
    EXPIRED = "expired"
    NOT_ENOUGH = "not_enough"  # auto-renew of tokens packages on end
    ALLOWED = "allowed"


def _find_tokens_package(session: Session, user_id: int):
    return session.scalars(select(TokensPackageEntity)
                           .order_by(TokensPackageEntity.left_tokens.desc())
                           .where(TokensPackageEntity.user_id == user_id)
                           ).first()


def add_new_tokens_package(session: Session, user_id: int, package_name: str):
    package = settings.tokens_packages[package_name]
    created_at = datetime.now()
    expires_at = created_at + parse_timedelta(package.duration)
    tokens_package = TokensPackageEntity(created_at=created_at,
                                         expires_at=expires_at,
                                         package_name=package_name,
                                         left_tokens=package.amount)
    tokens_package.user_id = user_id
    session.add(tokens_package)


def init_tokens_package(session: Session, user: UserEntity):
    if user.role in [Role.PRIVILEGED]:
        package_name = list(settings.tokens_packages.keys())[-1]
    else:
        package_name = 'trial'
    add_new_tokens_package(session, user.user_id, package_name)


def has_tokens_package(session: Session, user_id: int) -> bool:
    tokens_package = _find_tokens_package(session, user_id)
    return tokens_package is not None


def check_tokens(session: Session, user_id: int) -> TokensUsageStatus:
    tokens_package = _find_tokens_package(session, user_id)
    if tokens_package.expires_at > datetime.now():
        if tokens_package.left_tokens <= 0:
            return TokensUsageStatus.NOT_ENOUGH
        else:
            return TokensUsageStatus.ALLOWED
    else:
        return TokensUsageStatus.EXPIRED


def tokens_spending(session: Session, user_id: int, tokens_count):
    tokens_package = _find_tokens_package(session, user_id)
    left_tokens = tokens_package.left_tokens
    left_tokens = max(left_tokens - tokens_count, 0)
    tokens_package.left_tokens = left_tokens


def get_tokens_info(session: Session, user_id: int):
    tokens_package = _find_tokens_package(session, user_id)
    return tokens_package.left_tokens, tokens_package.expires_at
