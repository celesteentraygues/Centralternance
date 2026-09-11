from typing import Any, Protocol

from openai import OpenAIError
from pydantic import ValidationError

from app.config import (
    MSG_GENERATION,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
)
from app.prompts import Message, build_lettre_prompt, build_spontane_prompt
from app.schemas import GenerateRequest, SpontaneResponse


class GenerationError(Exception):
    """Erreur OpenAI, réponse vide ou JSON invalide."""


class ChatClient(Protocol):
    chat: Any  # openai.OpenAI ou FakeOpenAI en test


def _call(client: ChatClient, messages: list[Message], *, json_mode: bool = False) -> str:
    extra: dict[str, Any] = {}
    if json_mode:
        extra["response_format"] = {"type": "json_object"}
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            timeout=OPENAI_TIMEOUT_SECONDS,
            **extra,
        )
    except OpenAIError as exc:
        raise GenerationError(MSG_GENERATION) from exc

    content = completion.choices[0].message.content
    if not content or not content.strip():
        raise GenerationError(MSG_GENERATION)
    return content.strip()


def generate_lettre(client: ChatClient, req: GenerateRequest) -> str:
    return _call(client, build_lettre_prompt(req))


def generate_spontane(client: ChatClient, req: GenerateRequest) -> SpontaneResponse:
    raw = _call(client, build_spontane_prompt(req), json_mode=True)
    try:
        return SpontaneResponse.model_validate_json(raw)
    except ValidationError as exc:
        raise GenerationError(MSG_GENERATION) from exc
