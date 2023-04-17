import asyncio
import logging
import tempfile

from PIL import Image
from aiogram import types
from aiogram.dispatcher import FSMContext

from app.blip_captions_model import get_images_captions
from app.bot import dp, CONFIG, PERSONALITIES, build_reply_markup, thread_pool, MESSAGES, global_message
from app.exceptions_handler import exception_sorry
from app.open_ai_client import create_message, truncate_user_history, count_tokens
from app.user_service import UserState, reset_user_state, check_user_permission, check_is_admin

logger = logging.getLogger(__name__)


class TypingBlock(object):

    def __init__(self, chat: types.Chat):
        self.chat = chat
        self.typing_task = None

    async def __aenter__(self):

        async def typing_cycle():
            try:
                while True:
                    await self.chat.do("typing")
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                pass

        self.typing_task = asyncio.create_task(typing_cycle())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.typing_task:
            self.typing_task.cancel()


@dp.message_handler(state=UserState.admin_message)
@exception_sorry()
async def admin_message(message: types.Message, state: FSMContext, *args, **kwargs):

    await message.answer('Now your message will be sent to all known users...')
    data = await state.get_data()
    if data['do_markdown']:
        await global_message(message.md_text, do_markdown=True)
    else:
        await global_message(message.text, do_markdown=False)
    await message.answer('Done!')

    await reset_user_state(state)


@dp.message_handler(state=UserState.custom_pers_setup)
@exception_sorry()
async def custom_personality(message: types.Message, state: FSMContext, *args, **kwargs):

    await state.update_data({'custom_prompt': message.text.strip()})
    await UserState.communication.set()
    await message.answer(MESSAGES['pers_selection']['go'])


@dp.message_handler(state=None)
@exception_sorry()
async def default_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    user_name = message.from_user.username
    if check_user_permission(user_name):
        await reset_user_state(state)
        await message.answer(MESSAGES['bot_reboot'],
                             reply_markup=build_reply_markup(user_name))


@dp.message_handler(state=UserState.menu)
@exception_sorry()
async def pers_selection_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    user_name = message.from_user.username

    text = message.text.strip()
    found = list(filter(lambda x: x[1]['name'] == text, PERSONALITIES.items()))
    if len(found) == 1:
        await message.answer(MESSAGES['pers_selection']['go'],
                             reply_markup=types.ReplyKeyboardRemove())
        await state.update_data({'pers': found[0][0]})
        await UserState.communication.set()
    elif text == MESSAGES['custom_personality']['button']:
        await state.update_data({'pers': 'custom'})
        await UserState.custom_pers_setup.set()
        await message.answer(MESSAGES['custom_personality']['info'],
                             reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer(MESSAGES['pers_selection']['mistake'],
                             reply_markup=build_reply_markup(user_name))


@dp.message_handler(state=UserState.communication)
@exception_sorry()
async def communication_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    current_data = await state.get_data()
    user_name = message.from_user.username

    pers = current_data.get('pers')
    pers_prompt = PERSONALITIES[pers]['context'] if pers != 'custom' else current_data.get('custom_prompt')

    orig_history = current_data.get('history') or []
    history = orig_history + [{"role": "user", "content": message.text}]

    previous_tokens_usage = current_data.get('prev_tokens_usage') or 0
    previous_tokens_usage += count_tokens(message.text)  # maybe +10? (openai...)

    history = history[-CONFIG['last_messages_count']:]
    history, removed_tokens = truncate_user_history(user_name, pers_prompt, history, previous_tokens_usage)

    async with TypingBlock(message.chat):
        ai_message, tokens_usage = await asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                                  create_message,
                                                                                  user_name, pers_prompt, history)
    ready_message = ai_message

    if removed_tokens > 0:
        ready_message += MESSAGES['tokens']['notion'].format(removed_tokens=removed_tokens)

    if CONFIG['append_tokens_count']:
        message_size = count_tokens(message.text)
        ready_message += MESSAGES['tokens']['notion'].format(message_size=message_size, tokens_usage=tokens_usage)

    await message.reply(ready_message)

    logger.info(f"Another reply to user '{user_name}' sent, personality '{pers}', used tokens: {tokens_usage}")

    updated_data = await state.get_data()  # may be already changed due concurrency
    if updated_data.get('pers') == pers:
        # updated_history = updated_data.get('history') or []
        updated_history = history + [
            # {"role": "user", "content": message.text},
            {"role": "assistant", "content": ai_message}
        ]

        # Debug breaks users privacy here! Disable it in general use!
        logger.debug(f'History of user {user_name}: {updated_history}')

        await state.update_data({'history': updated_history, 'prev_tokens_usage': tokens_usage})


@dp.message_handler(state=UserState.communication, content_types=['photo'])
@exception_sorry()
async def photo_answer(message: types.Message, state: FSMContext, *args, **kwargs):

    current_data = await state.get_data()
    user_name = message.from_user.username
    pers = current_data.get('pers')

    file_info = await message.bot.get_file(message.photo[-1].file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:  # temp dir for future support of many photos
        result = await message.bot.download_file(file_path=file_info.file_path,
                                                 destination_dir=tmp_dir)
        result.close()
        image = Image.open(result.name).convert('RGB')

    image_caption = get_images_captions(image)[0]

    if pers == 'joker':
        chat_gpt_prompt = CONFIG['blip_gpt_prompts']['joker'].format(image_caption=image_caption)
    else:
        chat_gpt_prompt = CONFIG['blip_gpt_prompts']['basic'].format(image_caption=image_caption)
    if message.caption != '' and message.caption is not None:
        chat_gpt_prompt = CONFIG['blip_gpt_prompts']['caption_message'].format(prompt=chat_gpt_prompt,
                                                                               message=message.caption)
    message.text = chat_gpt_prompt

    logger.info(f'User {user_name} sends a picture with size ({image.width}, {image.height})')

    # Debug breaks users privacy here! Disable it in general use!
    logger.debug(f'Picture from {user_name}, pers: {pers}. Caption: "{image_caption}"')

    await communication_answer(message, state)
