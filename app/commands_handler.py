import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.exceptions_handler import exception_handler
from .bot import dp, CONFIG, PERSONALITIES, reset_user_state

PERSONALITIES_REPLY_MARKUP = [types.KeyboardButton(v['name']) for k, v in PERSONALITIES.items()]
PERSONALITIES_REPLY_MARKUP = [PERSONALITIES_REPLY_MARKUP[i:i + 2] for i in range(0, len(PERSONALITIES_REPLY_MARKUP), 2)]

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@exception_handler()
async def welcome_user(message: types.Message, state: FSMContext, *args, **kwargs):

    if message.from_user.username in CONFIG['allowed_users']:
        await reset_user_state(state)
        reply_message = {
            'text': 'Этот бот сделан @hivaze для ограниченного количества людей.'
                    '\nВ основе ChatGPT и планируются некоторые другие модели.'
                    '\n\nДля использования просто выбери нужный режим и пиши сообщения как в ChatGPT.'
                    '\n\nВсе твои сообщения не сохраняются, я их не увижу.',
            'reply_markup': types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP)
        }
        logger.info(f"Юзер {message.from_user.username} с допуском инициировал бота")
    else:
        reply_message = {
            'text': 'Этот бот сделан @hivaze для ограниченного количества людей.'
                    '\n\nК сожалению, тебе нельзя пользоваться этим ботом :('
        }
        logger.warning(f"Юзер {message.from_user.username} без допуска пытается использовать бота!!")

    await message.answer(**reply_message)
