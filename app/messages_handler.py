import asyncio
import datetime
import logging
import tempfile
from collections import defaultdict

from PIL import Image
from aiogram import types
from aiogram.dispatcher import FSMContext

from app.blip_captions_model import get_images_captions
from app.bot import dp, thread_pool, settings
from app.bot_utils import TypingBlock, global_message, build_menu_markup, build_specials_markup, no_access_message
from app.exceptions_handler import exception_sorry
from app.open_ai_client import create_message, truncate_user_history, count_tokens
from app.user_service import UserState, reset_user_state, \
    check_user_access, get_or_create_user, add_message_record, \
    TokensUsageStatus, MessageEntity, check_tokens, tokens_spending, reset_tokens_package, Role

logger = logging.getLogger(__name__)

coroutine_locks = defaultdict(asyncio.Lock)


@dp.message_handler(state=UserState.admin_message)
@exception_sorry()
async def admin_message(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    await message.answer('Now your message will be sent to all known users...')

    data = await state.get_data()
    if data['do_markdown']:
        await global_message(message.md_text, do_markdown=True)
    else:
        await global_message(message.text, do_markdown=False)
    await message.answer('Done!')

    await reset_user_state(tg_user, state)

    reply_message = {
        'text': settings.messages['welcome']['reset'],
        'reply_markup': build_menu_markup(tg_user.username)
    }
    await message.answer(**reply_message)



@dp.message_handler(state=UserState.custom_pers_setup)
@exception_sorry()
async def custom_personality(message: types.Message, state: FSMContext, *args, **kwargs):
    await state.update_data({'custom_prompt': message.text.strip()})
    await UserState.communication.set()
    await message.answer(settings.messages['pers_selection']['go'])


@dp.message_handler(state=None)
@exception_sorry()
async def default_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    if check_user_access(tg_user):
        await reset_user_state(tg_user, state)
        await message.answer(settings.messages['bot_reboot'],
                             reply_markup=build_menu_markup(tg_user))
    else:
        await no_access_message(tg_user, message)


@dp.message_handler(state=UserState.menu)
@exception_sorry()
async def pers_selection_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user

    text = message.text.strip()
    all_pers = list(settings.personalities.items())
    found = list(filter(lambda x: x[1]['name'] == text, all_pers))
    if len(found) == 1:
        await message.answer(settings.messages['pers_selection']['go'],
                             reply_markup=types.ReplyKeyboardRemove())
        await state.update_data({'pers': found[0][0]})
        await UserState.communication.set()
    elif text == settings.messages['custom_personality']['button']:
        await state.update_data({'pers': 'custom'})
        await UserState.custom_pers_setup.set()
        await message.answer(settings.messages['custom_personality']['info'],
                             reply_markup=types.ReplyKeyboardRemove())
    elif text == settings.messages['specialties']['button']:
        await message.answer(settings.messages['specialties']['info'],
                             reply_markup=build_specials_markup(tg_user))
        await message.delete()
    elif text == settings.messages['specialties']['back_button']:
        await message.answer(settings.messages['pers_selection']['info'],
                             reply_markup=build_menu_markup(tg_user))
        await message.delete()
    else:
        await message.answer(settings.messages['pers_selection']['mistake'],
                             reply_markup=build_menu_markup(tg_user))


@dp.message_handler(state=UserState.communication)
# @exception_sorry()
async def communication_answer(message: types.Message, state: FSMContext, is_image=False, *args, **kwargs):
    tg_user = message.from_user

    await coroutine_locks[tg_user.id].acquire()

    current_data = await state.get_data()

    user = get_or_create_user(tg_user)

    if user.ban:
        await no_access_message(tg_user, message)
        coroutine_locks[tg_user.id].release()
        return

    if check_tokens(tg_user.id) != TokensUsageStatus.ALLOWED:
        if user.role != Role.PRIVILEGED:
            coroutine_locks[tg_user.id].release()
            return
        else:
            reset_tokens_package(user)
            logger.info(f"Resetting '{tg_user.username}' | '{tg_user.id}' tokens package due PRIVILEGED role.")

    # Personality prompt
    pers = current_data.get('pers')
    pers_prompt = settings.personalities[pers]['context'] if pers != 'custom' else current_data.get('custom_prompt')

    # Messages history management
    orig_history = current_data.get('history') or []
    history = orig_history + [{"role": "user", "content": message.text}]
    previous_tokens_usage = current_data.get('prev_tokens_usage') or 0
    previous_tokens_usage += count_tokens(message.text)  # maybe +10? (openai...)
    history = history[-settings.config['last_messages_count']:]
    history, removed_tokens = truncate_user_history(tg_user.username, pers_prompt, history, previous_tokens_usage)

    # request loop (do typing)
    async with TypingBlock(message.chat):
        ai_message, tokens_usage = await asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                                  create_message,
                                                                                  tg_user.username,
                                                                                  pers_prompt, history)
        add_message_record(tg_user.id, MessageEntity(tg_message_id=message.message_id,
                                                     used_tokens=tokens_usage,
                                                     has_image=is_image,
                                                     executed_at=datetime.datetime.now()))
        tokens_spending(tg_user.id, tokens_usage)

    sent_message = await message.reply(ai_message)

    if removed_tokens > 0:
        await sent_message.reply(settings.messages['tokens']['notion'].format(removed_tokens=removed_tokens))

    if settings.config['append_tokens_count']:
        message_size = count_tokens(message.text)
        await sent_message.reply(settings.messages['tokens']['tokens_count'].format(message_size=message_size,
                                                                                    tokens_usage=tokens_usage))

    logger.info(f"Another reply to user '{tg_user.username}' | '{tg_user.id}' sent, personality '{pers}',"
                f" used tokens: {tokens_usage}")

    updated_history = history + [
        {"role": "assistant", "content": ai_message}
    ]

    logger.debug(f'History of user {tg_user.username}: {updated_history}')

    await state.update_data({'history': updated_history, 'prev_tokens_usage': tokens_usage})

    coroutine_locks[tg_user.id].release()


@dp.message_handler(state=UserState.communication, content_types=['photo'])
@exception_sorry()
async def photo_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    current_data = await state.get_data()

    tg_user = message.from_user
    user = get_or_create_user(tg_user)

    if user.ban:
        await no_access_message(tg_user, message)
        coroutine_locks[tg_user.id].release()
        return

    file_info = await message.bot.get_file(message.photo[-1].file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:  # temp dir for future support of many photos
        result = await message.bot.download_file(file_path=file_info.file_path,
                                                 destination_dir=tmp_dir)
        result.close()
        image = Image.open(result.name).convert('RGB')

    image_caption = get_images_captions(image)[0]

    pers = current_data.get('pers')

    if pers == 'joker':
        chat_gpt_prompt = settings.config['blip_gpt_prompts']['joker'].format(image_caption=image_caption)
    else:
        chat_gpt_prompt = settings.config['blip_gpt_prompts']['basic'].format(image_caption=image_caption)
    if message.caption != '' and message.caption is not None:
        chat_gpt_prompt = settings.config['blip_gpt_prompts']['caption_message'].format(prompt=chat_gpt_prompt,
                                                                                        message=message.caption)
    message.text = chat_gpt_prompt

    logger.info(f"User '{tg_user.username}' sends a picture with size ({image.width}, {image.height})")

    # Debug breaks users privacy here! Disable it in general use!
    logger.debug(f'Picture from {tg_user.username}, pers: {pers}. Caption: "{image_caption}"')

    await communication_answer(message, state, is_image=True)
