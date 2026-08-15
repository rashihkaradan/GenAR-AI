"""Provider-neutral structured-output client abstractions. API keys stay in env vars."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class ModelClient(ABC):
    """Interface implemented by interchangeable model providers."""

    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        """Return a parsed structured response matching the supplied schema."""


class OpenAIResponsesClient(ModelClient):
    """Optional OpenAI Responses adapter; requires OPENAI_API_KEY at runtime only."""

    def __init__(self, *, model: str | None = None, api_key_env: str = "OPENAI_API_KEY") -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Set {api_key_env} before creating OpenAIResponsesClient.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the OpenAI Python SDK to use OpenAIResponsesClient.") from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-5")

    def generate(self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=user_prompt,
            text={"format": {"type": "json_schema", "name": response_schema["name"], "schema": response_schema["schema"], "strict": True}},
        )
        return json.loads(response.output_text)


class StaticModelClient(ModelClient):
    """Test-only client that returns a configured structured response without any network call."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def generate(self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        return self.response
