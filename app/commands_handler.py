import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.exceptions_handler import exception_sorry
from app.bot import dp, CONFIG, MESSAGES, reset_user_state, PERSONALITIES_REPLY_MARKUP

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@exception_sorry()
async def welcome_user(message: types.Message, state: FSMContext, *args, **kwargs):

    if message.from_user.username in CONFIG['allowed_users']:
        await reset_user_state(state)
        text = MESSAGES['welcome']['with_access'] if message.get_command() != '/reset' else MESSAGES['welcome']['reset']
        reply_message = {
            'text': text,
            'reply_markup': types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP)
        }
        logger.info(f"User {message.from_user.username} with access initialized the bot.")
    else:
        reply_message = {
            'text': MESSAGES['welcome']['no_access']
        }
        logger.warning(f"User {message.from_user.username} without access tries to use the bot!")

    await message.answer(**reply_message)
