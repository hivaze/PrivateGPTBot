import logging
import time

import openai
from openai.openai_object import OpenAIObject

from .bot import CONFIG

logger = logging.getLogger(__name__)
openai.api_key = CONFIG['OPENAI_KEY']


def create_message(system_prompt, history):
    MAX_RETRIES = 3
    history = history or []
    messages = [{"role": "system", "content": system_prompt}] + history
    for i in range(1, MAX_RETRIES + 1):
        try:
            response: OpenAIObject = openai.ChatCompletion.create(messages=messages, **CONFIG['generation_params'])
            return response['choices'][0]['message']['content']
        except (openai.error.APIError, openai.error.RateLimitError) as e:
            retries_left = MAX_RETRIES - i
            if i == MAX_RETRIES:
                raise
            else:
                logger.warning(f'Got {e.__class__.__name__} from OpenAI: {e}. '
                               f'Retrying {retries_left} more time{"" if retries_left == 1 else "s"}.')
                time.sleep(i**2)
