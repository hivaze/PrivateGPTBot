import logging
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils.executor import Executor

from app import settings
from app.utils.general import LRUMutableMemoryStorage

tg_bot = Bot(token=settings.config.TG_BOT_TOKEN)
memory = LRUMutableMemoryStorage(max_entries=settings.config.bot_max_users_memory)
dp = Dispatcher(tg_bot, storage=memory)
# dp.setup_middleware(LoggingMiddleware())

thread_pool = ThreadPoolExecutor(max_workers=None, thread_name_prefix='gpt_tg_bot')


def run_pooling():
    executor = Executor(dispatcher=dp)
    # executor.on_shutdown(settings.save_users_data, polling=True, webhook=False)
    executor.start_polling(dp)

