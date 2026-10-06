import time
from collections.abc import AsyncGenerator

from astrbot.api.star import Context, Star

from .lib import manager
from .lib.models import ModelConfig, ServerConfig
from .lib.server import ProxyServer


class PluginQQProxy(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        manager.server = ServerConfig.model_validate(config["server"])
        manager.default_model = config["default_model"]
        manager.active_time = time.time()
        for model in config["models"]:
            manager.models.append(ModelConfig.model_validate(model))
        for key in config["apikeys"]:
            manager.apikeys.append(key)
        self.logger.info(f"Models: {manager.models}")
        self.server = ProxyServer(self.model_call)

    async def model_call(self, model: ModelConfig) -> AsyncGenerator[str]:
        for token in "你是一个一个一个一个sb":
            yield token
