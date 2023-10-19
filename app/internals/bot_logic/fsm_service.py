import asyncio

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy.orm import Session

from app import settings
from app.database.chroma_db_service import create_vector_store
from app.database.sql_db_service import UserEntity
from app.database.entity_services.messages_service import get_last_message
from app.utils.tg_bot_utils import clean_last_message_markup, delete_settings_message


class UserState(StatesGroup):
    menu = State()
    custom_pers_setup = State()
    feedback = State()
    communication = State()
    admin_message = State()


async def setup_data(user: UserEntity, state: FSMContext):
    # Reset all possible fields in user state
    await state.set_data({
        'history': None,
        'personality': None,
        'custom_prompt': None,
        'documents': [],
        'vectorstore': create_vector_store(user.user_id),
        'messaging_lock': asyncio.Lock(),
        'instant_messages_buffer': None,
        'generation_task': None,
        'last_settings_message_id': None
    })


async def switch_to_communication_state(message, state, language_code):
    await message.answer(settings.messages.communication_start[language_code],
                         reply_markup=ReplyKeyboardRemove())
    await delete_settings_message(state, message.chat.id)
    await UserState.communication.set()


async def reset_user_state(session: Session, user: UserEntity, state: FSMContext):

    current_data = await state.get_data()
    if current_data.get('generation_task'):
        current_data.get('generation_task').cancel()

    last_message = get_last_message(session, user)
    if last_message is not None:
        await clean_last_message_markup(user, last_message)

    await state.reset_data()
    await UserState.menu.set()

    await setup_data(user, state)
