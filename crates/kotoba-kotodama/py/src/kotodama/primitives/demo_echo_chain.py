"""Tiny row-driven LangGraph primitives for v2 verification.

Used by topology-mode loader tests and by the staging seed example. These
nodes intentionally have no external dependencies so they can be exercised
in CI without hitting RisingWave / LLM / network.

Wire shape:
    state: dict
    node returns: partial dict merged into state by LangGraph default reducer
"""

from __future__ import annotations

from typing import Any


async def step_echo(state: dict[str, Any]) -> dict[str, Any]:
    """Copy ``state['input']`` to ``state['echo']``."""
    return {"echo": state.get("input", "")}


async def step_count(state: dict[str, Any]) -> dict[str, Any]:
    """Append the length of ``echo`` to state."""
    return {"length": len(state.get("echo", ""))}


def route_by_length(state: dict[str, Any]) -> str:
    """Conditional router: return 'short' if length < 5 else 'long'."""
    return "short" if state.get("length", 0) < 5 else "long"


async def step_short(state: dict[str, Any]) -> dict[str, Any]:
    return {"bucket": "short"}


async def step_long(state: dict[str, Any]) -> dict[str, Any]:
    return {"bucket": "long"}


async def step_classify_bucket(state: dict[str, Any]) -> dict[str, Any]:
    """Classify length → bucket, set as a state field. Used by field-based
    conditional-edge tests (ADR-2605082000 Phase D) so routing happens
    via state lookup, not a Python router callable."""
    return {"bucket": "short" if state.get("length", 0) < 5 else "long"}
