"""LLM client wrapping Hugging Face Inference Providers (OpenAI-compatible)."""
from __future__ import annotations

from huggingface_hub import InferenceClient

from advisor.config import settings

_client: InferenceClient | None = None


def get_client() -> InferenceClient:
    global _client
    if _client is None:
        _client = InferenceClient(provider=settings.llm_provider, api_key=settings.hf_token)
    return _client


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    """Run a chat completion. Returns the raw OpenAI-shaped response object."""
    kwargs: dict = {
        "model": settings.llm_model_id,
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.llm_temperature,
        "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return get_client().chat.completions.create(**kwargs)


def chat_text(messages: list[dict], **kwargs) -> str:
    """Convenience wrapper that returns only the assistant text."""
    resp = chat(messages, **kwargs)
    return resp.choices[0].message.content or ""
