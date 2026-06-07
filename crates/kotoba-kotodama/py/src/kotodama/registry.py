"""
NSID → handler registry.

Every @udf-decorated function is registered by its NSID into a single
in-process table. On worker boot, `kotodama.server.serve()` reads this
table and registers each entry with the arrow-udf UdfServer.

Design intent (ADR-0049):
- 1 worker process holds the handler set for ALL Mode A reactive actors
  — there is no per-actor isolation at the process level. Isolation lives
  at the pod level (replicas=2 + PDB + HPA).
- Handlers are stateless per call. State lives in RisingWave via
  `kotodama.db` (mirrors ADR-0036 Worker-direct Hyperdrive).
- `io_threads` is forwarded to the arrow-udf decorator. The GIL caps any
  single process at ~1 CPU, but `io_threads=100` lets 100 LLM / HTTP calls
  overlap during IO wait within a single row-batch.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# arrow-udf is the official RisingWave External Python UDF framework.
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
# See https://docs.risingwave.com/sql/udfs/use-udfs-in-python
try:
    from arrow_udf import udf as _arrow_udf
except ImportError:  # pragma: no cover — arrow-udf is a runtime dep
    _arrow_udf = None


@dataclass(frozen=True)
class HandlerEntry:
    nsid: str
    fn: Callable[..., Any]
    io_threads: int
    capability_tags: tuple[str, ...]
    agent_tool: str | None  # MCP tool description (ADR-0042)


_HANDLERS: dict[str, HandlerEntry] = {}


def udf(
    nsid: str,
    *,
    io_threads: int = 100,
    capability_tags: tuple[str, ...] = (),
    agent_tool: str | None = None,
    input_types: list[str] | None = None,
    result_type: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Register a Python callable as a mitama UDF handler.

    Args:
        nsid: AT Lexicon NSID (e.g. "com.etzhayyim.apps.yabai.classify").
              Must match a lexicon JSON in 00-contracts/lexicons/.
        io_threads: concurrent IO thread count (ADR-0044 default 100).
        capability_tags: forwarded to the MCP tool facade (ADR-0042).
        agent_tool: one-line description for MCP tools/list. If None, the
                    NSID is not exposed as an agent tool.
        input_types / result_type: arrow-udf arrow schema strings. If
                    omitted, inferred from Python type annotations via the
                    arrow-udf framework.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if nsid in _HANDLERS:
            raise ValueError(
                f"NSID {nsid} is already registered by {_HANDLERS[nsid].fn!r}"
            )

        # arrow-udf's `udf` is a decorator factory. Must be called with
        # input_types + result_type, and `name=` so the handler is reachable
        # via its NSID when the arrow-flight server publishes it.
        if _arrow_udf is not None and input_types is not None:
            decorator = _arrow_udf(
                input_types=input_types,
                result_type=result_type,
                io_threads=io_threads,
                name=nsid,
            )
            wrapped = decorator(fn)
        else:
            wrapped = fn

        _HANDLERS[nsid] = HandlerEntry(
            nsid=nsid,
            fn=wrapped,
            io_threads=io_threads,
            capability_tags=capability_tags,
            agent_tool=agent_tool,
        )

        @functools.wraps(fn)
        def passthrough(*args: Any, **kwargs: Any) -> Any:
            return wrapped(*args, **kwargs)

        # Attach metadata for introspection + MCP discovery.
        passthrough.__kotodama_nsid__ = nsid  # type: ignore[attr-defined]
        passthrough.__kotodama_entry__ = _HANDLERS[nsid]  # type: ignore[attr-defined]
        return passthrough

    return decorator


def registered() -> dict[str, HandlerEntry]:
    """Return a read-only view of all registered NSIDs."""
    return dict(_HANDLERS)


def agent_tools() -> list[dict[str, Any]]:
    """
    Emit the MCP tools/list payload (ADR-0042) for all @udf handlers that
    declared `agent_tool=...`.
    """
    out: list[dict[str, Any]] = []
    for entry in _HANDLERS.values():
        if not entry.agent_tool:
            continue
        sig = inspect.signature(entry.fn)
        out.append(
            {
                "name": entry.nsid,
                "description": entry.agent_tool,
                "capability_tags": list(entry.capability_tags),
                "parameters": list(sig.parameters.keys()),
            }
        )
    return out
