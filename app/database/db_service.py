import enum
import inspect
import typing

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

# sys.path.append('/home/hivaze/Documents/CODE-W/PyCharm Projects/HelperAIBot')
# print(sys.path)

DB_PATH = 'resources/users.db'

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)  # can be async
session_factory = sessionmaker(engine, expire_on_commit=False, autoflush=True)
Base = declarative_base()


# ------- SQL ORM Objects -------


class Role(enum.Enum):
    DEFAULT = "default"
    PRIVILEGED = "privileged"  # auto-renew of tokens packages on end


class TokensPackageEntity(Base):
    __tablename__ = "tokens_packages"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    # user = relationship("UserEntity", uselist=False, back_populates="tokens_package", lazy='joined')

    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    package_name = Column(String(20), nullable=False)
    left_tokens = Column(Integer, default=0, nullable=False)


class UserEntity(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)

    user_name = Column(String(50), nullable=True)
    first_name = Column(String(50), nullable=True)
    language_code = Column(String(6), nullable=True)

    role = Column(Enum(Role), nullable=False)
    joined_at = Column(DateTime, nullable=False)

    ban = Column(Boolean, default=False, nullable=False)

    tokens_packages = relationship("TokensPackageEntity", backref="user", cascade="all, delete-orphan")
    messages = relationship("MessageEntity", backref="user", cascade="all, delete-orphan")


class MessageEntity(Base):
    __tablename__ = "messages"

    id = Column("id", Integer, primary_key=True)

    tg_message_id = Column(Integer, nullable=False)
    used_tokens = Column(Integer, default=0, nullable=False)
    has_image = Column(Boolean, default=False, nullable=False)
    executed_at = Column(DateTime, nullable=False)
    personality = Column(String(50), nullable=False)
    history_size = Column(Integer, default=1, nullable=False)

    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)


Base.metadata.create_all(engine)


def with_session(fn: typing.Callable):

    assert inspect.iscoroutinefunction(fn), "Only async functions supported"

    async def inner(*args, **kwargs):
        with session_factory() as session:
            try:
                result = await fn(session, *args, **kwargs)
            except Exception:
                session.rollback()
                raise
            else:
                session.commit()
            session.close()
            return result

    return inner
