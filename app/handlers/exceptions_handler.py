import asyncio
import sys
import typing
import logging
import inspect

from aiogram import types as aiogram_types

from app import settings
from app.utils.bot_utils import format_language_code


def zero_exception(fn: typing.Callable):
    _name = fn_name(fn)
    assert inspect.iscoroutinefunction(fn), "Only async functions supported"

    async def inner(message: aiogram_types.Message, *args, **kwargs):
        try:
            await fn(message, *args, **kwargs)
        except asyncio.CancelledError:
            logging.warning(f"Coroutine {_name} was cancelled. Live is different", _name)
        except (SystemExit, KeyboardInterrupt, GeneratorExit):
            raise
        except Exception as e:
            logging.error(f'{e} while call {_name}', exc_info=sys.exc_info())

            tg_user = message.from_user
            lc = format_language_code(tg_user.language_code)

            if isinstance(message, aiogram_types.Message):
                await message.answer(text=settings.messages.error[lc])
            if isinstance(message, aiogram_types.CallbackQuery):
                await message.message.answer(text=settings.messages.error[lc])

    return inner


def fn_name(fn) -> str:
    """
    Returns callable dotted name including module
    """
    parts = [fn.__module__]
    if hasattr(fn, '__qualname__'):
        parts.append(fn.__qualname__)
    return '.'.join(parts)
