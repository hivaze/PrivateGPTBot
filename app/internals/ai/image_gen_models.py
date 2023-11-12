from abc import ABC

from app.settings import ImageGenModelConfig


class BaseImageGenModel(ABC):

    def __init__(self, config: ImageGenModelConfig):
        self.config = config
