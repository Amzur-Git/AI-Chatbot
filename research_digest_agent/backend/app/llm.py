from __future__ import annotations

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from .config import get_settings


def get_chat_llm(temperature: float = 0.1) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=temperature,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
