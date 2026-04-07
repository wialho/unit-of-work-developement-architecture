from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from workflow_runtime.config import Settings


class LLMRequest(BaseModel):
    system_prompt: str | None = None
    user_prompt: str
    temperature: float = 0.1
    max_tokens: int | None = None


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    metadata: dict[str, object] = Field(default_factory=dict)


class LLMClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    async def close(self) -> None:
        ...


class OllamaLLMClient:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(timeout=120)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        prompt = request.user_prompt
        if request.system_prompt:
            prompt = f"{request.system_prompt}\n\n{request.user_prompt}"

        response = await self._client.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    **({"num_predict": request.max_tokens} if request.max_tokens else {}),
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        return LLMResponse(
            text=payload.get("response", ""),
            model=self._model,
            provider="ollama",
            metadata={"done": payload.get("done"), "total_duration": payload.get("total_duration")},
        )

    async def close(self) -> None:
        await self._client.aclose()


class OpenAICompatibleLLMClient:
    def __init__(self, base_url: str, model: str, api_key: str | None) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        headers = {"authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(timeout=120, headers=headers)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens:
            body["max_tokens"] = request.max_tokens

        response = await self._client.post(f"{self._base_url}/chat/completions", json=body)
        response.raise_for_status()
        payload = response.json()
        choice = payload["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            model=payload.get("model", self._model),
            provider="openai_compatible",
            metadata={"finish_reason": choice.get("finish_reason"), "usage": payload.get("usage")},
        )

    async def close(self) -> None:
        await self._client.aclose()


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaLLMClient(settings.llm_base_url, settings.llm_model)
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_key,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
