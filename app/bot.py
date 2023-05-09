import json
import logging
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.executor import Executor

logger = logging.getLogger(__name__)


class BotSettings:

    config = {}
    personalities = {}
    messages = {}
    tokens_packages = {}

    def __init__(self):
        self.load_configs()

    def load_configs(self, *args, **kwargs):

        with open('resources/config.json') as file:
            self.config.update(json.load(file))
            logger.info(f"Main config loaded. Last messages count: {self.config['last_messages_count']}")

        with open('resources/personalities.json') as file:
            self.personalities.update(json.load(file))
            logger.info(f"Personalities config loaded. Count: {len(self.personalities.keys())}")

        with open('resources/messages.json') as file:
            self.messages.update(json.load(file))
            logger.info(f"Messaged config loaded.")

        with open('resources/tokens_packages.json') as file:  # Dumb way to store users, must be changed to Postgres
            self.tokens_packages.update(json.load(file))
            logger.info(f"Tokens packages config loaded.")


settings = BotSettings()

bot = Bot(token=settings.config['TG_BOT_TOKEN'])
dp = Dispatcher(bot, storage=MemoryStorage())

thread_pool = ThreadPoolExecutor(max_workers=None, thread_name_prefix='gpt_tg_bot')


def run_pooling():
    executor = Executor(dispatcher=dp)
    # executor.on_shutdown(settings.save_users_data, polling=True, webhook=False)
    executor.start_polling(dp)
