import asyncio
import datetime
import logging
from asyncio import CancelledError

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType
from sqlalchemy.orm import Session

from app import settings
from app.bot import dp, small_context_model, long_context_model, superior_model, thread_pool
from app.database.entity_services.feedback_service import save_feedback
from app.database.entity_services.global_messages_service import global_message, get_gmua
from app.database.entity_services.messages_service import add_message_record, get_last_message, get_message_by_tgid
from app.database.entity_services.tokens_packages_service import tokens_spending, find_tokens_package, tokens_barrier
from app.database.entity_services.users_service import get_users_with_filters, access_check, get_all_users
from app.database.sql_db_service import MessageEntity, with_session, Reaction, UserEntity
from app.handlers.exceptions_handler import zero_exception
from app.internals.bot_logic.fsm_service import UserState, reset_user_state, switch_to_communication_state
from app.internals.chat.chat_history import ChatHistory, ChatRole, ChatMessage
from app.internals.ai.chat_models import TextGenerationResult
from app.internals.ai.blip_captions_model import get_images_captions
from app.internals.function_calling.definitions import build_openai_functions
from app.internals.function_calling.executors import execute_function_call
from app.internals.function_calling.utils.document_processor import check_if_extension_supported, \
    handle_document_upload
from app.utils.tg_bot_utils import build_menu_markup, build_specials_markup, format_language_code, \
    send_response_message, \
    format_system_prompt, instant_messages_collector, clean_last_message_markup, update_messages_reaction_markup, \
    send_settings_menu, update_settings_markup, TypingBlock, update_gmua_reaction_markup, handle_image_upload

logger = logging.getLogger(__name__)


@dp.message_handler(state=None, content_types=ContentType.ANY)
@zero_exception
@with_session
@access_check
async def void_answer(session: Session, user: UserEntity,
                      message: types.Message, state: FSMContext,
                      *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    await reset_user_state(session, user, state)

    await message.answer(settings.messages.session.zero_state[lc],
                         reply_markup=build_menu_markup(lc),
                         disable_notification=True)

    if await tokens_barrier(session, user):
        if message.text is not None:
            await asyncio.get_event_loop().create_task(main_menu_buttons(message, state=state))


@dp.message_handler(state=UserState.menu)
@zero_exception
@with_session
@access_check
async def main_menu_buttons(session: Session, user: UserEntity,
                            message: types.Message, state: FSMContext,
                            *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    if not await tokens_barrier(session, user):
        return

    text = message.text.strip()
    all_pers = list(settings.personalities.items())
    found = list(filter(lambda x: x[1].name[lc] == text, all_pers))
    if len(found) == 1:
        await state.update_data({'personality': found[0][0]})
        await switch_to_communication_state(message, state, lc)
    elif text == settings.messages.custom_personality.button[lc]:
        await state.update_data({'personality': 'custom'})
        await UserState.custom_pers_setup.set()
        await message.answer(settings.messages.custom_personality.info[lc],
                             reply_markup=types.ReplyKeyboardRemove())
    elif text == settings.messages.main_menu.specialities[lc]:
        await message.answer(settings.messages.specialties_menu.info[lc],
                             reply_markup=build_specials_markup(lc))
        await message.delete()
    elif text == settings.messages.specialties_menu.back[lc]:
        await message.answer(settings.messages.main_menu.info[lc],
                             reply_markup=build_menu_markup(lc))
        await message.delete()
    elif text == settings.messages.main_menu.settings[lc]:
        await send_settings_menu(message, state, user)
    elif text == settings.messages.main_menu.about[lc]:
        await message.answer(settings.messages.about_bot_info[lc], parse_mode='HTML')
    elif text == settings.messages.main_menu.feedback[lc]:
        await UserState.feedback.set()
        await message.answer(settings.messages.feedback.info[lc],
                             reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer(settings.messages.main_menu.mistake[lc],
                             reply_markup=build_menu_markup(lc))


@dp.message_handler(state=UserState.custom_pers_setup, content_types=ContentType.TEXT)
@zero_exception
async def custom_personality_message(message: types.Message, state: FSMContext,
                                     *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    if len(message.text.strip()) < 5:
        await message.answer(settings.messages.custom_personality.too_short[lc])
    else:
        await state.update_data({'custom_prompt': message.text.strip()})
        await switch_to_communication_state(message, state, lc)


@dp.message_handler(state=UserState.feedback, content_types=ContentType.TEXT)
@zero_exception
@with_session
@access_check
async def feedback_message(session: Session, user: UserEntity,
                           message: types.Message, state: FSMContext,
                           *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    if len(message.text.strip()) < 5:
        await message.answer(settings.messages.feedback.too_short[lc])
    else:
        save_feedback(session, user, message.text)
        await UserState.menu.set()
        await message.answer(settings.messages.feedback.got[lc],
                             reply_markup=build_menu_markup(lc))


@dp.message_handler(state=UserState.admin_message)
@zero_exception
@with_session
@access_check
async def admin_message(session: Session, user: UserEntity,
                        message: types.Message, state: FSMContext,
                        *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    data = await state.get_data()
    users = get_users_with_filters(session) if not data['for_all'] else get_all_users(session)

    await message.answer(f'Now your message will be sent to {len(users)} users...')
    await global_message(session, tg_user.id, users, message.text, do_html=data['do_html'])
    await message.answer('Done!')

    await reset_user_state(session, user, state)

    reply_message = {
        'text': settings.messages.reset[lc],
        'reply_markup': build_menu_markup(lc)
    }
    await message.answer(**reply_message)


@dp.message_handler(state=UserState.communication, content_types=ContentType.TEXT)
@zero_exception
@with_session
@access_check
async def communication_answer(session: Session, user: UserEntity,
                               message: types.Message, state: FSMContext,
                               add_user_message_to_hist=True, do_superior=False,
                               is_image=False, has_document=False,
                               function_call="auto", ignore_lock=False,
                               *args, **kwargs):
    tg_user = message.from_user
    sent_message = None
    lc = format_language_code(tg_user.language_code)

    do_answer, instant_messages_buffer_size, concatenated_message, messages_lock = \
        await instant_messages_collector(state, message)
    if not do_answer:
        return

    if not ignore_lock:
        await messages_lock.acquire()

    try:  # try-finally block for precise lock release

        tokens_package = find_tokens_package(session, tg_user.id)
        tokens_package_config = settings.tokens_packages.get(tokens_package.package_name, 'default')
        last_message = get_last_message(session, user)
        functions = await build_openai_functions(state) if tokens_package_config.use_functions else None

        if last_message is not None:
            await clean_last_message_markup(user, last_message)

        # Force to use superior model
        if user.settings.use_superior_by_default:
            do_superior = True

        # Get current user in-memory data
        current_user_data = await state.get_data()

        # Choose personality prompt and get history
        personality = current_user_data.get('personality')

        # Check if user state was reset during previous generation
        if personality is None:
            return

        system_prompt = settings.personalities[personality].context \
            if personality != 'custom' else current_user_data.get('custom_prompt')
        system_prompt = format_system_prompt(tg_user, current_user_data, system_prompt)

        # Get current chat history
        history: ChatHistory = current_user_data.get('history') or ChatHistory()
        history.system_message = ChatMessage(role=ChatRole.SYSTEM, text=system_prompt)
        if add_user_message_to_hist:
            history.add_message(ChatMessage(role=ChatRole.USER, text=message.text))

        # Main loop
        async with TypingBlock(message.chat):

            small_tokens_overflow: bool = small_context_model.count_tokens_overflow(history, functions)[0] == 0

            # Model selection
            if do_superior and tokens_package_config.superior_model:
                generation_task = asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                           superior_model.generate_answer,
                                                                           history,
                                                                           functions,
                                                                           function_call)
            elif small_tokens_overflow or not tokens_package_config.long_context:
                generation_task = asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                           small_context_model.generate_answer,
                                                                           history,
                                                                           functions,
                                                                           function_call)
            else:
                generation_task = asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                           long_context_model.generate_answer,
                                                                           history,
                                                                           functions,
                                                                           function_call)

            # Update current generation task
            await state.update_data({"generation_task": generation_task})

            try:
                # Execution of generation request in parallel process
                generation_result: TextGenerationResult = await generation_task
            except CancelledError:
                return

            # Remove current gen task
            await state.update_data({"generation_task": None})

        # Adding generated message to chat history
        history.add_message(generation_result.message)

        # Action management (Default message / FunctionCall)
        if not generation_result.is_function_call:
            sent_message = await send_response_message(user=user,
                                                       user_message=message,
                                                       bot_message=generation_result.message.text,
                                                       do_reply=instant_messages_buffer_size == 1,
                                                       add_redo=instant_messages_buffer_size == 1 and not is_image)
            logger.info(f'AI answer sent to "{tg_user.username}" | "{tg_user.id}",'
                        f' personality: "{personality}",'
                        f' model: "{generation_result.model_config.model_name}",'
                        f' tokens used: {generation_result.total_tokens_usage},'
                        f' time taken: {generation_result.time_taken}')

        add_message_record(session, tg_user.id,
                           MessageEntity(tg_message_id=sent_message.message_id if sent_message else None,
                                         executed_at=datetime.datetime.now(),
                                         time_taken=generation_result.time_taken,
                                         model=generation_result.model_config.model_name,
                                         personality=personality,
                                         prompt_tokens=generation_result.prompt_tokens_usage,
                                         completion_tokens=generation_result.completion_tokens_usage,
                                         total_tokens=generation_result.total_tokens_usage,
                                         history_size=len(history),
                                         instant_buffer=instant_messages_buffer_size,
                                         has_image=is_image,
                                         has_document=has_document,
                                         function_call=generation_result.message.name if generation_result.is_function_call else None,
                                         regenerated=False))
        left_tokens = tokens_spending(tokens_package,
                                      generation_result.total_tokens_usage,
                                      generation_result.model_config)

        if user.settings.enable_tokens_info:
            await message.reply(settings.messages.tokens.tokens_count[lc].format(
                prompt_tokens=int(generation_result.prompt_tokens_usage * generation_result.model_config.tokens_scale),
                completion_tokens=int(
                    generation_result.completion_tokens_usage * generation_result.model_config.tokens_scale),
                left_tokens=left_tokens,
            ), parse_mode='HTML')

        # Make function call
        if generation_result.is_function_call:
            async with TypingBlock(message.chat):
                await message.reply(settings.messages.external_data[lc])
                function_response = await asyncio.get_event_loop().run_in_executor(thread_pool,
                                                                                   execute_function_call,
                                                                                   user,
                                                                                   current_user_data,
                                                                                   generation_result.message)

            # Update chat history and release the lock
            history.add_message(function_response)
            await state.update_data({"history": history})

            # Call to get the final response
            asyncio.get_event_loop().create_task(communication_answer(message,
                                                                      state=state,
                                                                      add_user_message_to_hist=False,
                                                                      do_superior=do_superior,
                                                                      function_call="none",
                                                                      has_document=has_document,
                                                                      is_image=is_image,
                                                                      ignore_lock=True))
            return

        # Check tokens in the end and reset the state to menu
        if not await tokens_barrier(session, user):
            await reset_user_state(session, user, state)
            return

        # Warning about tokens amount
        if left_tokens / tokens_package_config.tokens < 0.1 and left_tokens > 0 and not settings.config.free_mode:
            await message.answer(settings.messages.tokens.running_out[lc])

        # Remove functions responses to save tokens
        history.remove_function_responses()

        # Update user state with new history
        await state.update_data({"history": history})

    finally:
        if not ignore_lock and messages_lock.locked():
            messages_lock.release()


@dp.message_handler(state=UserState.communication, content_types=ContentType.PHOTO)
@zero_exception
@with_session
@access_check
async def photo_answer(message: types.Message, state: FSMContext, *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    # current_user_data = await state.get_data()

    await message.reply(settings.messages.image_forward[lc])
    message.text = message.caption
    asyncio.get_event_loop().create_task(communication_answer(message, state=state, is_image=False))

    # file_info = await message.bot.get_file(message.photo[-1].file_id)
    #
    # async with TypingBlock(message.chat):
    #     image = await handle_image_upload(file_info)
    #     image_caption = get_images_captions(image)[0]
    #
    # pers = current_user_data.get('personality')
    #
    # if pers == 'joker':
    #     chat_gpt_prompt = settings.config.blip_gpt_prompts.joker.format(image_caption=image_caption, lang=lc)
    # else:
    #     chat_gpt_prompt = settings.config.blip_gpt_prompts.basic.format(image_caption=image_caption, lang=lc)
    # if message.caption != '' and message.caption is not None:
    #     chat_gpt_prompt = settings.config.blip_gpt_prompts.caption_message.format(prompt=chat_gpt_prompt,
    #                                                                               message=message.caption)
    # message.text = chat_gpt_prompt
    #
    # logger.info(f"User '{tg_user.username}' sends a picture with size ({image.width}, {image.height})")
    #
    # asyncio.get_event_loop().create_task(communication_answer(message, state=state, is_image=True))


@dp.message_handler(state=UserState.communication, content_types=ContentType.DOCUMENT)
@zero_exception
@with_session
@access_check
async def document_answer(session: Session,
                          message: types.Message, state: FSMContext,
                          *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    tokens_package = find_tokens_package(session, tg_user.id)
    tokens_package_config = settings.tokens_packages.get(tokens_package.package_name, 'default')

    if not tokens_package_config.use_functions:
        await message.reply(settings.messages.documents.not_allowed[lc])
        return

    file_info = await message.bot.get_file(message.document.file_id)
    caption = message.caption

    if not check_if_extension_supported(file_info.file_path):
        await message.reply(settings.messages.documents.not_supported[lc])
        return

    async with TypingBlock(message.chat):
        await message.reply(settings.messages.documents.loading[lc])
        await handle_document_upload(tg_user, message.document.file_name, file_info, state)

    if message.caption != '' and message.caption is not None:
        message.text = caption
        asyncio.get_event_loop().create_task(communication_answer(message, state=state, is_document=True))
    else:
        await message.answer(settings.messages.documents.loaded[lc])


@dp.message_handler(state=UserState.communication, content_types=ContentType.VOICE)
@zero_exception
@with_session
@access_check
async def voice_answer(session: Session,
                       message: types.Message, state: FSMContext,
                       *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    await message.reply(settings.messages.audio[lc])


@dp.callback_query_handler(state=UserState.all_states)
@zero_exception
@with_session
@access_check
async def callback_query(session: Session, user: UserEntity,
                         message: types.CallbackQuery, state: FSMContext,
                         *args, **kwargs):
    tg_user = message.from_user
    lc = format_language_code(tg_user.language_code)

    tokens_package = find_tokens_package(session, user.user_id)
    tokens_package_config = settings.tokens_packages.get(tokens_package.package_name, 'default')

    if message.data.startswith('settings'):

        settings_action = message.data.split('|', maxsplit=1)[1]
        if settings_action == 'allow_global_messages':
            user.settings.allow_global_messages = not user.settings.allow_global_messages
        if settings_action == 'enable_reactions':
            user.settings.enable_reactions = not user.settings.enable_reactions
        if settings_action == 'enable_tokens_info':
            user.settings.enable_tokens_info = not user.settings.enable_tokens_info
        if settings_action == 'use_superior_by_default':
            if tokens_package_config.use_superior_as_default:
                user.settings.use_superior_by_default = not user.settings.use_superior_by_default
            else:
                await message.answer(settings.messages.settings_menu.cant_use[lc])
                return

        await update_settings_markup(user, message.message.message_id)
        await message.answer()

        return

    if message.data.startswith('global_messages'):

        related_to = get_gmua(session, user, message.message.message_id)

        if related_to is None:
            await message.answer()
            return None

        gm_action = message.data.split('|', maxsplit=1)[1]
        if gm_action == 'like':
            related_to.reaction = Reaction.GOOD
            await update_gmua_reaction_markup(user, related_to)
        else:
            related_to.reaction = Reaction.BAD
            await update_gmua_reaction_markup(user, related_to)
        await message.answer()

    if message.data.startswith('messages'):

        related_to = get_message_by_tgid(session, message.message.message_id)

        if related_to is None:
            await message.answer()
            return None

        messages_action = message.data.split('|', maxsplit=1)[1]
        current_user_data = await state.get_data()

        if messages_action in ['like', 'dislike']:
            last_message = get_last_message(session, user)
            add_redo: bool = related_to == last_message and related_to.instant_buffer == 1 and current_user_data.get(
                'history')
            if messages_action == 'like':
                related_to.reaction = Reaction.GOOD
                await update_messages_reaction_markup(user, related_to, add_redo)
            else:
                related_to.reaction = Reaction.BAD
                await update_messages_reaction_markup(user, related_to, add_redo)
            await message.answer()

        if messages_action.startswith('redo'):
            tokens_package = find_tokens_package(session, tg_user.id)
            tokens_package_config = settings.tokens_packages.get(tokens_package.package_name, 'default')

            use_superior = messages_action.split('|')[1] == 'gpt-4'
            if not tokens_package_config.superior_model and use_superior:
                await message.answer(settings.messages.redo.not_allowed[lc])
                return

            await message.answer()

            messages_lock = current_user_data.get("messaging_lock")
            await messages_lock.acquire()

            # Here we need to await for the lock and get the latest message
            last_message = get_last_message(session, user)
            if related_to != last_message:
                return

            current_user_data = await state.get_data()
            history: ChatHistory = current_user_data.get('history')
            if not history:
                return

            try:
                target_message = message.message.reply_to_message
                if target_message.text is None:
                    target_message.text = target_message.caption
                if use_superior:
                    await target_message.reply(settings.messages.redo.generating.superior[lc])
                else:
                    await target_message.reply(settings.messages.redo.generating.default[lc])
                related_to.regenerated = True
                history.drop_last_arc()
                await state.update_data({"history": history})
                asyncio.get_event_loop().create_task(communication_answer(target_message,
                                                                          do_superior=use_superior,
                                                                          ignore_lock=True,
                                                                          state=state))
            except:
                await message.answer(settings.messages.redo.error[lc])
            finally:
                if messages_lock.locked():
                    messages_lock.release()

    else:
        await message.answer()
