import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.database.sql_db_service import FeedbackEntity, UserEntity


logger = logging.getLogger(__name__)


def save_feedback(session: Session, user: UserEntity, text: str):
    fe = FeedbackEntity(user_id=user.user_id, created_at=datetime.now(), text=text)
    session.add(fe)
    logger.info(f"User saved new feedback message '{user.user_name}' | '{user.user_id}': '{text[:15]}...'")
