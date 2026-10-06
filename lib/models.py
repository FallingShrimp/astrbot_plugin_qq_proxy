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
