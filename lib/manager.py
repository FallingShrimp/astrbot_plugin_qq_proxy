from .models import ModelConfig, ServerConfig

models: list[ModelConfig] = []
apikeys: list[str] = []
server: ServerConfig
default_model: str = ""
active_time: float = 0
timeout: int = 30
