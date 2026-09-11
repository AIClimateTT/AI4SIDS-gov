import json
from collections.abc import Iterator
from typing import Literal, Protocol

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config import settings

_FAKE_STREAM_CHUNK = 8

# Short names an officer might type, longest first so "San Juan" wins
# over a later "Juan" fragment. Used only by the fake provider.
_CORP_HINTS = (
    ("couva/tabaquite/talparo", "couva_tabaquite_talparo_regiona"),
    ("san juan/laventille", "san_juan_laventille_regional_co"),
    ("tunapuna/piarco", "tunapuna_piarco_regional_corpor"),
    ("mayaro/rio claro", "mayaro_rio_claro_regional_corpo"),
    ("port of spain", "port_of_spain_city_corporation"),
    ("princes town", "princes_town_regional_corporati"),
    ("diego martin", "diego_martin_regional_corporati"),
    ("sangre grande", "sangre_grande_regional_corporat"),
    ("point fortin", "point_fortin_borough_corporatio"),
    ("san fernando", "san_fernando_city_corporation"),
    ("penal/debe", "penal_debe_regional_corporation"),
    ("chaguanas", "chaguanas_borough_corporation"),
    ("siparia", "siparia_regional_corporation"),
    ("arima", "arima_borough_corporation"),
)


def _corp_mentioned(text: str) -> str | None:
    lowered = text.lower()
    found: list[tuple[int, str]] = []
    for hint, slug in _CORP_HINTS:
        idx = lowered.find(hint)
        if idx >= 0:
            found.append((idx, slug))
    if not found:
        return None
    found.sort()
    return found[0][1]


def _assign_fake_corp(row: object, slug: str) -> object:
    if not isinstance(row, dict):
        return row
    next_row = dict(row)
    next_row["corporation"] = slug
    next_row["included"] = True
    return next_row


def _fake_whatsapp_turn(data: dict) -> str:
    working = dict(data.get("working") or {})
    user = str(data.get("user_message") or "")
    slug = _corp_mentioned(user)
    incidents = list(working.get("incidents") or [])
    logs = list(working.get("logs") or [])
    if slug:
        incidents = [_assign_fake_corp(row, slug) for row in incidents]
        logs = [_assign_fake_corp(row, slug) for row in logs]
    return json.dumps(
        {
            "assistant_message": (
                "Updated. Tell me what else to change, or correct anything that looks wrong."
            ),
            "working": {
                "as_at": working.get("as_at"),
                "incidents": incidents,
                "logs": logs,
            },
        }
    )


_FAKE_CAPTURE_JSON = json.dumps(
    {
        "assistant_message": (
            "Captured. Tell me what else to add, or correct anything that looks wrong."
        ),
        "capture": {
            "as_at": None,
            "alert_level": "none",
            "present_activity": None,
            "situation_overview": None,
            "incidents": [],
            "logs": [],
        },
    }
)


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
        try:
            data = json.loads(user_content)
        except json.JSONDecodeError:
            # WhatsApp extract sends a redacted transcript, not fact-table JSON.
            quote = user_content.strip()[:240] or "Pasted context"
            return json.dumps(
                {
                    "incidents": [
                        {
                            "corporation": None,
                            "incident_summary": quote,
                            "source_index": 1,
                            "source_quote": quote,
                        }
                    ],
                    "logs": [],
                }
            )
        if isinstance(data, dict) and (
            "working" in data or "source_kind" in data
        ):
            return _fake_whatsapp_turn(data)
        if isinstance(data, dict) and ("capture" in data or "user_message" in data):
            return _FAKE_CAPTURE_JSON
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


class NimLLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        chat: "ChatOpenAI | None" = None,
    ):
        self._base_url = base_url
        self._model = model
        self._api_key = api_key
        self._chat = chat or ChatOpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            model=model,
            api_key=api_key,
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
    if settings.llm_provider == "nim":
        model = settings.nim_chat_model if purpose == "chat" else settings.nim_model
        return NimLLMClient(
            base_url=settings.nim_base_url,
            model=model,
            api_key=settings.nim_api_key,
        )
    return FakeLLMClient()


def get_default_llm_client() -> LLMClient:
    return get_llm_client("batch")
