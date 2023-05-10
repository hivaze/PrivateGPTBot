import json
import logging
from datetime import datetime
import numpy as np

from aiogram import types
from aiogram.dispatcher import FSMContext

from app.bot import settings, dp
from app.bot_utils import build_menu_markup
from app.exceptions_handler import exception_sorry
from app.user_service import reset_user_state, UserState, check_user_access, \
    check_is_admin, ban_username, has_tokens_package,\
    init_tokens_package, get_or_create_user, get_all_users, get_all_messages

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@exception_sorry()
async def welcome_user(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_user_access(tg_user):

        await reset_user_state(tg_user, state)

        if message.get_command() != '/reset':
            text = settings.messages['welcome']['with_access']
            logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access initialized the bot.")
        else:
            text = settings.messages['welcome']['reset']
            logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access reset the bot.")

        reply_message = {
            'text': text,
            'reply_markup': build_menu_markup(tg_user.username)
        }
    else:
        reply_message = {
            'text': settings.messages['welcome']['no_access']
        }
        logger.warning(f"User '{tg_user.username}' | '{tg_user.id}' without access tries to use the bot!")

    await message.answer(**reply_message)


@dp.message_handler(commands=["sendMessage"], state=UserState.menu)
@exception_sorry()
async def send_message(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    do_markdown = message.text.split(' ').__len__() > 1

    if check_is_admin(tg_user):
        await UserState.admin_message.set()
        await state.update_data({'do_markdown': do_markdown})
        reply_message = {
            'text': f'In the next message, write a message that will be sent to all known users.'
                    f' Users count: {len(get_all_users())}',
            'reply_markup': types.ReplyKeyboardRemove()
        }
        await message.answer(**reply_message)


@dp.message_handler(commands=["ban"], state=UserState.menu)
@exception_sorry()
async def ban(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        user_name = message.text.split(' ')[1]
        if ban_username(user_name):
            reply_message = {
                'text': f'User {user_name} successfully banned!'
            }
        else:
            reply_message = {
                'text': f'User {user_name} does not exists banned, maybe does not exits.'
            }
        await message.answer(**reply_message)


@dp.message_handler(commands=["status"], state=UserState.menu)
@exception_sorry()
async def ban(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        all_messages = get_all_messages()
        today_messages = [m for m in all_messages if m.executed_at.date() == datetime.today().date()]
        total_used_tokens = np.array([m.used_tokens for m in all_messages])
        all_users = get_all_users()
        today_new_users = [user for user in all_users if user.joined_at.date() == datetime.today().date()]
        reply_message = {
            'text': f'Chatbot status:\n\n'
                    f'Total users count: {len(all_users)}\n'
                    f'Today new users: {len(today_new_users)}\n\n'
                    f'Total messages count: {len(all_messages)}\n'
                    f'Today total messages: {len(today_messages)}\n\n'
                    f'Total used tokens: {total_used_tokens.sum()}\n'
                    f'Average used tokens (per message): {total_used_tokens.mean()}'
        }
        await message.answer(**reply_message)


@dp.message_handler(commands=["reload"], state=UserState.menu)
@exception_sorry()
async def reload(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        settings.load_configs()
        reply_message = {
            'text': 'Configs reloaded. Main config:\n\n' + json.dumps(settings.config, indent=2)
        }
        await message.answer(**reply_message)
