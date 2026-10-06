from astrbot.api.star import Context, Star

from .lib import manager
from .lib.models import ModelConfig, ServerConfig


class PluginQQProxy(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        for model in config["models"]:
            manager.models.append(ModelConfig.model_validate(model))
        manager.server = ServerConfig.model_validate(config["server"])
        for key in config["apikeys"]:
            manager.apikeys.append(key)
        self.logger.info(f"Models: {manager.models}")
