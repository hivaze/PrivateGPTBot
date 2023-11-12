import json
import logging
from typing import List, Dict

from pydantic import BaseModel

logger = logging.getLogger(__name__)


##### Main configuration


class DocumentsConfig(BaseModel):
    summary_blocks: int
    search_best_k: int
    blocks_size: int


class EmbeddingsModelConfig(BaseModel):
    model_name: str
    max_retries: int
    embedding_ctx_length: int


class AudioModelConfig(BaseModel):
    type: str
    model_name: str


class ImageGenModelConfig(BaseModel):
    type: str
    model_name: str
    size: str
    quality: str


class ChatModelConfig(BaseModel):
    type: str
    max_context_size: int
    model_name: str
    tokens_scale: float
    generation_params: dict


class TokensPackagesConfig(BaseModel):
    by_default: str
    as_first: str


class ModelsConfig(BaseModel):
    small_context: ChatModelConfig
    long_context: ChatModelConfig
    superior: ChatModelConfig


class BotConfig(BaseModel):
    OPENAI_KEY: str
    TG_BOT_TOKEN: str
    embeddings_model: EmbeddingsModelConfig
    audio_transcript_model: AudioModelConfig
    image_gen_model: ImageGenModelConfig
    models: ModelsConfig
    last_messages_count: int
    global_mode: bool
    free_mode: bool
    tokens_packages: TokensPackagesConfig
    admins: List[str]
    bot_max_users_memory: int
    instant_messages_waiting: int
    append_tokens_count: bool
    openai_api_retries: int
    documents: DocumentsConfig

##### Personalities


class PersonalityConfig(BaseModel):
    location: str
    name: dict
    context: str


##### Tokens packages


class TokensPackageConfig(BaseModel):
    level: int
    long_context: bool
    superior_model: bool
    use_functions: bool
    use_superior_as_default: bool
    stt_minutes: bool
    max_image_gens: int
    tokens: int
    price: int
    duration: str


##### Messages

class Welcome(BaseModel):
    with_access: Dict[str, str]
    no_access: Dict[str, str]


class Session(BaseModel):
    zero_state: Dict[str, str]
    end: Dict[str, str]


class Documents(BaseModel):
    not_allowed: Dict[str, str]
    not_supported: Dict[str, str]
    loading: Dict[str, str]
    loaded: Dict[str, str]


class MainMenu(BaseModel):
    info: Dict[str, str]
    mistake: Dict[str, str]
    about: Dict[str, str]
    settings: Dict[str, str]
    feedback: Dict[str, str]
    specialities: Dict[str, str]


class SettingsItemState(BaseModel):
    turn_on: Dict[str, str]
    turn_off: Dict[str, str]


class SettingsMenu(BaseModel):
    info: Dict[str, str]
    cant_use: Dict[str, str]
    allow_global_messages: SettingsItemState
    reactions: SettingsItemState
    tokens_info: SettingsItemState
    use_superior_by_default: SettingsItemState


class SpecialtiesMenu(BaseModel):
    info: Dict[str, str]
    back: Dict[str, str]


class Feedback(BaseModel):
    info: Dict[str, str]
    got: Dict[str, str]
    too_short: Dict[str, str]


class Reactions(BaseModel):
    good: Dict[str, str]
    bad: Dict[str, str]
    liked: Dict[str, str]
    disliked: Dict[str, str]


class RedoModels(BaseModel):
    default: Dict[str, str]
    superior: Dict[str, str]


class Redo(BaseModel):
    default: Dict[str, str]
    superior: Dict[str, str]
    not_allowed: Dict[str, str]
    generating: RedoModels
    error: Dict[str, str]


class CustomPersonality(BaseModel):
    button: Dict[str, str]
    info: Dict[str, str]
    too_short: Dict[str, str]


class Tokens(BaseModel):
    out_of_tokens: Dict[str, str]
    reset: Dict[str, str]
    tokens_count: Dict[str, str]
    running_out: Dict[str, str]
    granted: Dict[str, str]


class PriceList(BaseModel):
    info: Dict[str, str]
    package_info: Dict[str, str]


class Confirmation(BaseModel):
    yes: Dict[str, str]
    no: Dict[str, str]


class MessagesConfig(BaseModel):
    welcome: Welcome
    about_bot_info: Dict[str, str]
    account_info: Dict[str, str]
    reset: Dict[str, str]
    communication_start: Dict[str, str]
    session: Session
    error: Dict[str, str]
    external_data: Dict[str, str]
    documents: Documents
    audio: Dict[str, str]
    main_menu: MainMenu
    settings_menu: SettingsMenu
    specialties_menu: SpecialtiesMenu
    feedback: Feedback
    reactions: Reactions
    redo: Redo
    cont: Dict[str, str]
    time_format: Dict[str, str]
    custom_personality: CustomPersonality
    tokens: Tokens
    price_list: PriceList
    image_upload: Dict[str, str]
    confirmation: Confirmation


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
    print(bot_settings.messages)
    print(bot_settings.tokens_packages)
