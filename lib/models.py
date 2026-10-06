import asyncio
from typing import Literal, TypedDict

from pydantic import BaseModel

from astrbot.api import logger


class ModelConfig(BaseModel):
    uid: str
    id: str
    name: str
    group: str | None = None


class ServerConfig(BaseModel):
    port: int
    host: str
    name: str
    apikeys: list[str]


class PluginConfig(BaseModel):
    server: ServerConfig
    models: list[ModelConfig]
    default_model: str
    timeout: float
    notice: bool


class MessagePart(TypedDict):
    role: Literal["user"] | Literal["assistant"] | Literal["system"]
    content: str


class ResponseState:
    def __init__(self, status: bool, source: ModelConfig, id: str) -> None:
        self.status: bool = status
        self.source: ModelConfig = source
        self.id: str = id
        self.queue = asyncio.Queue[str]()

    def stop(self):
        self.status = False
        self.upload("")

    def upload(self, data: str):
        self.queue.put_nowait(data)
        logger.info(f"正在上传“{data}”")

    async def pop(self, timeout: float):
        return await asyncio.wait_for(self.queue.get(), timeout)
