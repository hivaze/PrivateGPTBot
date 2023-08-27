import asyncio
import datetime
import logging
import tempfile

from PIL import Image
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import BadRequest
from sqlalchemy.orm import Session

from app import settings
from app.bot import dp, thread_pool
from app.database.db_service import Role, MessageEntity, with_session
from app.database.messages_service import add_message_record
from app.database.tokens_service import check_tokens, TokensUsageStatus, init_tokens_package, tokens_spending
from app.database.users_service import UserState, reset_user_state, check_user_access, get_or_create_user, \
    get_user_model
from app.handlers.exceptions_handler import zero_exception
from app.models_api.blip_captions_model import get_images_captions
from app.models_api.open_ai_client import generate_message, truncate_user_history, count_tokens
from app.utils.bot_utils import global_message, build_menu_markup, build_specials_markup, no_access_message, \
    format_language_code
from app.utils.general import TypingBlock

logger = logging.getLogger(__name__)

FORWARD_MESSAGE_FORMAT = "Forwarded message from {user_name}: {message}"
DEFAULT_MESSAGE_FORMAT = "{message}"


@dp.message_handler(state=UserState.admin_message)
@zero_exception
@with_session
async def admin_message(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    await message.answer('Now your message will be sent to all known users...')

    data = await state.get_data()
    await global_message(session, message.text, do_markdown=data['do_markdown'])
    await message.answer('Done!')

    await reset_user_state(session, tg_user, state)

    reply_message = {
        'text': settings.messages.welcome.reset[lc],
        'reply_markup': build_menu_markup(tg_user)
    }
    await message.answer(**reply_message)


@dp.message_handler(state=UserState.custom_pers_setup)
@zero_exception
async def custom_personality(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    await state.update_data({'custom_prompt': message.text.strip(), 'lock': asyncio.Lock()})
    await UserState.communication.set()
    await message.answer(settings.messages.pers_selection.go[lc])


@dp.message_handler(state=None)
@zero_exception
@with_session
async def default_answer(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    if check_user_access(session, tg_user):
        await reset_user_state(session, tg_user, state)
        await message.answer(settings.messages.bot_reboot[lc],
                             reply_markup=build_menu_markup(tg_user),
                             disable_notification=True)
    else:
        await no_access_message(tg_user, message)


@dp.message_handler(state=UserState.menu)
@zero_exception
async def pers_selection_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    text = message.text.strip()
    all_pers = list(settings.personalities.items())
    found = list(filter(lambda x: x[1].name[lc] == text, all_pers))
    if len(found) == 1:
        await message.answer(settings.messages.pers_selection.go[lc],
                             reply_markup=types.ReplyKeyboardRemove())
        await state.update_data({'pers': found[0][0], "lock": asyncio.Lock()})
        await UserState.communication.set()
    elif text == settings.messages.custom_personality.button[lc]:
        await state.update_data({'pers': 'custom'})
        await UserState.custom_pers_setup.set()
        await message.answer(settings.messages.custom_personality.info[lc],
                             reply_markup=types.ReplyKeyboardRemove())
    elif text == settings.messages.specialties.button[lc]:
        await message.answer(settings.messages.specialties.info[lc],
                             reply_markup=build_specials_markup(tg_user))
        await message.delete()
    elif text == settings.messages.specialties.back_button[lc]:
        await message.answer(settings.messages.pers_selection.info[lc],
                             reply_markup=build_menu_markup(tg_user))
        await message.delete()
    else:
        await message.answer(settings.messages.pers_selection.mistake[lc],
                             reply_markup=build_menu_markup(tg_user))


async def instant_messages_collector(state, message):
    current_user_data = await state.get_data()

    instant_messages_buffer = current_user_data.get('instant_messages_buffer') or []
    if message.is_forward():
        instant_messages_buffer.append(FORWARD_MESSAGE_FORMAT.format(
            user_name=message.forward_from.first_name if message.forward_from else "Unknown",
            message=message.text))
    else:
        instant_messages_buffer.append(DEFAULT_MESSAGE_FORMAT.format(message=message.text))
    await state.update_data({'instant_messages_buffer': instant_messages_buffer})

    await asyncio.sleep(settings.config.instant_messages_waiting / 1000.0)  # waiting in seconds

    current_user_data = await state.get_data()
    new_buffer = current_user_data.get('instant_messages_buffer') or []

    do_answer = len(instant_messages_buffer) == len(new_buffer)
    concatenated_message = None
    if do_answer:
        await state.update_data({'instant_messages_buffer': []})
        concatenated_message = "\n\n".join(instant_messages_buffer)

    return do_answer, len(instant_messages_buffer), concatenated_message, current_user_data.get("lock")


@dp.message_handler(state=UserState.communication)
@zero_exception
@with_session
async def communication_answer(session: Session, message: types.Message,
                               state: FSMContext, is_image=False, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    do_answer, instant_messages_buffer_size, concatenated_message, messages_lock = \
        await instant_messages_collector(state, message)
    if not do_answer:
        return

    await messages_lock.acquire()

    try:  # try-finally block for precise lock release

        # Get or crete user entity
        user = get_or_create_user(session, tg_user)
        model_config = get_user_model(user)

        if user.ban:
            await no_access_message(tg_user, message)
            messages_lock.release()
            return

        # Check if enough tokens
        if check_tokens(session, tg_user.id) != TokensUsageStatus.ALLOWED:
            if user.role != Role.PRIVILEGED and not settings.config.free_mode:
                messages_lock.release()
                return
            else:
                init_tokens_package(session, user)
                logger.info(f"Reinitializing '{tg_user.username}' | '{tg_user.id}' tokens package due PRIVILEGED role "
                            f"or free mode enabled.")

        # Get current user in-memory data
        current_user_data = await state.get_data()

        # Personality prompt
        pers = current_user_data.get('pers')
        pers_prompt = settings.personalities[pers].context \
            if pers != 'custom' else current_user_data.get('custom_prompt')
        pers_prompt = pers_prompt.format(user_name=tg_user.first_name,
                                         dt=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

        # Messages history management
        orig_history = current_user_data.get('history') or []
        history = orig_history + [{"role": "user", "content": concatenated_message}]

        # request loop (do typing)
        async with TypingBlock(message.chat):

            previous_tokens_usage = current_user_data.get('prev_tokens_usage') or 0
            query_tokens = count_tokens(model_config, concatenated_message)
            previous_tokens_usage += query_tokens  # maybe +10? (openai...)

            history = history[-model_config.last_messages_count:]
            history, removed_tokens = truncate_user_history(tg_user.username,
                                                            model_config,
                                                            pers_prompt,
                                                            history,
                                                            previous_tokens_usage)

            ai_message, tokens_usage, ms_time = await asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                                               generate_message,
                                                                                               tg_user.username,
                                                                                               model_config,
                                                                                               pers_prompt,
                                                                                               history)
            add_message_record(session, tg_user.id, MessageEntity(tg_message_id=message.message_id,
                                                                  used_tokens=tokens_usage,
                                                                  personality=pers,
                                                                  history_size=len(history),
                                                                  has_image=is_image,
                                                                  query_tokens=query_tokens,
                                                                  time_taken=ms_time,
                                                                  instant_buffer=instant_messages_buffer_size,
                                                                  model=model_config.model_name,
                                                                  executed_at=datetime.datetime.now()))
            tokens_spending(session, tg_user.id, tokens_usage)

        if instant_messages_buffer_size == 1:
            try:
                sent_message = await message.reply(ai_message)
            except BadRequest:  # Fix for 'Replied message not found'
                sent_message = await message.answer(ai_message)
        else:
            sent_message = await message.answer(ai_message)

        if removed_tokens > 0:
            await sent_message.reply(settings.messages.tokens.notion[lc].format(removed_tokens=removed_tokens),
                                     disable_notification=True)

        if settings.config.append_tokens_count:
            await sent_message.reply(settings.messages.tokens.tokens_count[lc].format(message_size=query_tokens,
                                                                                      tokens_usage=tokens_usage),
                                     disable_notification=True)

        logger.info(f"Another reply to user '{tg_user.username}' | '{tg_user.id}' sent,"
                    f" model: '{model_config.model_name}', personality '{pers}' used tokens: {tokens_usage}")

        # We need to check if pers is the same as in start of the message execution
        new_data = await state.get_data()
        if new_data.get('pers') == pers:
            updated_history = history + [{"role": "assistant", "content": ai_message}]
            await state.update_data({
                'history': updated_history,
                'prev_tokens_usage': tokens_usage
            })
            logger.debug(f'History of user {tg_user.username}: {updated_history}')
    finally:
        messages_lock.release()


@dp.message_handler(state=UserState.communication, content_types=['photo'])
@zero_exception
@with_session
async def photo_answer(session: Session, message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    current_user_data = await state.get_data()
    messages_lock = current_user_data.get("lock", asyncio.Lock())

    user = get_or_create_user(session, tg_user)

    if user.ban:
        await no_access_message(tg_user, message)
        messages_lock.release()
        return

    if message.is_forward():
        await message.reply(settings.messages.image_forward[lc])

        message.text = message.caption
        await asyncio.get_event_loop().create_task(communication_answer(message, state=state, is_image=False))

        return

    file_info = await message.bot.get_file(message.photo[-1].file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:  # temp dir for future support of many photos
        result = await message.bot.download_file(file_path=file_info.file_path,
                                                 destination_dir=tmp_dir)
        result.close()
        image = Image.open(result.name).convert('RGB')

    image_caption = get_images_captions(image)[0]

    pers = current_user_data.get('pers')

    if pers == 'joker':
        chat_gpt_prompt = settings.config.blip_gpt_prompts.joker.format(image_caption=image_caption)
    else:
        chat_gpt_prompt = settings.config.blip_gpt_prompts.basic.format(image_caption=image_caption)
    if message.caption != '' and message.caption is not None:
        chat_gpt_prompt = settings.config.blip_gpt_prompts.caption_message.format(prompt=chat_gpt_prompt,
                                                                                  message=message.caption)
    message.text = chat_gpt_prompt

    logger.info(f"User '{tg_user.username}' sends a picture with size ({image.width}, {image.height})")

    # Debug breaks users privacy here! Disable it in general use!
    logger.debug(f'Picture from {tg_user.username}, pers: {pers}. Caption: "{image_caption}"')

    await asyncio.get_event_loop().create_task(communication_answer(message, state=state, is_image=True))
