from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "zhang-gui-zhi-ku"
    app_env: str = "dev"
    app_debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # CORS
    cors_origins: list[str] = ["*"]

    # History
    history_max_turns: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
