from abc import ABC

from app.settings import ImageGenModelConfig


class BaseAudioModel(ABC):

    def __init__(self, config: ImageGenModelConfig):
        self.config = config
