import json
import logging

from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.executor import Executor
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

logger = logging.getLogger(__name__)

with open('resources/config.json') as file:
    CONFIG = json.load(file)
    logger.info(f"Main config loaded. Last messages count: {CONFIG['last_messages_count']}")

with open('resources/personalities.json') as file:
    PERSONALITIES = json.load(file)
    logger.info(f"Personalities config loaded. Count: {len(PERSONALITIES.keys())}")


bot = Bot(token=CONFIG['TG_BOT_TOKEN'])
dp = Dispatcher(bot, storage=MemoryStorage())
executor = Executor(dispatcher=dp)


class UserState(StatesGroup):
    communication = State()


def run_pooling():
    executor.start_polling(dp)
