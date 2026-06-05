import json

import httpx

from app.config import settings


async def complete_json(messages: list[dict]) -> dict | None:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return await _ollama_complete(messages)
    if provider == "openai" and settings.openai_api_key:
        return await _openai_complete(messages)
    return None


async def _ollama_complete(messages: list[dict]) -> dict | None:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": "llama3.2",
                "messages": messages,
                "format": "json",
                "stream": False,
            },
        )
        if response.status_code != 200:
            return None
        content = response.json().get("message", {}).get("content", "{}")
        return json.loads(content)


async def _openai_complete(messages: list[dict]) -> dict | None:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "response_format": {"type": "json_object"},
            },
        )
        if response.status_code != 200:
            return None
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
