import json
import time
from typing import Protocol
from urllib.parse import urlparse

from langchain_ollama import ChatOllama

from app.config import settings

# #region agent log
_DEBUG_LOG_PATH = "/Users/devonmurray/just-projects/AI4SIDS-repos/gov/.cursor/debug-33839c.log"


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "sessionId": "33839c",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass


# #endregion


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_content: str) -> str: ...


class FakeLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses is not None else None

    def generate(self, system_prompt: str, user_content: str) -> str:
        # #region agent log
        _agent_log(
            "D",
            "llm.py:FakeLLMClient.generate",
            "fake llm generate called",
            {"system_prompt_len": len(system_prompt), "user_content_len": len(user_content)},
        )
        # #endregion
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
        self._base_url = base_url
        self._model = model
        self._chat = chat or ChatOllama(
            base_url=base_url, model=model, num_ctx=settings.ollama_num_ctx
        )

    def generate(self, system_prompt: str, user_content: str) -> str:
        # #region agent log
        parsed = urlparse(self._base_url)
        _agent_log(
            "A",
            "llm.py:OllamaLLMClient.generate",
            "ollama generate starting",
            {
                "base_url": self._base_url,
                "hostname": parsed.hostname,
                "port": parsed.port,
                "scheme": parsed.scheme,
                "model": self._model,
            },
        )
        # #endregion
        try:
            messages = [("system", system_prompt), ("human", user_content)]
            response = self._chat.invoke(messages)
            # #region agent log
            _agent_log(
                "A",
                "llm.py:OllamaLLMClient.generate",
                "ollama generate succeeded",
                {"content_len": len(getattr(response, "content", "") or "")},
            )
            # #endregion
            return response.content
        except Exception as exc:
            # #region agent log
            _agent_log(
                "B",
                "llm.py:OllamaLLMClient.generate",
                "ollama generate failed",
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "base_url": self._base_url,
                    "hostname": urlparse(self._base_url).hostname,
                },
            )
            # #endregion
            raise


def get_default_llm_client() -> LLMClient:
    # #region agent log
    parsed = urlparse(settings.ollama_base_url)
    _agent_log(
        "E",
        "llm.py:get_default_llm_client",
        "resolving default llm client",
        {
            "llm_provider": settings.llm_provider,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "hostname": parsed.hostname,
            "hostname_empty": not bool(parsed.hostname),
            "app_env": settings.app_env,
        },
    )
    # #endregion
    if settings.llm_provider == "ollama":
        return OllamaLLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)
    return FakeLLMClient()
