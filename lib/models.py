import asyncio
import random
from typing import Literal, TypedDict

from pydantic import BaseModel


class ServerConfig(BaseModel):
    port: int
    host: str
    name: str


class ModelConfig(BaseModel):
    uid: str
    id: str
    name: str
    group: str | None = None


class MessagePart(TypedDict):
    role: Literal["user"] | Literal["assistant"] | Literal["system"]
    content: str


class ResponseState:
    def __init__(self, status: bool, source: ModelConfig, id: str) -> None:
        self.status: bool = status
        self.source: ModelConfig = source
        self.id: str = id
        self.out_count = random.randint(2, 6)
        self.in_count = random.randint(3, 5)
        self.outed = 0
        self.ined = 0
        self.queue = asyncio.Queue[str]()

    def is_started(self) -> bool:
        return (
            self.status and self.outed >= self.out_count and self.ined < self.in_count
        )

    def stop(self):
        self.status = False
        self.queue.put_nowait("")

    def upload(self, data: str):
        if self.status:
            if data == f"{self.id} out":
                self.outed += 1
            elif data == f"{self.id} in":
                self.ined += 1
            elif self.is_started():
                self.queue.put_nowait(data)
            else:
                self.outed = 0
                self.ined = 0
        else:
            self.queue.put_nowait(data)

    async def pop(self, timeout: float):
        return await asyncio.wait_for(self.queue.get(), timeout)
