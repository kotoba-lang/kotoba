"""Shared helpers for kafun-bokumetsu LangGraph chains.

Path-based actor DIDs (ADR-0019):
  did:web:n97ik10n.etzhayyim.com                     — controller (Fund)
  did:web:n97ik10n.etzhayyim.com:actor:researcher    — research output author
  did:web:n97ik10n.etzhayyim.com:actor:proposer      — think output author
  did:web:n97ik10n.etzhayyim.com:actor:executor      — tick output author

Persistence is OUT OF SCOPE here — graphs only return rows. Pod-side
LangServer handlers write through the runtime data boundary (ADR-0036).
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

import httpx


KAFUN_CONTROLLER_DID = "did:web:n97ik10n.etzhayyim.com"
RESEARCHER_DID = f"{KAFUN_CONTROLLER_DID}:actor:researcher"
PROPOSER_DID = f"{KAFUN_CONTROLLER_DID}:actor:proposer"
EXECUTOR_DID = f"{KAFUN_CONTROLLER_DID}:actor:executor"

_LLM_URL = os.environ.get("etzhayyim_LLM_URL", "https://murakumo.etzhayyim.com/v1/chat/completions")
_LLM_KEY = os.environ.get("etzhayyim_LLM_API_KEY", "sk-murakumo-local")
_LLM_MODEL = os.environ.get("KAFUN_LLM_MODEL", os.environ.get("etzhayyim_LLM_MODEL", "qwen3-vl-8b"))


async def llm(prompt: str, *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            _LLM_URL,
            headers={"Authorization": f"Bearer {_LLM_KEY}"},
            json={
                "model": _LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
    return r.json()["choices"][0]["message"]["content"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rkey(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:24]


def vertex_id(did: str, kind: str, key: str) -> str:
    return f"at://{did}/com.etzhayyim.apps.kafun.{kind}/{key}"
