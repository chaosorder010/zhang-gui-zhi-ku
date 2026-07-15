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

    # MinerU
    mineru_api_key: str = ""
    mineru_base_url: str = "https://mineru.net/api/v4"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: str = "19530"
    milvus_collection: str = "zgzk"

    # CORS
    cors_origins: list[str] = ["*"]

    # History
    history_max_turns: int = 10

    # HyDE 检索 (Hypothetical Document Embeddings)
    # 默认关闭;开启后 retrieve 节点会生成假设答案并与原始检索 RRF 融合
    enable_hyde: bool = False
    hyde_prompt_template: str = (
        "请仅根据用户的问题,写出一段简洁、事实性的假设答案(约 80~150 字).\n"
        '要求:仅输出答案正文,不要出现"假设""可能"等元话语.\n\n'
        "用户问题:{question}\n\n假设答案:"
    )

    # Rerank
    enable_rerank: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
