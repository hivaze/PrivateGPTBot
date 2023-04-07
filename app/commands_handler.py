import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.exceptions_handler import exception_sorry
from .bot import dp, CONFIG, PERSONALITIES, UserState

PERSONALITIES_REPLY_MARKUP = [types.KeyboardButton(v['name']) for k, v in PERSONALITIES.items()]
PERSONALITIES_REPLY_MARKUP = [PERSONALITIES_REPLY_MARKUP[i:i + 2] for i in range(0, len(PERSONALITIES_REPLY_MARKUP), 2)]

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start"])
@exception_sorry()
async def welcome_user(message: types.Message, state: FSMContext, *args, **kwargs):

    if message.from_user.username in CONFIG['allowed_users']:
        reply_message = {
            'text': 'Этот бот сделан @hivaze для ограниченного количества людей.'
                    '\nВ основе ChatGPT и других GPT моделей от OpenAI.'
                    '\n\nДля использования просто выбери нужный режим и пиши сообщения как в ChatGPT.'
                    '\n\nВсе твои сообщения не сохраняются, я их не увижу (только если включен режим дебага)',
            'reply_markup': types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP)
        }
        logger.info(f"Юзер {message.from_user.username} с допуском инициировал бота")
    else:
        reply_message = {
            'text': 'К сожалению, тебе нельзя пользоваться этим ботом :('
        }
        logger.warning(f"Юзер {message.from_user.username} без допуска пытается использовать бота!!")

    await message.answer(**reply_message)


@dp.message_handler(commands=["reset"], state=UserState.communication)
@exception_sorry()
async def reset(message: types.Message, state: FSMContext, *args, **kwargs):
    await UserState.previous()
    await state.reset_data()
    await message.answer(f"Ты должен выбрать персонажа для общения.",
                         reply_markup=types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP))
