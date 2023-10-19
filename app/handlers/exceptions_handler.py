import asyncio
import sys
import typing
import logging
import inspect
from datetime import datetime

from aiogram import types as aiogram_types

from app import settings
from app.database.sql_db_service import session_factory, FailedCommunicationEntity
from app.utils.tg_bot_utils import format_language_code
import traceback

logger = logging.getLogger(__name__)


async def save_failed_state(user_id: int, exception_message: str, trace: str):
    with session_factory() as session:
        try:
            happened_at = datetime.now()
            fc = FailedCommunicationEntity(user_id=user_id,
                                           happened_at=happened_at,
                                           exception_message=exception_message,
                                           traceback=trace)
            session.add(fc)
        except Exception as e:
            session.rollback()
            logger.warning(f"Can't save failed state for user {user_id}, error: {e}!!!")
        else:
            session.commit()
        session.close()


def zero_exception(fn: typing.Callable):
    _name = fn_name(fn)
    assert inspect.iscoroutinefunction(fn), "Only async functions supported"

    async def inner(message: aiogram_types.Message, *args, **kwargs):
        try:
            await fn(message=message, *args, **kwargs)
        except asyncio.CancelledError:
            logger.warning(f"Coroutine {_name} was cancelled. Live is different", _name)
        except (SystemExit, KeyboardInterrupt, GeneratorExit):
            raise
        except Exception as e:
            logger.error(f'{e} while call {_name}', exc_info=sys.exc_info())

            tg_user = message.from_user
            lc = format_language_code(tg_user.language_code)

            if isinstance(message, aiogram_types.Message):
                await message.answer(text=settings.messages.error[lc])
            if isinstance(message, aiogram_types.CallbackQuery):
                await message.message.answer(text=settings.messages.error[lc])

            exception_message, trace = str(e), traceback.format_exc(limit=5, chain=True)
            await save_failed_state(message.from_user.id, exception_message, trace)

    return inner


def fn_name(fn) -> str:
    """
    Returns callable dotted name including module
    """
    parts = [fn.__module__]
    if hasattr(fn, '__qualname__'):
        parts.append(fn.__qualname__)
    return '.'.join(parts)
