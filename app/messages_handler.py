import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.bot import dp, CONFIG, PERSONALITIES, UserState, reset_user_state, PERSONALITIES_REPLY_MARKUP, thread_pool
from app.exceptions_handler import exception_sorry
from app.open_ai_client import create_message, truncate_user_history, count_tokens

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
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                pass

        self.typing_task = asyncio.create_task(typing_cycle())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.typing_task:
            self.typing_task.cancel()


@dp.message_handler(state=None)
@exception_sorry()
async def answer(message: types.Message, state: FSMContext, *args, **kwargs):
    if message.from_user.username in CONFIG['allowed_users']:
        await reset_user_state(state)
        await message.answer(f"Вероятно бот был перезагружен или обновлен. Снова выбери персонажа.",
                             reply_markup=types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP))


@dp.message_handler(state=UserState.menu)
@exception_sorry()
async def answer(message: types.Message, state: FSMContext, *args, **kwargs):

    text = message.text.strip()
    found = list(filter(lambda x: x[1]['name'] == text, PERSONALITIES.items()))
    if len(found) == 1:
        await message.answer(f"Теперь можешь просто писать, спрашивать что угодно и тд. "
                             f"Для перезапуска - /start или /reset. Удачи!",
                             reply_markup=types.ReplyKeyboardRemove())
        await state.update_data({'pers': found[0][0], 'history': []})
        await UserState.communication.set()
    else:
        await message.answer(f"Ты должен выбрать персонажа для общения."
                             f"\nУказанного персонажа не найдено, если считаешь это ошибкой пиши @hivaze",
                             reply_markup=types.ReplyKeyboardMarkup(keyboard=PERSONALITIES_REPLY_MARKUP))


@dp.message_handler(state=UserState.communication)
@exception_sorry()
async def answer(message: types.Message, state: FSMContext, *args, **kwargs):
    current_data = await state.get_data()
    user_name = message.from_user.username

    pers = current_data.get('pers')
    pers_prompt = PERSONALITIES[pers]['context']

    orig_history = current_data.get('history') or []
    history = orig_history + [{"role": "user", "content": message.text}]

    previous_tokens_usage = current_data.get('prev_tokens_usage') or 0
    previous_tokens_usage += count_tokens(message.text)  # maybe +10? (openai...)

    history = history[-CONFIG['last_messages_count']:]
    history, removed_tokens = truncate_user_history(user_name, pers_prompt, history, previous_tokens_usage)

    async with TypingBlock(message.chat):
        ai_message, tokens_usage = await asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                                  create_message,
                                                                                  user_name, pers_prompt, history)
    ready_message = ai_message

    if removed_tokens > 0:
        ready_message += f"\n\n-----------------------\n" \
                         "Так как размер истории сообщений довольно большой, " \
                         f"из истории сообщений было удалено {removed_tokens} токенов, " \
                         f"но вы вероятно этого не заметите, присылайте текста короче."

    if CONFIG['append_tokens_count']:
        ready_message += f"\n\n-----------------------\n" \
                        f"Размер вашего сообщения: {count_tokens(message.text)}\n" \
                        f"Токенов в истории: {tokens_usage}"

    await message.reply(ready_message)

    logger.info(f"Another reply to user '{user_name}' sent, personality '{pers}'")

    updated_data = await state.get_data()  # may be already changed due concurrency
    if updated_data.get('pers') == pers:
        # updated_history = updated_data.get('history') or []
        updated_history = history + [
            # {"role": "user", "content": message.text},
            {"role": "assistant", "content": ai_message}
        ]

        # Debug breaks users privacy here! Disable it in general use!
        logger.debug(f'History of user {message.from_user.username}: {updated_history}')

        await state.update_data({'history': updated_history, 'prev_tokens_usage': tokens_usage})
