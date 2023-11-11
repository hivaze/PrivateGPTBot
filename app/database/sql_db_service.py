import enum
import inspect
import typing

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum, Boolean, create_engine, Table, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

# DB_PATH = 'resources/users.db'
# engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)  # can be async

engine = create_engine(f'postgresql+psycopg2://test_user:testPassword123@postgres:5432/app_db',
                       pool_size=20,
                       max_overflow=200)

session_factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)  # Autoflush must be disabled
Base = declarative_base()


# ------- SQL ORM Objects -------


class Role(enum.Enum):
    DEFAULT = "default"
    PRIVILEGED = "privileged"


class Reaction(enum.Enum):
    GOOD = "good"
    BAD = "bad"


class FeedbackEntity(Base):
    __tablename__ = "feedback"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    tg_message_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False)
    text = Column(String(), nullable=False)


class GlobalMessagesUsersAssociation(Base):
    __tablename__ = 'global_messages_users'

    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    global_message_id = Column(Integer, ForeignKey('global_messages.id'), primary_key=True)

    processed_at = Column(DateTime, nullable=False)
    reaction = Column(Enum(Reaction), default=None, nullable=True)
    tg_message_id = Column(BigInteger, default=None, nullable=True)
    error_message = Column(String, default=None, nullable=True)

    # Relationships
    user = relationship("UserEntity",
                        back_populates="global_message_associations")

    global_message = relationship("GlobalMessageEntity",
                                  back_populates="user_associations")


class GlobalMessageEntity(Base):
    __tablename__ = "global_messages"

    id = Column("id", Integer, primary_key=True)

    created_at = Column(DateTime, nullable=False)
    text = Column(String(), nullable=False)
    from_user = Column(BigInteger, nullable=False)

    user_associations = relationship("GlobalMessagesUsersAssociation",
                                     back_populates="global_message",
                                     cascade="all, delete-orphan")


class TokensPackageEntity(Base):
    __tablename__ = "tokens_packages"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    # user = relationship("UserEntity", uselist=False, back_populates="tokens_package", lazy='joined')

    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    package_name = Column(String(20), nullable=False)
    level = Column(Integer, nullable=False)
    left_tokens = Column(Integer, default=0, nullable=False)
    left_images = Column(Integer, default=0, nullable=False)
    left_stt_minutes = Column(Integer, default=0, nullable=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)

    allow_global_messages = Column(Boolean, default=True, nullable=False)
    enable_reactions = Column(Boolean, default=True, nullable=False)
    enable_tokens_info = Column(Boolean, default=False, nullable=False)
    use_sse = Column(Boolean, default=False, nullable=False)
    use_superior_by_default = Column(Boolean, default=False, nullable=False)


class UserEntity(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)

    user_name = Column(String(50), nullable=True)
    first_name = Column(String(50), nullable=True)
    language_code = Column(String(6), nullable=True)

    role = Column(Enum(Role), nullable=False)
    joined_at = Column(DateTime, nullable=False)

    ban = Column(Boolean, default=False, nullable=False)

    tokens_packages = relationship("TokensPackageEntity",
                                   backref="user",
                                   cascade="all, delete-orphan")
    settings = relationship("UserSettings",
                            backref="user", uselist=False,
                            cascade="all, delete-orphan")
    messages = relationship("MessageEntity",
                            backref="user",
                            cascade="all, delete-orphan")

    global_message_associations = relationship("GlobalMessagesUsersAssociation",
                                               back_populates="user",
                                               cascade="all, delete-orphan")


class ImageGenerationEntity(Base):
    __tablename__ = "image_generations"

    id = Column("id", Integer, primary_key=True)

    tg_message_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)


class MessageEntity(Base):
    __tablename__ = "messages"

    id = Column("id", Integer, primary_key=True)

    tg_message_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)

    executed_at = Column(DateTime, nullable=False)
    time_taken = Column(Integer, default=None, nullable=True)

    model = Column(String(50), nullable=False)
    personality = Column(String(50), nullable=False)

    prompt_tokens = Column(Integer, default=0, nullable=True)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    history_size = Column(Integer, default=1, nullable=False)

    instant_buffer = Column(Integer, default=1, nullable=False)
    has_image = Column(Boolean, default=False, nullable=False)
    has_audio = Column(Boolean, default=False, nullable=False)
    has_document = Column(Boolean, default=False, nullable=False)
    function_call = Column(String(50), nullable=True)

    # new fields
    regenerated = Column(Boolean, default=False, nullable=False)
    reaction = Column(Enum(Reaction), default=None, nullable=True)


class FailedCommunicationEntity(Base):
    __tablename__ = "failed_communications"

    id = Column("id", Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    happened_at = Column(DateTime, nullable=False)
    exception_message = Column(String, nullable=False)
    traceback = Column(String, nullable=False)


Base.metadata.create_all(engine)


def with_session(fn: typing.Callable):
    assert inspect.iscoroutinefunction(fn), "Only async functions supported"

    async def inner(*args, **kwargs):
        with session_factory() as session:
            try:
                kwargs.update({'session': session})
                result = await fn(*args, **kwargs)
            except Exception:
                session.rollback()
                raise
            else:
                session.commit()
            session.close()
            return result

    return inner
