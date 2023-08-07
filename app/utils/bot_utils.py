import datetime
import logging

from aiogram import types
from aiogram.types import User, InputFile
from sqlalchemy.orm import Session

from app import settings
from app.bot import tg_bot
from app.database.db_service import DB_PATH
from app.database.users_service import get_all_users

logger = logging.getLogger(__name__)


async def no_access_message(tg_user: User, message):
    reply_message = {
        'text': settings.messages.welcome.no_access
    }
    logger.warning(f"User '{tg_user.username}' | '{tg_user.id}' without access tries to use the bot!")
    await message.answer(**reply_message)


async def send_db(tg_user: User):
    file = InputFile(DB_PATH, filename=f"users-{datetime.datetime.now()}.db")
    await tg_bot.send_document(tg_user.id, file)


async def global_message(session: Session, text: str, do_markdown: bool = False):
    logger.info(f"Admin initialized global message:\n{text[:30]}...")
    parse_mode = 'Markdown' if do_markdown else None
    for user_entity in get_all_users(session):
        try:
            await tg_bot.send_message(user_entity.user_id, text, parse_mode=parse_mode, disable_notification=True)
        except Exception as e:
            logger.info(
                f"Exception {e} while sending global message to '{user_entity.user_name}' | '{user_entity.user_id}'")


def build_menu_markup(tg_user: User):
    markup = [types.KeyboardButton(v.name) for k, v in settings.personalities.items()
              if v.location == 'main']
    markup = [markup[i:i + 2] for i in range(0, len(markup), 2)]
    markup = markup + [[types.KeyboardButton(settings.messages.specialties.button)]]
    return types.ReplyKeyboardMarkup(keyboard=markup, resize_keyboard=True)


def build_specials_markup(tg_user: User):
    markup = [types.KeyboardButton(v.name) for k, v in settings.personalities.items()
              if v.location == 'specialties']
    markup = [markup[i:i + 2] for i in range(0, len(markup), 2)]
    markup = markup + [[types.KeyboardButton(settings.messages.custom_personality.button),
                        types.KeyboardButton(settings.messages.specialties.back_button)]]
    return types.ReplyKeyboardMarkup(keyboard=markup, resize_keyboard=True)
