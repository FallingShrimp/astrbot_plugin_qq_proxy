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
    session: str


class MessagePart(TypedDict):
    role: Literal["user"] | Literal["assistant"] | Literal["system"]
    content: str
