import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.sql_db_service import FeedbackEntity, UserEntity

logger = logging.getLogger(__name__)


def get_feedback_by_id(session: Session,
                       feedback_id: int) -> FeedbackEntity:
    result = session.scalars(select(FeedbackEntity).where(FeedbackEntity.id == feedback_id))
    return result.first()


def save_feedback(session: Session, user: UserEntity, text: str):
    fe = FeedbackEntity(user_id=user.user_id, created_at=datetime.now(), text=text)
    session.add(fe)
    logger.info(f"User saved new feedback message '{user.user_name}' | '{user.user_id}': '{text[:15]}...'")


def get_week_feedbacks(session: Session):
    last_week = datetime.now() - timedelta(weeks=1)
    feedbacks = session.scalars(select(FeedbackEntity).where(FeedbackEntity.created_at >= last_week)).all()
    return feedbacks
