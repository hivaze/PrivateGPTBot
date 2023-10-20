import logging
from datetime import datetime

import numpy as np
from aiogram import types
from aiogram.dispatcher import FSMContext
from sqlalchemy.orm import Session

from app import settings
from app.bot import dp, tg_bot
from app.database.sql_db_service import with_session, UserEntity
from app.database.entity_services.messages_service import get_all_messages, get_avg_hist_size_by_user, \
    get_avg_tokens_by_user, \
    get_avg_tokens_per_message, get_avg_messages_by_user
from app.database.entity_services.tokens_service import tokens_barrier, add_new_tokens_package, find_tokens_package
from app.database.entity_services.users_service import access_check, check_is_admin, get_all_users, \
    get_user_by_id, set_ban_userid, get_users_with_filters
from app.handlers.exceptions_handler import zero_exception
from app.internals.bot_logic.fsm_service import reset_user_state, UserState
from app.utils.tg_bot_utils import build_menu_markup, format_language_code, build_price_markup

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["start", "reset"], state='*')
@zero_exception
@with_session
@access_check
async def welcome_user(session: Session, user: UserEntity,
                       message: types.Message, state: FSMContext,
                       *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    await reset_user_state(session, user, state)

    if not await tokens_barrier(session, user):
        return

    if message.get_command() != '/reset':
        text = settings.messages.welcome.with_access[lc]
        logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access initialized the bot.")
    else:
        text = settings.messages.reset[lc]
        logger.info(f"User '{tg_user.username}' | '{tg_user.id}' with access reset the bot.")

    reply_message = {
        'text': text,
        'reply_markup': build_menu_markup(lc),
        'parse_mode': 'HTML'
    }
    await message.answer(**reply_message)


@dp.message_handler(commands=["account"], state='*')
@zero_exception
@with_session
@access_check
async def account_status(session: Session, user: UserEntity,
                         message: types.Message, state: FSMContext,
                         *args, **kwargs):
    lc = format_language_code(user.language_code)

    for_other = message.text.split(' ').__len__() > 1

    if for_other and check_is_admin(user.user_name):
        other_id = int(message.text.split(' ')[1])
        user = get_user_by_id(session, other_id)
        if user is None:
            await message.answer(f'User {other_id} does not exits')
            return

    tokens_package = find_tokens_package(session, user.user_id)
    tokens_package_config = settings.tokens_packages.get(tokens_package.package_name, 'default')

    messages = user.messages
    used_tokens = sum([m.total_tokens for m in messages])
    avg_t_m = max(min(get_avg_tokens_per_message(session) or 1500, 3000), 1500)

    long_context = settings.messages.confirmation.yes[lc] if tokens_package_config.long_context else settings.messages.confirmation.no[lc]
    superior_model = settings.messages.confirmation.yes[lc] if tokens_package_config.superior_model else settings.messages.confirmation.no[lc]
    functions = settings.messages.confirmation.yes[lc] if tokens_package_config.use_functions else settings.messages.confirmation.no[lc]

    info_message = settings.messages.account_info[lc]
    info_message = info_message.format(registration_date=user.joined_at.strftime("%Y-%m-%d %H:%M"),
                                       messages_count=len(messages),
                                       used_tokens=used_tokens,
                                       left_tokens=tokens_package.left_tokens,
                                       approx_messages=tokens_package.left_tokens // avg_t_m,
                                       tokens_package_name=tokens_package.package_name.upper(),
                                       expires_at=tokens_package.expires_at.strftime("%Y-%m-%d %H:%M"),
                                       functions=functions,
                                       long_context=long_context,
                                       superior_model=superior_model)

    await message.answer(info_message, parse_mode='HTML')


@dp.message_handler(commands=["price_list"], state='*')
@zero_exception
@with_session
@access_check
async def price_list(session: Session, user: UserEntity,
                     message: types.Message, state: FSMContext,
                     *args, **kwargs):

    lc = format_language_code(user.language_code)
    current_package = find_tokens_package(session, user.user_id)
    avg_t_m = max(min(get_avg_tokens_per_message(session) or 1500, 3000), 1500)

    await message.answer(settings.messages.price_list.info[lc].format(package_name=current_package.package_name.upper()),
                         parse_mode='HTML')

    for name, package in settings.tokens_packages.items():
        if package.level < 2:
            continue

        long_context = settings.messages.confirmation.yes[lc] if package.long_context else settings.messages.confirmation.no[lc]
        superior_model = settings.messages.confirmation.yes[lc] if package.superior_model else settings.messages.confirmation.no[lc]
        functions = settings.messages.confirmation.yes[lc] if package.use_functions else settings.messages.confirmation.no[lc]
        superior_as_default = settings.messages.confirmation.yes[lc] if package.use_superior_as_default else settings.messages.confirmation.no[lc]

        info = settings.messages.price_list.package_info[lc].format(name=name.upper(),
                                                                    tokens=package.tokens,
                                                                    approx_messages=package.tokens // avg_t_m,
                                                                    duration=package.duration,
                                                                    price=package.price,
                                                                    long_context=long_context,
                                                                    superior_model=superior_model,
                                                                    superior_model_as_default=superior_as_default,
                                                                    functions=functions)
        await message.answer(info, parse_mode='HTML', reply_markup=build_price_markup(lc, name, package.price))


@dp.message_handler(commands=["grant_package"], state='*')
@zero_exception
@with_session
@access_check
async def grant_package(session: Session, user: UserEntity,
                        message: types.Message, state: FSMContext,
                        *args, **kwargs):
    if check_is_admin(user.user_name):
        other_id = int(message.text.split(' ')[1])
        package_name = message.text.split(' ')[2]
        other_user = get_user_by_id(session, other_id)
        if other_user:
            lc = format_language_code(other_user.language_code)
            add_new_tokens_package(session, other_id, package_name)
            await message.answer(
                f"Package {package_name} granted to user '{other_user.user_id}' | '{other_user.user_name}'!")
            await tg_bot.send_message(other_user.user_id,
                                      settings.messages.tokens.granted[lc].format(package_name=package_name.upper()),
                                      parse_mode='HTML')
        else:
            await message.answer(f'User {other_id} does not exits')


@dp.message_handler(commands=["send_message"], state=UserState.menu)
@zero_exception
@with_session
async def send_message(session: Session,
                       message: types.Message, state: FSMContext,
                       *args, **kwargs):
    tg_user = message.from_user
    do_html = message.text.split(' ').__len__() > 1

    if check_is_admin(tg_user.username):
        await UserState.admin_message.set()
        await state.update_data({'do_html': do_html})
        reply_message = {
            'text': f'In the next message, write a message that will be sent to all known users.'
                    f' Users count: {len(get_users_with_filters(session))}',
            'reply_markup': types.ReplyKeyboardRemove()
        }
        await message.answer(**reply_message)


# @dp.message_handler(commands=["send_db"], state=UserState.menu)
# @zero_exception
# async def send_db_file(message: types.Message, state: FSMContext,
#                        *args, **kwargs):
#     tg_user = message.from_user
#
#     if check_is_admin(tg_user.username):
#         await message.answer(text="DB file preparing...")
#         await send_db(tg_user)


@dp.message_handler(commands=["ban"], state=UserState.menu)
@zero_exception
@with_session
async def ban(session: Session,
              message: types.Message, state: FSMContext,
              *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user.username):
        user_id = int(message.text.split(' ')[1])
        if set_ban_userid(session, user_id, True):
            reply_message = {
                'text': f'User {user_id} successfully forced banned!'
            }
        else:
            reply_message = {
                'text': f'User {user_id} does not banned, maybe does not exits.'
            }
        await message.answer(**reply_message)


@dp.message_handler(commands=["unban"], state=UserState.menu)
@zero_exception
@with_session
async def unban(session: Session,
                message: types.Message, state: FSMContext,
                *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user.username):
        other_id = int(message.text.split(' ')[1])
        if set_ban_userid(session, other_id, False):
            reply_message = {
                'text': f'User {other_id} successfully forced unbanned!'
            }
        else:
            reply_message = {
                'text': f'User {other_id} does not unbanned, maybe does not exits.'
            }
        await message.answer(**reply_message)


@dp.message_handler(commands=["status"], state='*')
@zero_exception
@with_session
async def status(session: Session,
                 message: types.Message, state: FSMContext,
                 *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user.username):
        all_messages = get_all_messages(session)
        today_messages = [m for m in all_messages if m.executed_at.date() == datetime.today().date()]
        today_unique_users = np.unique([m.user_id for m in today_messages])
        week_messages = [m for m in all_messages if (datetime.today() - m.executed_at).days < 7]
        week_unique_users = np.unique([m.user_id for m in week_messages])
        all_users = get_all_users(session)
        filtered_users = get_users_with_filters(session)
        today_new_users = [user for user in all_users if user.joined_at.date() == datetime.today().date()]
        week_new_users = [user for user in all_users if (datetime.today() - user.joined_at).days < 7]
        reply_message = {
            'text': f'<b>Chatbot status</b>\n\n'
                    f'<i>Users:</i>\n\n'
                    f'Total users count: {len(all_users)}\n'
                    f'Users count with GM and no ban: {len(filtered_users)}\n'
                    f'Week new users: {len(week_new_users)}\n'
                    f'Week unique users: {len(week_unique_users)}\n'
                    f'Today new users: {len(today_new_users)}\n'
                    f'Today unique users: {len(today_unique_users)}\n\n'
                    f'<i>Messages:</i>\n\n'
                    f'Total messages count: {len(all_messages)}\n'
                    f'Week messages count: {len(week_messages)}\n'
                    f'Week avg. user messages count: {round(get_avg_messages_by_user(session), 2)}\n'
                    f'Today messages count: {len(today_messages)}\n'
                    f'Week avg. user history size: {round(get_avg_hist_size_by_user(session), 2)}\n\n'
                    f'<i>Tokens:</i>\n\n'
                    f'Today total used tokens: {sum([m.total_tokens for m in today_messages])}\n'
                    f'Week avg. user used tokens: {round(get_avg_tokens_by_user(session), 2)}\n'
                    f'Week avg. message used tokens: {round(get_avg_tokens_per_message(session), 2)}'
        }
        await message.answer(**reply_message, parse_mode='HTML')


@dp.message_handler(commands=["reload"], state=UserState.menu)
@zero_exception
async def reload(message: types.Message, state: FSMContext,
                 *args, **kwargs):
    tg_user = message.from_user

    if check_is_admin(tg_user.username):
        settings.load()
        await message.answer('Configs reloaded.\n\nModels config:\n' + str(settings.config.models))
