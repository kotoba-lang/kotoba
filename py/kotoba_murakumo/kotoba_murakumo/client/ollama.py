"""Ollama-direct client.

Ollama exposes the OpenAI-compatible endpoint at ``/v1/chat/completions`` so
the wire format is identical to :mod:`kotoba_murakumo.client.litellm`. We
keep a separate module so R2 can wire Ollama-specific knobs (``num_ctx``,
``num_gpu``, ``keep_alive``) without touching the LiteLLM signature.

Used for the own-node ``gemma3:4b`` fallback per ``fleet.toml``
``failover.on_unreachable``.
"""

from __future__ import annotations

from typing import Any

from . import litellm as _litellm


def chat_completions(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
) -> str:
    """Synchronous chat-completions against own-node Ollama (no bearer auth)."""
    return _litellm.chat_completions(
        url=url, model=model, messages=messages,
        auth_bearer=None, max_tokens=max_tokens, timeout_s=timeout_s,
    )


async def chat_completions_async(
    *,
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
) -> str:
    return await _litellm.chat_completions_async(
        url=url, model=model, messages=messages,
        auth_bearer=None, max_tokens=max_tokens, timeout_s=timeout_s,
    )
