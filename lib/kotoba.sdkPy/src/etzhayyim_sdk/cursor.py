"""AT Protocol firehose cursor with EDN checkpoint persistence."""

from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlencode, urlparse, urlunparse

import cbor2
import websockets


def _checkpoint_path(cursor_id: str) -> Path:
    root = Path(os.environ.get("ETZHAYYIM_CURSOR_DIR", Path.home() / ".local/state/etzhayyim/cursors"))
    safe = "".join(c for c in cursor_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("cursor_id must contain a safe character")
    return root / f"{safe}.edn"


def _load(path: Path) -> int | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    prefix = "{:cursor/seq "
    if not text.startswith(prefix) or not text.endswith("}"):
        raise ValueError(f"invalid cursor EDN: {path}")
    return int(text[len(prefix):-1])


def _store(path: Path, seq: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".edn.tmp")
    temporary.write_text(f"{{:cursor/seq {seq}}}\n", encoding="utf-8")
    temporary.replace(path)


def _firehose_url(cursor: int | None) -> str:
    base = os.environ.get("ETZHAYYIM_PDS_URL", "https://pds.etzhayyim.com")
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = urlencode({"cursor": cursor}) if cursor is not None else ""
    return urlunparse((scheme, parsed.netloc, "/xrpc/com.atproto.sync.subscribeRepos", "", query, ""))


def _decode_frame(frame: bytes) -> dict[str, Any] | None:
    decoder = cbor2.CBORDecoder(io.BytesIO(frame))
    header = decoder.decode()
    body = decoder.decode()
    if not isinstance(header, dict) or header.get("op") != 1 or not isinstance(body, dict):
        return None
    return body


async def subscribe_with_checkpoint(
    *,
    cursor_id: str,
    collections: list[str] | None = None,
    checkpoint_every: int = 100,
    checkpoint_interval_s: float = 30.0,
) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded commit events and atomically persist their sequence in EDN."""
    path = _checkpoint_path(cursor_id)
    cursor = _load(path)
    since_store = 0
    last_store = time.monotonic()
    async with websockets.connect(_firehose_url(cursor), max_size=None) as socket:
        async for frame in socket:
            if not isinstance(frame, bytes):
                continue
            event = _decode_frame(frame)
            if event is None:
                continue
            if collections is not None:
                event["ops"] = [
                    op for op in event.get("ops", [])
                    if isinstance(op, dict) and str(op.get("path", "")).partition("/")[0] in collections
                ]
            seq = event.get("seq")
            yield event
            if isinstance(seq, int):
                cursor = seq
                since_store += 1
            now = time.monotonic()
            if cursor is not None and (since_store >= checkpoint_every or now - last_store >= checkpoint_interval_s):
                _store(path, cursor)
                since_store = 0
                last_store = now
    if cursor is not None:
        _store(path, cursor)
