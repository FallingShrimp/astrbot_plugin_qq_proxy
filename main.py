from astrbot.api.star import Context, Star

from .lib.manager import models
from .lib.model import ModelConfig


class PluginQQProxy(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        for model in config["models"]:
            models.append(ModelConfig.model_validate(model))
        self.logger.info(f"Models: {models}")
