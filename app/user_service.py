from aiogram.dispatcher.filters.state import StatesGroup, State

from app.bot import CONFIG, USERS


class UserState(StatesGroup):
    menu = State()
    custom_pers_setup = State()
    communication = State()
    admin_message = State()


async def reset_user_state(state):
    await state.reset_data()
    await UserState.menu.set()


def check_user_permission(user_name) -> bool:
    return user_name in CONFIG['allowed_users'] or user_name == CONFIG['admin'] or CONFIG['global_mode']


def check_is_admin(user_name):
    return user_name == CONFIG['admin']


def save_user(user_name, chat_id):
    USERS[user_name] = chat_id
