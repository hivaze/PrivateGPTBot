import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.executor import Executor

logger = logging.getLogger(__name__)

CONFIG, PERSONALITIES, MESSAGES, USERS = {}, {}, {}, {}


def build_reply_markup(user_name):
    markup = [types.KeyboardButton(v['name']) for k, v in PERSONALITIES.items()]
    markup = [markup[i:i + 2] for i in range(0, len(markup), 2)]
    return types.ReplyKeyboardMarkup(keyboard=markup)


def load_configs(*args, **kwargs):

    with open('resources/config.json') as file:
        CONFIG.update(json.load(file))
        logger.info(f"Main config loaded. Last messages count: {CONFIG['last_messages_count']}")

    with open('resources/personalities.json') as file:
        PERSONALITIES.update(json.load(file))
        logger.info(f"Personalities config loaded. Count: {len(PERSONALITIES.keys())}")

    with open('resources/messages.json') as file:
        MESSAGES.update(json.load(file))
        logger.info(f"Messaged config loaded.")

    with open('resources/users_data.json') as file:  # Dumb way to store users, must be changed to Postgres
        USERS.update(json.load(file))
        logger.info(f"Users file loaded. Count: {len(USERS.keys())}")


async def save_users_data(*args, **kwargs):
    logger.info('Saving users data...')
    with open('resources/users_data.json', 'w') as outfile:
        json.dump(USERS, outfile)
    logger.info('Users data saved!')


load_configs()  # Entrypoint configs loading

bot = Bot(token=CONFIG['TG_BOT_TOKEN'])
dp = Dispatcher(bot, storage=MemoryStorage())
thread_pool = ThreadPoolExecutor(max_workers=None, thread_name_prefix='gpt_tg_bot')


async def global_message(text: str):
    logger.info(f"Admin initialized global message:\n{text[:30]}...")
    await asyncio.gather(*[bot.send_message(chat_id, text, parse_mode='Markdown')
                           for tg_name, chat_id in USERS.items()])


def run_pooling():
    executor = Executor(dispatcher=dp)
    executor.on_shutdown(save_users_data, polling=True, webhook=False)
    executor.start_polling(dp)
