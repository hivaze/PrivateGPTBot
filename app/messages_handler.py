import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.exceptions_handler import exception_sorry
from . import PERSONALITIES_REPLY_MARKUP
from .bot import dp, CONFIG, PERSONALITIES, UserState
from .open_ai_client import create_message

logger = logging.getLogger(__name__)


class TypingBlock(object):

    def __init__(self, chat: types.Chat):
        self.chat = chat
        self.typing_task = None

    async def __aenter__(self):

        async def typing_cycle():
            try:
                while True:
                    await self.chat.do("typing")
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        self.typing_task = asyncio.create_task(typing_cycle())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.typing_task:
            self.typing_task.cancel()


@dp.message_handler()
@exception_sorry()
async def answer(message: types.Message, state: FSMContext, *args, **kwargs):
    # data = await state.get_data()
    if message.from_user.username in CONFIG['allowed_users']:

        text = message.text.strip()
        found = list(filter(lambda x: x[1]['name'] == text, PERSONALITIES.items()))
        if len(found) == 1:
            await message.answer(f"Теперь можешь просто писать, спрашивать что угодно и тд. "
                                 f"Для перезапуска - /reset. Удачи!",
                                 reply_markup=types.ReplyKeyboardRemove())
            await state.update_data({'pers': found[0][0], 'history': []})
            await UserState.communication.set()
        else:
            await message.answer(f"Ты должен выбрать персонажа для общения."
                                 f"\nУказанного персонажа не найдено, если считаешь это ошибкой пиши @hivaze",
                                 reply_markup=types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP))


@dp.message_handler(state=UserState.communication)
@exception_sorry()
@dp.async_task
async def answer(message: types.Message, state: FSMContext, *args, **kwargs):
    data = await state.get_data()

    pers = data.get('pers')
    history = data.get('history') or []
    history = history + [{"role": "user", "content": message.text}]

    if len(history) > CONFIG['last_messages_count']:
        history = history[-CONFIG['last_messages_count']:]

    async with TypingBlock(message.chat):
        prompt = PERSONALITIES[pers]['context']
        ai_message = await asyncio.get_event_loop().run_in_executor(None, create_message, prompt, history)

    await message.reply(ai_message)

    logger.info(f"Отправлен очередной ответ юзеру {message.from_user.username}, бот {pers}")

    history = history + [{"role": "assistant", "content": ai_message}]
    history = history[-CONFIG['last_messages_count']:]

    await state.update_data({'history': history})
