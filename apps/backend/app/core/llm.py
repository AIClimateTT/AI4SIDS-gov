import json
from typing import Protocol

from langchain_ollama import ChatOllama

from app.config import settings


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_content: str) -> str: ...


class FakeLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses is not None else None

    def generate(self, system_prompt: str, user_content: str) -> str:
        if self._responses is not None:
            if len(self._responses) > 1:
                return self._responses.pop(0)
            return self._responses[0]
        return self._auto_narrative(user_content)

    def _auto_narrative(self, user_content: str) -> str:
        data = json.loads(user_content)
        lines = []
        for fact in data["facts"]:
            unit = fact["unit"] or ""
            title = fact["metric"].replace("_", " ").title()
            lines.append(f"{title}: {fact['value']} {unit} [{fact['citation']['cid']}].")
        return "\n\n".join(lines)


class OllamaLLMClient:
    def __init__(self, base_url: str, model: str, chat: "ChatOllama | None" = None):
        self._chat = chat or ChatOllama(base_url=base_url, model=model)

    def generate(self, system_prompt: str, user_content: str) -> str:
        messages = [("system", system_prompt), ("human", user_content)]
        response = self._chat.invoke(messages)
        return response.content


def get_default_llm_client() -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaLLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)
    return FakeLLMClient()
