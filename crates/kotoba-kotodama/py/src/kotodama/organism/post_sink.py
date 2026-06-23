"""Post-sink implementations for Organism.

Per ADR-2605240100. Substrate-boundary-honoring: the Python side writes
to a queue (file or logger); the TS-side drainer (@etzhayyim/sdk) reads
the queue and dispatches to AT Protocol PDS.

Three sinks:
  - ``LoggerPostSink``: default; emits an INFO log line per post.
  - ``NdjsonQueuePostSink``: appends one JSON object per line to an
    append-only NDJSON file. Drainer consumes this.
  - ``NullPostSink``: discards posts (for tests / dry-run).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from kotodama.organism.joucho import Mood

logger = logging.getLogger("kotodama.organism.post_sink")


SCHEMA_VERSION = 1
DEFAULT_LEXICON = "app.bsky.feed.post"


class PostSinkContext(Protocol):
    """Minimal protocol an organism passes when emitting a post.

    Kept narrow so sinks don't need a Organism reference.
    """

    code: str
    title: str
    actor_did: str


class PostSink(Protocol):
    """Pluggable sink. Takes the rendered post text + organism context."""

    def __call__(
        self,
        text: str,
        *,
        ctx: PostSinkContext,
        mood: Mood,
        content_source_kind: str,
    ) -> None:  # pragma: no cover
        ...


# ── LoggerPostSink (default) ──────────────────────────────────────────


class LoggerPostSink:
    """Emits INFO log line per post. Default sink; no substrate side-effect."""

    def __call__(
        self,
        text: str,
        *,
        ctx: PostSinkContext,
        mood: Mood,
        content_source_kind: str,
    ) -> None:
        logger.info(
            "shinka c%s [%s/%s]: %s",
            ctx.code,
            mood,
            content_source_kind,
            text,
        )


# ── NullPostSink (tests / dry-run) ────────────────────────────────────


class NullPostSink:
    """Discards posts. For tests + dry-run."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(
        self,
        text: str,
        *,
        ctx: PostSinkContext,
        mood: Mood,
        content_source_kind: str,
    ) -> None:
        self.count += 1


# ── NdjsonQueuePostSink (substrate bridge) ────────────────────────────


class NdjsonQueuePostSink:
    """Appends one NDJSON line per post to the queue file.

    Thread-safe: a single ``threading.Lock`` serializes writes from
    concurrent organism ticks (fleet cells tick organisms sequentially
    inside one asyncio task, but the lock makes this sink safe for any
    caller).

    The queue file is opened in ``O_APPEND`` mode each write, so atomic
    line writes are guaranteed on POSIX even if multiple processes share
    the file (POSIX writes ≤ PIPE_BUF on the same fd are atomic; one
    JSON line is well under PIPE_BUF on every modern kernel).

    Line schema = ADR-2605240100 §Line schema (v=1).
    """

    def __init__(self, path: str | Path, *, lexicon: str = DEFAULT_LEXICON) -> None:
        self.path = Path(path)
        self.lexicon = lexicon
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch so the drainer can `tail -f` even before the first post.
        self.path.touch(exist_ok=True)
        self.write_count = 0
        self.error_count = 0

    def _now(self) -> tuple[int, str]:
        now = time.time()
        return int(now * 1000), datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def __call__(
        self,
        text: str,
        *,
        ctx: PostSinkContext,
        mood: Mood,
        content_source_kind: str,
    ) -> None:
        ts_ms, created_at = self._now()
        line = json.dumps(
            {
                "v": SCHEMA_VERSION,
                "ts": ts_ms,
                "actorDid": ctx.actor_did,
                "code": ctx.code,
                "title": ctx.title,
                "mood": mood,
                "contentSourceKind": content_source_kind,
                "text": text,
                "lexicon": self.lexicon,
                "createdAt": created_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self.write_count += 1
        except Exception as exc:  # noqa: BLE001 — never let sink crash a tick
            self.error_count += 1
            logger.warning("NdjsonQueuePostSink write failed: %s", exc)


# ── Sink resolution from env ──────────────────────────────────────────


def _default_queue_path() -> Path:
    # Production: emptyDir mount under /var/lib/etzhayyim/organism-posts/
    # Dev: writable directory under ~/.etzhayyim/log/organism-posts/
    explicit = os.environ.get("UNISPSC_ORGANISM_POST_QUEUE_PATH")
    if explicit:
        return Path(explicit)
    shard = os.environ.get("UNISPSC_ORGANISM_SHARD_INDEX", "0")
    if Path("/var/lib").is_dir() and os.access("/var/lib", os.W_OK):
        return Path(f"/var/lib/etzhayyim/organism-posts/shard-{shard}.ndjson")
    home = Path.home() / ".etzhayyim" / "log" / "organism-posts"
    return home / f"shard-{shard}.ndjson"


# Compat alias matching the existing Organism contract (text-only sink)
LegacyTextSink = Callable[[str], None]


def resolve_post_sink() -> PostSink:
    """Resolve sink from env vars.

    UNISPSC_ORGANISM_POST_SINK ∈ {ndjson, logger, null} (default: logger)
    UNISPSC_ORGANISM_POST_QUEUE_PATH = /...  (only used for ndjson)
    """
    kind = os.environ.get("UNISPSC_ORGANISM_POST_SINK", "logger").lower()
    if kind == "null":
        return NullPostSink()
    if kind == "ndjson":
        path = _default_queue_path()
        sink = NdjsonQueuePostSink(path)
        logger.info("organism post sink: NDJSON queue at %s", path)
        return sink
    return LoggerPostSink()


def adapt_legacy_text_sink(sink: PostSink) -> LegacyTextSink:
    """Wrap a context-aware sink into the legacy ``Callable[[str], None]``.

    The pre-ADR-2605240100 Organism.post_sink signature is text-only.
    Until the wrapper is migrated end-to-end, we provide a closure that
    captures organism context from the call site.
    """

    def _legacy(text: str) -> None:
        sink(text, ctx=_AnonymousCtx(), mood="neutral", content_source_kind="legacy")

    return _legacy


class _AnonymousCtx:
    """Fallback context when a legacy sink is used outside an organism."""

    code = "00000000"
    title = "unknown"
    actor_did = "did:web:etzhayyim.com:actor:c00000000"


__all__ = [
    "DEFAULT_LEXICON",
    "LegacyTextSink",
    "LoggerPostSink",
    "NdjsonQueuePostSink",
    "NullPostSink",
    "PostSink",
    "PostSinkContext",
    "SCHEMA_VERSION",
    "adapt_legacy_text_sink",
    "resolve_post_sink",
]
