from pydantic import BaseModel


class ModelConfig(BaseModel):
    uid: str
    id: str
    name: str
    session: str
