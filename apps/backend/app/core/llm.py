import json
from collections.abc import Iterator
from typing import Literal, Protocol

from langchain_ollama import ChatOllama

from app.config import settings

_FAKE_STREAM_CHUNK = 8


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_content: str) -> str: ...

    def generate_stream(
        self, system_prompt: str, user_content: str
    ) -> Iterator[str]: ...


class FakeLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses is not None else None

    def generate(self, system_prompt: str, user_content: str) -> str:
        if self._responses is not None:
            if len(self._responses) > 1:
                return self._responses.pop(0)
            return self._responses[0]
        return self._auto_narrative(user_content)

    def generate_stream(self, system_prompt: str, user_content: str) -> Iterator[str]:
        text = self.generate(system_prompt, user_content)
        if not text:
            return
        for start in range(0, len(text), _FAKE_STREAM_CHUNK):
            yield text[start : start + _FAKE_STREAM_CHUNK]

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
        self._base_url = base_url
        self._model = model
        self._chat = chat or ChatOllama(
            base_url=base_url, model=model, num_ctx=settings.ollama_num_ctx
        )

    def generate(self, system_prompt: str, user_content: str) -> str:
        messages = [("system", system_prompt), ("human", user_content)]
        response = self._chat.invoke(messages)
        return response.content

    def generate_stream(self, system_prompt: str, user_content: str) -> Iterator[str]:
        messages = [("system", system_prompt), ("human", user_content)]
        for chunk in self._chat.stream(messages):
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                yield content


def get_llm_client(purpose: Literal["batch", "chat"] = "batch") -> LLMClient:
    if settings.llm_provider == "ollama":
        model = settings.ollama_chat_model if purpose == "chat" else settings.ollama_model
        return OllamaLLMClient(base_url=settings.ollama_base_url, model=model)
    return FakeLLMClient()


def get_default_llm_client() -> LLMClient:
    return get_llm_client("batch")
