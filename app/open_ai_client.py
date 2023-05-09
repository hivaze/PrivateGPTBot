import logging
import time

import openai
from openai.openai_object import OpenAIObject

import tiktoken
import numpy as np

from app.bot import settings

logger = logging.getLogger(__name__)
openai.api_key = settings.config['OPENAI_KEY']

chat_gpt_encoder = tiktoken.encoding_for_model(settings.config['generation_params']['model'])

CHATGPT_MAX_LENGTH = 4096  # claimed by OpenAI
ALLOWED_TOTAL_HIST_TOKENS = CHATGPT_MAX_LENGTH - settings.config['generation_params'].get('max_tokens', 1024)


def create_message(user_name, system_prompt, history):
    """
    Sends a request to OpenAI API, blocks until response, do openai_api_retries retries to bypass rate limits
    :param user_name: tg username
    :param system_prompt: one of personalities
    :param history: user history messages
    :return: ChatGPT answer and tokens usage statistics dict
    """
    history = history or []
    messages = [{"role": "system", "content": system_prompt}] + history
    for i in range(0, settings.config['openai_api_retries']):
        try:
            response: OpenAIObject = openai.ChatCompletion.create(messages=messages,
                                                                  **settings.config['generation_params'])
            return response['choices'][0]['message']['content'], response['usage']['total_tokens']
        except (openai.error.APIError, openai.error.RateLimitError) as e:
            logger.warning(f"Get exception from OpenAI for {user_name}: {e}")
            time.sleep(2**i)  # wait longer


def count_tokens(text):
    return chat_gpt_encoder.encode(text).__len__()


def truncate_user_history(user_name, pers_prompt, history, tokens_usage):
    """
    Translates all messages into a distribution of lengths, multiplies them by the number of tokens to be removed,
    and removes the computed normalized number of tokens from the end of each message,
    leaving the most recent message intact.

    Note:
    This method is not perfect for very short histories, but it can fix most length-limit errors with OpenAI API.
    """
    pers_allowed_hist_tokens = ALLOWED_TOTAL_HIST_TOKENS - chat_gpt_encoder.encode(pers_prompt).__len__()
    total_tokens_to_remove = max(tokens_usage - pers_allowed_hist_tokens, 0)

    if total_tokens_to_remove == 0:
        return history, total_tokens_to_remove

    history_tokens_counts = np.array([count_tokens(md['content']) for md in history[:-1]])
    history_tokens_counts_norm = history_tokens_counts / history_tokens_counts.sum()

    history_tokens_remove_instructions = (history_tokens_counts_norm * total_tokens_to_remove).round().astype(np.int64)

    logger.debug(f'Removing {total_tokens_to_remove} tokens from {user_name} history. '
                 f'Tokens delete instructions: {history_tokens_remove_instructions}')

    for i, message_dict in enumerate(history[:-1]):
        content_tokens = chat_gpt_encoder.encode(message_dict['content'])
        content_tokens = content_tokens[:-history_tokens_remove_instructions[i]]  # remove last tokens
        truncated_message = chat_gpt_encoder.decode(content_tokens)
        message_dict['content'] = truncated_message

    return history, total_tokens_to_remove
