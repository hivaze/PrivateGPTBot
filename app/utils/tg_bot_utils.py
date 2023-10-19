import asyncio
import datetime
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import User, Message
from aiogram.utils.exceptions import BadRequest

from app import settings
from app.database.sql_db_service import UserEntity, MessageEntity, Reaction, GlobalMessagesUsersAssociation, \
    session_factory

logger = logging.getLogger(__name__)

FORWARD_MESSAGE_FORMAT = "Forwarded message from {user_name}: {message}"
DEFAULT_MESSAGE_FORMAT = "{message}"
DOCUMENTS_DESCRIPTION_PROMPT = "\nDescription of documents provided by user: \n{documents_desc}"


class TypingBlock(object):

    def __init__(self, chat):
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


def format_language_code(language_code: str):
    return language_code if language_code in ['ru', 'en'] else 'en'


def format_system_prompt(tg_user: User, current_user_data: dict, system_prompt: str):
    lc = format_language_code(tg_user.language_code)
    system_prompt = system_prompt.format(user_name=tg_user.first_name,
                                         user_lang=lc,
                                         dt=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if current_user_data.get('documents'):
        documents_desc = "\n".join(current_user_data.get('documents'))
        system_prompt += DOCUMENTS_DESCRIPTION_PROMPT.format(documents_desc=documents_desc)
    return system_prompt


async def no_access_message(tg_user: User, message):
    lc = format_language_code(tg_user.language_code)
    await message.answer(text=settings.messages.welcome.no_access[lc])


# async def send_db(tg_user: User):
#     from app.bot import tg_bot
#     file = InputFile(DB_PATH, filename=f"users-{datetime.datetime.now()}.db")
#     await tg_bot.send_document(tg_user.id, file)


def session_auto_ended(tg_chat_id: int):
    from app.bot import tg_bot
    from app.database.entity_services import users_service
    with session_factory() as session:
        user = users_service.get_user_by_id(session, tg_chat_id)
        if user is not None:
            lc = format_language_code(user.language_code)
            try:
                asyncio.create_task(tg_bot.send_message(chat_id=tg_chat_id,
                                                        text=settings.messages.session.end[lc],
                                                        reply_markup=build_menu_markup(lc)))
            except Exception as e:
                logger.info(f"Can't send message about auto session closing to {tg_chat_id}, reason: {e}")
        session.close()


async def instant_messages_collector(state, message):
    """A function that allows you to receive forwarded messages in any quantity, as well as collect messages from the
    user into a buffer with a slight delay. Translates this buffer into a single message."""

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

    return do_answer, len(instant_messages_buffer), concatenated_message, current_user_data.get("messaging_lock")


def build_settings_markup(user: UserEntity):
    lc = format_language_code(user.language_code)
    settings_menu = InlineKeyboardMarkup(row_width=1)
    global_messages_btn = settings.messages.settings_menu.allow_global_messages.turn_off[lc] if user.settings.allow_global_messages else settings.messages.settings_menu.allow_global_messages.turn_on[lc]
    settings_menu.add(InlineKeyboardButton(
        text=global_messages_btn,
        callback_data="settings|allow_global_messages"))
    reactions_btn = settings.messages.settings_menu.reactions.turn_off[lc] if user.settings.enable_reactions else settings.messages.settings_menu.reactions.turn_on[lc]
    settings_menu.add(InlineKeyboardButton(
        text=reactions_btn,
        callback_data="settings|enable_reactions"))
    tokens_info_bth = settings.messages.settings_menu.tokens_info.turn_off[lc] if user.settings.enable_tokens_info else settings.messages.settings_menu.tokens_info.turn_on[lc]
    settings_menu.add(InlineKeyboardButton(
        text=tokens_info_bth,
        callback_data="settings|enable_tokens_info"))
    superior_by_default_btn = settings.messages.settings_menu.use_superior_by_default.turn_off[lc] if user.settings.use_superior_by_default else settings.messages.settings_menu.use_superior_by_default.turn_on[lc]
    settings_menu.add(InlineKeyboardButton(
        text=superior_by_default_btn,
        callback_data="settings|use_superior_by_default"))
    return settings_menu


async def update_settings_markup(user: UserEntity, settings_message_id: int):
    from app.bot import tg_bot
    settings_menu = build_settings_markup(user)
    try:
        await tg_bot.edit_message_reply_markup(user.user_id, settings_message_id, reply_markup=settings_menu)
    except Exception:
        pass


async def delete_settings_message(state: FSMContext, chat_id: int):
    from app.bot import tg_bot
    current_data = await state.get_data()
    if current_data.get('last_settings_message_id'):
        try:
            await tg_bot.delete_message(chat_id, current_data.get('last_settings_message_id'))
        except Exception:
            pass


async def send_settings_menu(message: types.Message, state: FSMContext, user: UserEntity):
    lc = format_language_code(user.language_code)
    settings_menu = build_settings_markup(user)
    settings_message = await message.answer(
        settings.messages.settings_menu.info[lc],
        reply_markup=settings_menu)
    await delete_settings_message(state, message.chat.id)
    await state.update_data({'last_settings_message_id': settings_message.message_id})


def build_gmua_markup(user: UserEntity, gmua: GlobalMessagesUsersAssociation):
    lc = format_language_code(user.language_code)
    markup = InlineKeyboardMarkup(row_width=2)
    if gmua.reaction is None:
        like = InlineKeyboardButton(settings.messages.reactions.good[lc], callback_data='global_messages|like')
        dislike = InlineKeyboardButton(settings.messages.reactions.bad[lc], callback_data='global_messages|dislike')
        markup.add(like, dislike)
    else:
        reaction_name = settings.messages.reactions.liked[lc] if gmua.reaction == Reaction.GOOD else settings.messages.reactions.disliked[lc]
        reacted = InlineKeyboardButton(reaction_name, callback_data='reacted')
        markup.add(reacted)
    return markup


async def update_gmua_reaction_markup(user: UserEntity, gmua: GlobalMessagesUsersAssociation):
    from app.bot import tg_bot
    markup = build_gmua_markup(user, gmua)
    try:
        await tg_bot.edit_message_reply_markup(user.user_id, gmua.tg_message_id, reply_markup=markup)
    except Exception:
        pass


def build_message_markup(user: UserEntity,
                         last_message: MessageEntity = None,
                         with_redo: bool = True) -> InlineKeyboardMarkup:
    lc = format_language_code(user.language_code)
    markup = InlineKeyboardMarkup(row_width=2)

    if user.settings.enable_reactions:
        if last_message is None or last_message.reaction is None:
            like = InlineKeyboardButton(settings.messages.reactions.good[lc], callback_data='messages|like')
            dislike = InlineKeyboardButton(settings.messages.reactions.bad[lc], callback_data='messages|dislike')
            markup.add(like, dislike)
        elif last_message is not None:
            reaction_name = settings.messages.reactions.liked[lc] if last_message.reaction == Reaction.GOOD else settings.messages.reactions.disliked[lc]
            reacted = InlineKeyboardButton(reaction_name, callback_data='reacted')
            markup.add(reacted)
    if with_redo:
        redo_buttons = []
        if not user.settings.use_superior_by_default:
            redo_buttons.append(InlineKeyboardButton(settings.messages.redo.default[lc], callback_data='messages|redo|gpt-3.5'))
        gpt_4_button_name = settings.messages.redo.default[lc] if user.settings.use_superior_by_default else settings.messages.redo.superior[lc]
        redo_buttons.append(InlineKeyboardButton(gpt_4_button_name, callback_data='messages|redo|gpt-4'))
        markup.add(*redo_buttons)

    return markup


async def update_messages_reaction_markup(user: UserEntity, target_message: MessageEntity, add_redo: bool = True):
    from app.bot import tg_bot
    markup = build_message_markup(user, target_message, with_redo=add_redo)
    try:
        await tg_bot.edit_message_reply_markup(user.user_id, target_message.tg_message_id, reply_markup=markup)
    except Exception:
        pass


async def clean_last_message_markup(user: UserEntity, last_message: MessageEntity):
    from app.bot import tg_bot
    markup = build_message_markup(user, last_message, with_redo=False)
    try:
        await tg_bot.edit_message_reply_markup(user.user_id, last_message.tg_message_id, reply_markup=markup)
    except Exception:
        pass


async def send_response_message(user: UserEntity,
                                user_message: Message,
                                bot_message: str,
                                do_reply: bool,
                                add_redo=True) -> Message:
    markup = build_message_markup(user, last_message=None, with_redo=add_redo)
    if do_reply:
        try:
            sent_message = await user_message.reply(bot_message, reply_markup=markup)
        except BadRequest:  # Fix for 'Replied message not found'
            sent_message = await user_message.answer(bot_message, reply_markup=markup)
    else:
        sent_message = await user_message.answer(bot_message, reply_markup=markup)
    return sent_message


def build_menu_markup(language_code: str) -> types.ReplyKeyboardMarkup:
    markup = [types.KeyboardButton(v.name[language_code])
              for k, v in settings.personalities.items() if v.location == 'main']
    markup += [types.KeyboardButton(settings.messages.main_menu.specialities[language_code])]
    markup = [markup[i:i + 2] for i in range(0, len(markup), 2)]
    markup += [[types.KeyboardButton(settings.messages.main_menu.about[language_code]),
                types.KeyboardButton(settings.messages.main_menu.settings[language_code]),
                types.KeyboardButton(settings.messages.main_menu.feedback[language_code])]]
    return types.ReplyKeyboardMarkup(keyboard=markup, row_width=2, resize_keyboard=True)


def build_specials_markup(language_code: str) -> types.ReplyKeyboardMarkup:
    markup = [types.KeyboardButton(v.name[language_code])
              for k, v in settings.personalities.items() if v.location == 'specialties']
    markup = [markup[i:i + 2] for i in range(0, len(markup), 2)]
    markup = markup + [[types.KeyboardButton(settings.messages.custom_personality.button[language_code]),
                        types.KeyboardButton(settings.messages.specialties_menu.back[language_code])]]
    return types.ReplyKeyboardMarkup(keyboard=markup, resize_keyboard=True)
