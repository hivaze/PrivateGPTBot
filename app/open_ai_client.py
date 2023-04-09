import asyncio
import logging
import time

import openai
from openai.openai_object import OpenAIObject

from .bot import CONFIG

logger = logging.getLogger(__name__)
openai.api_key = CONFIG['OPENAI_KEY']


def create_message(system_prompt, history):
    history = history or []
    messages = [{"role": "system", "content": system_prompt}] + history
    for i in range(0, 3):
        try:
            response: OpenAIObject = openai.ChatCompletion.create(messages=messages, **CONFIG['generation_params'])
            return response['choices'][0]['message']['content']
        except (openai.error.APIError, openai.error.RateLimitError) as e:
            logger.warning(f"Get exception from OpenAI: {e}")
            time.sleep(i**2)
