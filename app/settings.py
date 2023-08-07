import json
import logging
from typing import List, Dict

from pydantic import BaseModel

logger = logging.getLogger(__name__)


##### Main configuration


class BlipConfig(BaseModel):
    use_large: bool
    device: str


class BlipGptPrompts(BaseModel):
    joker: str
    basic: str
    caption_message: str


class ContextConfig(BaseModel):
    last_messages_count: int
    max_context_size: int


class BotConfig(BaseModel):
    OPENAI_KEY: str
    TG_BOT_TOKEN: str
    context: ContextConfig
    global_mode: bool
    admins: List[str]
    bot_max_users_memory: int
    white_list_users: List[str]
    append_tokens_count: bool
    openai_api_retries: int
    blip: BlipConfig
    blip_gpt_prompts: BlipGptPrompts
    generation_params: dict


class PersonalityConfig(BaseModel):
    location: str
    name: str
    context: str


##### Tokens packages


class TokensPackageConfig(BaseModel):
    amount: int
    duration: str


##### Messages

class WelcomeText(BaseModel):
    with_access: str
    no_access: str
    reset: str


class TokensText(BaseModel):
    notion: str
    tokens_count: str


class PersSelectionText(BaseModel):
    go: str
    mistake: str
    info: str


class SpecialtiesText(BaseModel):
    button: str
    back_button: str
    info: str


class CustomPersonalityText(BaseModel):
    button: str
    info: str


class MessagesConfig(BaseModel):
    welcome: WelcomeText
    tokens: TokensText
    pers_selection: PersSelectionText
    bot_reboot: str
    error: str
    specialties: SpecialtiesText
    custom_personality: CustomPersonalityText


class BotSettings:

    _CONFIGS_MAP = dict()
    _CONFIG_PATH = 'resources/config.json'
    _PERSONALITIES_PATH = 'resources/personalities.json'
    _MESSAGES_PATH = 'resources/messages.json'
    _TOKENS_PACKAGES_PATH = 'resources/tokens_packages.json'

    def __init__(self):
        self.load()

    @property
    def config(self) -> BotConfig:
        return self._CONFIGS_MAP['config']

    @property
    def messages(self) -> MessagesConfig:
        return self._CONFIGS_MAP['messages']

    @property
    def personalities(self) -> Dict[str, PersonalityConfig]:
        return self._CONFIGS_MAP['personalities']

    @property
    def tokens_packages(self) -> Dict[str, TokensPackageConfig]:
        return self._CONFIGS_MAP['tokens_packages']

    def load(self):
        with open(self._CONFIG_PATH) as file:
            self._CONFIGS_MAP['config'] = BotConfig(**json.load(file))
            logger.info(f"Main config loaded. Last messages count: {self.config}")
        with open(self._PERSONALITIES_PATH) as file:
            _personalities = json.load(file)
            _personalities = {k: PersonalityConfig(**v) for k, v in _personalities.items()}
            self._CONFIGS_MAP['personalities'] = _personalities
            logger.info(f"Personalities config loaded. Count: {len(self.personalities.keys())}")
        with open(self._MESSAGES_PATH) as file:
            self._CONFIGS_MAP['messages'] = MessagesConfig(**json.load(file))
            logger.info(f"Messaged config loaded.")
        with open(self._TOKENS_PACKAGES_PATH) as file:  # Dumb way to store users, must be changed to Postgres
            _tokens_packages = json.load(file)
            _tokens_packages = {k: TokensPackageConfig(**v) for k, v in _tokens_packages.items()}
            self._CONFIGS_MAP['tokens_packages'] = _tokens_packages
            logger.info(f"Tokens packages config loaded. Types: {list(self.tokens_packages.keys())}")


if __name__ == '__main__':
    bot_settings = BotSettings()
    print(bot_settings.config)
    print(bot_settings.tokens_packages)
