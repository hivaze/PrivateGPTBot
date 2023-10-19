import typing
from datetime import datetime, timedelta

from aiogram.types import User
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.sql_db_service import MessageEntity, UserEntity
from app.database.entity_services.users_service import get_user_by_id


def get_user_messages(session: Session, tg_user: User) -> typing.List[MessageEntity]:
    user = get_user_by_id(session, tg_user.id)
    return user.messages  # lazy request here


def add_message_record(session: Session,
                       user_id: int,
                       message_entity: MessageEntity) -> UserEntity:
    message_entity.user_id = user_id
    session.add(message_entity)
    return message_entity.user


def get_all_messages(session: Session) -> typing.List[MessageEntity]:
    all_messages = session.scalars(select(MessageEntity)).all()
    return all_messages


def get_message_by_tgid(session: Session, tgid: int):
    result = session.query(MessageEntity).where(MessageEntity.tg_message_id == tgid).first()
    return result


def get_last_message(session: Session, user: UserEntity):
    last_message = (session.query(MessageEntity)
                    .filter((MessageEntity.user_id == user.user_id) & (MessageEntity.function_call == None))
                    .order_by(MessageEntity.executed_at.desc())
                    .first())
    return last_message


def get_avg_hist_size_by_user(session: Session) -> float:
    last_week = datetime.now() - timedelta(weeks=1)
    subquery = (session.query(MessageEntity.user_id, func.avg(MessageEntity.history_size).label('average_hist_size'))
                .filter(MessageEntity.executed_at >= last_week)
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.average_hist_size).label('average_between_averages')).scalar()
    return average_query


def get_avg_tokens_by_user(session: Session) -> float:
    last_week = datetime.now() - timedelta(weeks=1)
    subquery = (session.query(MessageEntity.user_id, func.sum(MessageEntity.total_tokens).label('average_used_tokens'))
                .filter(MessageEntity.executed_at >= last_week)
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.average_used_tokens).label('average_between_averages')).scalar()
    return average_query


def get_avg_tokens_per_message(session: Session) -> float:
    last_week = datetime.now() - timedelta(weeks=1)
    average_query = (session.query(func.avg(MessageEntity.total_tokens).label('average_used_tokens'))
                     .filter(MessageEntity.executed_at >= last_week)
                     .scalar())
    return average_query


def get_avg_messages_by_user(session: Session) -> float:
    last_week = datetime.now() - timedelta(weeks=1)
    subquery = (session.query(MessageEntity.user_id, func.count().label('total_messages'))
                .filter(MessageEntity.executed_at >= last_week)
                .group_by(MessageEntity.user_id)
                .subquery())
    average_query = session.query(func.avg(subquery.c.total_messages).label('average_messages')).scalar()
    return average_query
