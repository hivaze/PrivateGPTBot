import asyncio
import typing
import logging
import inspect

from aiogram import types as aiogram_types

from app.bot import settings

SORRY_TEXT = settings.messages['error']


def exception_sorry():

    def wrapper(fn: typing.Callable):
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
                logging.error(f'{e} while call {_name}')

                if isinstance(message, aiogram_types.Message):
                    await message.reply(text=SORRY_TEXT)
                if isinstance(message, aiogram_types.CallbackQuery):
                    await message.message.reply(text=SORRY_TEXT)
        return inner

    return wrapper


def fn_name(fn) -> str:
    """
    Returns callable dotted name including module
    """
    parts = [fn.__module__]
    if hasattr(fn, '__qualname__'):
        parts.append(fn.__qualname__)
    return '.'.join(parts)
