import json
import logging
from datetime import datetime

from aiogram import types
from aiogram.dispatcher import FSMContext
from sqlalchemy.orm import Session

from app import settings
from app.bot import dp
from app.utils.bot_utils import build_menu_markup, send_db
from app.database.db_service import with_session
from app.database.messages_service import get_all_messages, get_avg_hist_size_by_user, get_avg_tokens_by_user, \
    get_avg_tokens_per_message, get_avg_messages_by_user
from app.database.users_service import check_user_access, reset_user_state, UserState, check_is_admin, get_all_users, \
    ban_username, get_or_create_user, get_user_model
from app.handlers.exceptions_handler import zero_exception

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@with_session
@zero_exception
async def welcome_user(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_user_access(session, tg_user):

        user = await reset_user_state(session, tg_user, state)

        model_config = get_user_model(user)

        if message.get_command() != '/reset':
            text = settings.messages.welcome.with_access.format(model_name=model_config.model_name)
            logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access initialized the bot.")
        else:
            text = settings.messages.welcome.reset
            logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access reset the bot.")

        reply_message = {
            'text': text,
            'reply_markup': build_menu_markup(tg_user.username)
        }
    else:
        reply_message = {
            'text': settings.messages.welcome.no_access
        }
        logger.warning(f"User '{tg_user.username}' | '{tg_user.id}' without access tries to use the bot!")

    await message.answer(**reply_message)


@dp.message_handler(commands=["send_message"], state=UserState.menu)
@with_session
@zero_exception
async def send_message(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    do_markdown = message.text.split(' ').__len__() > 1

    if check_is_admin(tg_user):
        await UserState.admin_message.set()
        await state.update_data({'do_markdown': do_markdown})
        reply_message = {
            'text': f'In the next message, write a message that will be sent to all known users.'
                    f' Users count: {len(get_all_users(session))}',
            'reply_markup': types.ReplyKeyboardRemove()
        }
        await message.answer(**reply_message)


@dp.message_handler(commands=["send_db"], state=UserState.menu)
@zero_exception
async def send_db_file(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        await message.answer(text="DB file preparing...")
        await send_db(tg_user)


@dp.message_handler(commands=["ban"], state=UserState.menu)
@with_session
@zero_exception
async def ban(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        user_name = message.text.split(' ')[1]
        if ban_username(session, user_name):
            reply_message = {
                'text': f'User {user_name} successfully banned!'
            }
        else:
            reply_message = {
                'text': f'User {user_name} does not exists banned, maybe does not exits.'
            }
        await message.answer(**reply_message)


@dp.message_handler(commands=["status"], state=UserState.menu)
@with_session
@zero_exception
async def status(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        all_messages = get_all_messages(session)
        today_messages = [m for m in all_messages if m.executed_at.date() == datetime.today().date()]
        week_messages = [m for m in all_messages if (datetime.today() - m.executed_at).days < 7]
        all_users = get_all_users(session)
        today_new_users = [user for user in all_users if user.joined_at.date() == datetime.today().date()]
        week_new_users = [user for user in all_users if (datetime.today() - user.joined_at).days < 7]
        reply_message = {
            'text': f'**Chatbot status**\n\n'
                    f'__Users:__\n\n'
                    f'Total users count: {len(all_users)}\n'
                    f'Week new users: {len(week_new_users)}\n'
                    f'Today new users: {len(today_new_users)}\n\n'
                    f'__Messages:__\n\n'
                    f'Total messages count: {len(all_messages)}\n'
                    f'Week messages count: {len(week_messages)}\n'
                    f'Today total messages: {len(today_messages)}\n'
                    f'Average user history size: {get_avg_hist_size_by_user(session)}\n'
                    f'Average user messages count: {get_avg_messages_by_user(session)}\n\n'
                    f'__Tokens:__\n\n'
                    f'Average user used tokens: {get_avg_tokens_by_user(session)}\n'
                    f'Average message used tokens: {get_avg_tokens_per_message(session)}'
        }
        await message.answer(**reply_message, parse_mode='markdown')


@dp.message_handler(commands=["reload"], state=UserState.menu)
@zero_exception
async def reload(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user):
        settings.load()
        reply_message = {
            'text': 'Configs reloaded. Main config:\n\n' + json.dumps(settings.config, indent=2)
        }
        await message.answer(**reply_message)