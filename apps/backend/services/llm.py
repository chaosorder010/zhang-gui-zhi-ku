from langchain_openai import ChatOpenAI

from apps.backend.core.config import get_settings


def build_llm():
    s = get_settings()
    return ChatOpenAI(
        model=s.openai_model,
        api_key=s.openai_api_key,
        base_url=s.openai_base_url,
        temperature=0.2,
    )
