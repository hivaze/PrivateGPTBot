import json
import logging
from concurrent.futures import ThreadPoolExecutor

from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.executor import Executor
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

logger = logging.getLogger(__name__)

with open('resources/config.json') as file:
    CONFIG = json.load(file)
    logger.info(f"Main config loaded. Last messages count: {CONFIG['last_messages_count']}")

with open('resources/personalities.json') as file:
    PERSONALITIES = json.load(file)
    logger.info(f"Personalities config loaded. Count: {len(PERSONALITIES.keys())}")

with open('resources/messages.json') as file:
    MESSAGES = json.load(file)
    logger.info(f"Messaged config loaded.")

PERSONALITIES_REPLY_MARKUP = [types.KeyboardButton(v['name']) for k, v in PERSONALITIES.items()]
PERSONALITIES_REPLY_MARKUP = [PERSONALITIES_REPLY_MARKUP[i:i + 2] for i in range(0, len(PERSONALITIES_REPLY_MARKUP), 2)]


bot = Bot(token=CONFIG['TG_BOT_TOKEN'])
dp = Dispatcher(bot, storage=MemoryStorage())
thread_pool = ThreadPoolExecutor(max_workers=None, thread_name_prefix='gpt_tg_bot')


class UserState(StatesGroup):
    menu = State()
    communication = State()


async def reset_user_state(state):
    await state.reset_data()
    await UserState.menu.set()


def run_pooling():
    executor = Executor(dispatcher=dp)
    executor.start_polling(dp)
