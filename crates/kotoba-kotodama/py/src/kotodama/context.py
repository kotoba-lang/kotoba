"""Minimal Context shim for in-progress handlers.

Two handlers (`contracts.py`, `houbun.py`) reference `kotodama.context.Context`
while the real Context wiring is still under design. Until that lands,
this shim lets the module graph import cleanly so the rest of the UDF
pool (bpmn, shinka, classify_t3, gmail_contact, news_translate,
mangaka_storyboard) can boot.

Any handler that actually calls `ctx.db.*` or `ctx.logger()` at runtime
raises NotImplementedError — the failure surfaces at invocation, not at
server startup. This is deliberate: we don't want one in-progress
handler to take down the whole UDF server.
"""

from __future__ import annotations

import logging
from typing import Any


class _UnwiredDb:
    async def fetchrow(self, *_args: Any, **_kw: Any) -> None:
        raise NotImplementedError(
            "kotodama.context.Context.db is not wired yet. "
            "contracts/houbun handlers cannot run in this build."
        )

    async def fetch(self, *_args: Any, **_kw: Any) -> None:
        raise NotImplementedError(
            "kotodama.context.Context.db is not wired yet."
        )

    async def execute(self, *_args: Any, **_kw: Any) -> None:
        raise NotImplementedError(
            "kotodama.context.Context.db is not wired yet."
        )

    async def executemany(self, *_args: Any, **_kw: Any) -> None:
        raise NotImplementedError(
            "kotodama.context.Context.db is not wired yet."
        )


class Context:
    """Placeholder for per-NSID request context.

    Real wiring will give each handler an asyncpg pool + structured
    logger. Until then this is a stub that imports cleanly.
    """

    def __init__(self, nsid: str) -> None:
        self.nsid = nsid
        self.db = _UnwiredDb()
        self._logger = logging.getLogger(f"kotodama.ctx.{nsid}")

    def logger(self) -> logging.Logger:
        return self._logger
