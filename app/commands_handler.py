import json
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.exceptions_handler import exception_sorry
from app.bot import dp, CONFIG, MESSAGES, USERS, build_reply_markup, load_configs, save_users_data
from app.user_service import reset_user_state, check_user_permission, UserState, check_is_admin, save_user

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@exception_sorry()
async def welcome_user(message: types.Message, state: FSMContext, *args, **kwargs):
    user_name = message.from_user.username

    if check_user_permission(user_name):
        await reset_user_state(state)
        save_user(user_name, message.chat.id)  # save user on start

        if message.get_command() != '/reset':
            text = MESSAGES['welcome']['with_access']
            logger.info(f"User '{user_name}' with access initialized the bot.")
        else:
            text = MESSAGES['welcome']['reset']
            logger.info(f"User '{user_name}' with access reset the bot.")

        reply_message = {
            'text': text,
            'reply_markup': build_reply_markup(user_name)
        }
    else:
        reply_message = {
            'text': MESSAGES['welcome']['no_access']
        }
        logger.warning(f"User '{user_name}' without access tries to use the bot!")

    await message.answer(**reply_message)


@dp.message_handler(commands=["sendMessage"], state=UserState.menu)
@exception_sorry()
async def send_message(message: types.Message, state: FSMContext, *args, **kwargs):
    user_name = message.from_user.username

    if check_is_admin(user_name):
        await UserState.admin_message.set()
        reply_message = {
            'text': f'In the next message, write a message that will be sent to all known users.'
                    f' Users count: {len(USERS)}',
            'reply_markup': types.ReplyKeyboardRemove()
        }
        await message.answer(**reply_message)


@dp.message_handler(commands=["reload"], state=UserState.menu)
@exception_sorry()
async def reload(message: types.Message, state: FSMContext, *args, **kwargs):
    user_name = message.from_user.username

    if check_is_admin(user_name):
        await save_users_data()
        load_configs()
        reply_message = {
            'text': 'Configs reloaded. Main config:\n\n' + json.dumps(CONFIG, indent=2)
        }
        await message.answer(**reply_message)
