import asyncio
import typing
import logging
import inspect

from aiogram import types as aiogram_types


def exception_handler():
    def wrapper(fn: typing.Callable):
        _name = attr_name(fn)
        assert inspect.iscoroutinefunction(fn), "Only async functions supported"

        async def inner(message: aiogram_types.Message, *args, **kwargs):
            try:
                await fn(message, *args, **kwargs)
            except asyncio.CancelledError:
                logging.warning(f"Coroutine {_name} was cancelled. Live is different", _name)
            except (SystemExit, KeyboardInterrupt, GeneratorExit):
                raise
            except Exception as e:
                error_name = attr_name(e.__class__)
                error_text = f'"{error_name}: {e}" in {_name}'
                user_error_text = f'Ошибка: "{error_name}: {e}" при вызове {_name}\n\n' + \
                    "Как видите, что-то сломалось. Попробуйте написать ещё раз, решить проблему своими силами или обратитесь к @hivaze."

                logging.error(error_text)
                if isinstance(message, aiogram_types.Message):
                    await message.reply(text=user_error_text)
                elif isinstance(message, aiogram_types.CallbackQuery):
                    await message.message.reply(text=user_error_text)
        return inner

    return wrapper


def attr_name(attr) -> str:
    """
    Returns dotted name of an attribute (including module)
    """
    parts = [attr.__module__]
    if hasattr(attr, '__qualname__'):
        parts.append(attr.__qualname__)
    return '.'.join(parts)
