import enum
import sys
import typing
from datetime import datetime
from functools import lru_cache

from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import User
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum, select, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session

# sys.path.append('/home/hivaze/Documents/CODE-W/PyCharm Projects/HelperAIBot')
# print(sys.path)

from app.bot import settings
from app.utils import parse_timedelta

engine = create_engine('sqlite:///resources/users.db', echo=False)
session_factory = sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


# ------- SQL ORM Objects -------


class Role(enum.Enum):
    DEFAULT = "default"
    PRIVILEGED = "privileged"  # auto-renew of tokens packages on end


class TokensPackageEntity(Base):
    __tablename__ = "tokens_packages"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    user = relationship("UserEntity", uselist=False, back_populates="tokens_package", lazy='joined')

    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    package_name = Column(String(20), nullable=False)
    left_tokens = Column(Integer, default=-1, nullable=False)


class UserEntity(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)

    user_name = Column(String(50), nullable=True)
    first_name = Column(String(50), nullable=True)
    language_code = Column(String(6), nullable=True)

    role = Column(Enum(Role), nullable=False)
    joined_at = Column(DateTime, nullable=False)

    ban = Column(Boolean, default=False, nullable=False)

    # token_package_id = Column(Integer, ForeignKey('tokens_packages.id'), nullable=True)
    tokens_package = relationship("TokensPackageEntity", uselist=False, back_populates="user",
                                  cascade="all, delete-orphan")
    messages = relationship("MessageEntity", backref="user", cascade="all, delete-orphan")


class MessageEntity(Base):
    __tablename__ = "messages"

    id = Column("id", Integer, primary_key=True)

    tg_message_id = Column(Integer, nullable=False)
    used_tokens = Column(Integer, default=0, nullable=False)
    has_image = Column(Boolean, default=False, nullable=False)
    executed_at = Column(DateTime, nullable=False)

    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)


Base.metadata.create_all(engine)


# ------- Helper functions -------

@lru_cache(maxsize=100)
def get_session(user_id):
    return session_factory()


def with_session(fn: typing.Callable):
    def inner(*args, **kwargs):
        with session_factory() as session:
            try:
                result = fn(session, *args, **kwargs)
            except Exception:
                session.rollback()
                raise
            else:
                session.commit()
            session.close()
            return result

    return inner


# ------- User section -------


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
                             role=Role.PRIVILEGED, joined_at=datetime.now())  # TODO: Change role to DEFAULT
    session.add(user_entity)
    return user_entity


@with_session
def ban_username(session: Session, user_name: str) -> bool:
    user = _get_user_by_name(session, user_name)
    if user is not None:
        user.ban = True
        return True
    else:
        return False


@with_session
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


@with_session
def get_all_users(session: Session) -> typing.List[UserEntity]:
    users = session.scalars(select(UserEntity).where(UserEntity.ban != True)).all()
    return users


@with_session
def check_user_access(session: Session, tg_user: User) -> bool:
    user = _get_user_by_id(session, tg_user.id)
    if user is not None:
        if user.ban:
            return False
    if not settings.config['global_mode']:
        return tg_user.username in settings.config['white_list_users'] or tg_user.username == settings.config['admin']
    else:
        return True


def check_is_admin(tg_user: User) -> bool:
    return tg_user.username == settings.config['admin']


# ------- Messages section -------


@with_session
def get_user_messages(session: Session, tg_user: User) -> typing.List[MessageEntity]:
    user = _get_user_by_id(session, tg_user.id)
    return user.messages  # lazy request here


@with_session
def add_message_record(session: Session,
                       user_id: int, message_entity: MessageEntity) -> UserEntity:
    message_entity.user_id = user_id
    session.add(message_entity)
    return message_entity.user


# ------- Tokens section -------


class TokensUsageStatus(enum.Enum):
    EXPIRED = "expired"
    NOT_ENOUGH = "not_enough"  # auto-renew of tokens packages on end
    ALLOWED = "allowed"


@with_session
def set_tokens_package(session: Session, user_id: int, package_name: str):
    user = _get_user_by_id(session, user_id)
    package = settings.tokens_packages[package_name]
    created_at = datetime.now()
    expires_at = created_at + parse_timedelta(package['duration'])
    user.tokens_package = TokensPackageEntity(created_at=created_at,
                                              expires_at=expires_at,
                                              package_name=package_name,
                                              left_tokens=package['amount'])


def reset_tokens_package(user: UserEntity):
    if user.role in [Role.PRIVILEGED]:
        package_name = list(settings.tokens_packages.keys())[-1]
    else:
        package_name = 'trial'
    set_tokens_package(user.user_id, package_name)


@with_session
def has_tokens_package(session: Session, user_id: int) -> bool:
    tokens_package = session.scalars(select(TokensPackageEntity).where(TokensPackageEntity.user_id == user_id)).first()
    return tokens_package is not None


@with_session
def check_tokens(session: Session, user_id: int) -> TokensUsageStatus:
    user = _get_user_by_id(session, user_id)
    tokens_package = user.tokens_package
    if tokens_package.expires_at > datetime.now():
        if tokens_package.left_tokens <= 0:
            return TokensUsageStatus.NOT_ENOUGH
        else:
            return TokensUsageStatus.ALLOWED
    else:
        return TokensUsageStatus.EXPIRED


@with_session
def tokens_spending(session: Session, user_id: int, tokens_count):
    user = _get_user_by_id(session, user_id)
    left_tokens = user.tokens_package.left_tokens
    left_tokens = max(left_tokens - tokens_count, 0)
    user.tokens_package.left_tokens = left_tokens


@with_session
def get_tokens_info(session: Session, user_id: int):
    user = _get_user_by_id(session, user_id)
    tokens_package = user.tokens_package
    return tokens_package.left_tokens, tokens_package.expires_at


# ------- Aiogram FSM section -------


class UserState(StatesGroup):
    menu = State()
    custom_pers_setup = State()
    communication = State()
    admin_message = State()


async def reset_user_state(tg_user, state):
    user = get_or_create_user(tg_user)

    if not has_tokens_package(tg_user.id):
        reset_tokens_package(user)

    await state.reset_data()
    await UserState.menu.set()


def main() -> None:
    Base.metadata.create_all(engine)
    # await add_message_record(test_user.user_id, MessageEntity(tg_message_id=234, used_tokens=394,
    #                                                           has_image=False, executed_at=datetime.datetime.now()))
    # print(len(test_user.user_name))
    engine.dispose()
    user = get_all_users()[0]
    print(user._session)


if __name__ == '__main__':
    main()
