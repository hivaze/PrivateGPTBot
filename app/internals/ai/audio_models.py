from abc import ABC

from app.settings import AudioModelConfig


class BaseAudioModel(ABC):

    def __init__(self, config: AudioModelConfig):
        self.config = config
