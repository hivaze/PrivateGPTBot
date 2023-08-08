import typing

from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.db_service import MessageEntity, UserEntity
from app.database.users_service import _get_user_by_id


def get_user_messages(session: Session, tg_user: User) -> typing.List[MessageEntity]:
    user = _get_user_by_id(session, tg_user.id)
    return user.messages  # lazy request here


def add_message_record(session: Session,
                       user_id: int, message_entity: MessageEntity) -> UserEntity:
    message_entity.user_id = user_id
    session.add(message_entity)
    return message_entity.user


def get_all_messages(session: Session) -> typing.List[MessageEntity]:
    all_messages = session.scalars(select(MessageEntity)).all()
    return all_messages


def get_avg_hist_size_by_user(session: Session) -> float:
    subquery = (session.query(MessageEntity.user_id, func.avg(MessageEntity.history_size).label('average_hist_size'))
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.average_hist_size).label('average_between_averages')).scalar()
    return average_query


def get_avg_tokens_by_user(session: Session) -> float:
    subquery = (session.query(MessageEntity.user_id, func.sum(MessageEntity.used_tokens).label('average_used_tokens'))
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.average_used_tokens).label('average_between_averages')).scalar()
    return average_query


def get_avg_tokens_per_message(session: Session) -> float:
    average_query = session.query(func.avg(MessageEntity.used_tokens).label('average_used_tokens')).scalar()
    return average_query


def get_avg_messages_by_user(session: Session) -> float:
    subquery = (session.query(MessageEntity.user_id, func.count().label('total_messages'))
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.total_messages).label('average_messages')).scalar()
    return average_query
