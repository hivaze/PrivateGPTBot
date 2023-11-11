import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.bot import tg_bot
from app.database.sql_db_service import GlobalMessageEntity, GlobalMessagesUsersAssociation, UserEntity
from app.utils.tg_bot_utils import build_gmua_markup

logger = logging.getLogger(__name__)


def get_gmua(session: Session, user: UserEntity, tg_message_id: int) -> GlobalMessagesUsersAssociation:
    association = session.query(GlobalMessagesUsersAssociation).filter(
        GlobalMessagesUsersAssociation.user_id == user.user_id,
        GlobalMessagesUsersAssociation.tg_message_id == tg_message_id
    ).first()
    return association


async def global_message(session: Session, from_user: int, users: list, text: str, do_html: bool = False):
    logger.info(f"Admin initialized global message:\n{text[:50]}...")
    parse_mode = 'HTML' if do_html else None
    created_at = datetime.now()

    gm = GlobalMessageEntity(text=text, from_user=from_user, created_at=created_at)
    session.add(gm)
    session.commit()

    total_count = 0
    for user_entity in users:
        association = GlobalMessagesUsersAssociation(user=user_entity, global_message=gm, processed_at=datetime.now())
        try:
            sent_message = await tg_bot.send_message(user_entity.user_id, text,
                                                     parse_mode=parse_mode,
                                                     disable_notification=True,
                                                     reply_markup=build_gmua_markup(user_entity, association))
            association.tg_message_id = sent_message.message_id
            total_count += 1
        except Exception as e:
            association.error_message = f"{e}"
            logger.info(
                f"Exception {e} while sending global message to '{user_entity.user_name}' | '{user_entity.user_id}'")
        session.add(association)
        session.commit()

    duration = (datetime.now() - created_at).seconds

    logger.info(f"Admin global message was sent to {total_count} users in {duration} seconds!")
