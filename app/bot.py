from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher
from aiogram.utils.executor import Executor

from app import settings
from app.internals.bot_logic.bot_memory import LRUMutableMemoryStorage
from app.internals.chat.chat_models import load_chat_model
from app.utils.tg_bot_utils import session_auto_ended

tg_bot = Bot(token=settings.config.TG_BOT_TOKEN)
memory = LRUMutableMemoryStorage(max_entries=settings.config.bot_max_users_memory,
                                 non_copy_keys=['messaging_lock', 'generation_task'],
                                 on_auto_remove=session_auto_ended)
dp = Dispatcher(tg_bot, storage=memory)
# dp.setup_middleware(LoggingMiddleware())

thread_pool = ThreadPoolExecutor(max_workers=None, thread_name_prefix='gpt_tg_bot')

small_context_model = load_chat_model(settings.config.models.small_context)
long_context_model = load_chat_model(settings.config.models.long_context)
superior_model = load_chat_model(settings.config.models.superior)


def run_pooling():
    executor = Executor(dispatcher=dp)
    executor.start_polling(dp)

