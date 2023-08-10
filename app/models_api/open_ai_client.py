import logging
import time

import openai
from openai.openai_object import OpenAIObject

import tiktoken
import numpy as np

from app.bot import settings

logger = logging.getLogger(__name__)
openai.api_key = settings.config.OPENAI_KEY


def generate_message(user_name, model_config, system_prompt, history):
    """
    Sends a request to OpenAI API, blocks until response, do openai_api_retries retries to bypass rate limits
    :param user_name: tg username
    :param model_config: ModelConfig
    :param system_prompt: one of personalities
    :param history: user history messages
    :return: ChatGPT answer and tokens usage statistics dict, also time taken in ms
    """
    start_time = int(time.time() * 1000)
    messages = [{"role": "system", "content": system_prompt}] + history
    for i in range(0, settings.config.openai_api_retries):
        try:
            response: OpenAIObject = openai.ChatCompletion.create(messages=messages,
                                                                  model=model_config.model_name,
                                                                  **settings.config.generation_params)
            time_taken = int(time.time() * 1000) - start_time
            return response['choices'][0]['message']['content'], response['usage']['total_tokens'], time_taken
        except (openai.error.APIError, openai.error.RateLimitError) as e:
            logger.warning(f"Get exception from OpenAI for {user_name}: {e}")
            time.sleep(2**i)  # wait longer


def count_tokens(model_config, text):
    encoder = tiktoken.encoding_for_model(model_config.model_name)
    return encoder.encode(text).__len__()


def truncate_user_history(user_name, model_config, pers_prompt, history, tokens_usage):
    """
    Translates all messages into a distribution of lengths, multiplies them by the number of tokens to be removed,
    and removes the computed normalized number of tokens from the end of each message,
    leaving the most recent message intact.

    Note:
    This method is not perfect for very short histories, but it can fix most length-limit errors with OpenAI API.
    """

    allowed_total_tokens = model_config.max_context_size - settings.config.generation_params.get('max_tokens', 1024)

    pers_allowed_hist_tokens = allowed_total_tokens - count_tokens(model_config, pers_prompt)
    total_tokens_to_remove = max(tokens_usage - pers_allowed_hist_tokens, 0)

    if total_tokens_to_remove == 0:
        return history, total_tokens_to_remove

    history_tokens_counts = np.array([count_tokens(model_config, md['content']) for md in history[:-1]])
    history_tokens_counts_norm = history_tokens_counts / history_tokens_counts.sum()

    history_tokens_remove_instructions = (history_tokens_counts_norm * total_tokens_to_remove).round().astype(np.int64)

    logger.debug(f'Removing {total_tokens_to_remove} tokens from {user_name} history. '
                 f'Tokens delete instructions: {history_tokens_remove_instructions}')

    encoder = tiktoken.encoding_for_model(model_config.model_name)

    for i, message_dict in enumerate(history[:-1]):
        content_tokens = encoder.encode(message_dict['content'])
        content_tokens = content_tokens[:-history_tokens_remove_instructions[i]]  # remove last tokens
        truncated_message = encoder.decode(content_tokens)
        message_dict['content'] = truncated_message

    return history, total_tokens_to_remove
