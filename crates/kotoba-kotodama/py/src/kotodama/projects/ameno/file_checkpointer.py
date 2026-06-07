"""file_checkpointer.py — Disk-persisted MemorySaver for the daemon.

Mirrors the TS daemon's FileCheckpointer (ADR-2605191229). When
@etzhayyim/sdk/checkpointer (MstCheckpointSaver sidecar, ADR-2605171800)
graduates this gets swapped for that — same put/putWrites entry points.

Authoritative ADR: 90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md
"""
from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver


_FLUSH_DEBOUNCE_SEC = 0.5
_MAX_PAYLOAD_BYTES = 16 * 1024 * 1024  # 16 MB


def _b64(b: bytes | bytearray | memoryview) -> str:
    return base64.b64encode(bytes(b)).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


class FileCheckpointer(MemorySaver):
    """LangGraph in-memory checkpointer + JSON snapshot on disk.

    Internally MemorySaver keeps a nested dict of bytes payloads. We
    snapshot that to disk on every write, debounced by a background
    timer thread so a flurry of putWrites does not amplify into a flurry
    of disk syncs.
    """

    def __init__(self, path: str | os.PathLike[str], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.path = Path(path)
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None
        self._load_from_disk()

    # ── Persistence layer ─────────────────────────────────────────────

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        with self._lock:
            for thread, nss in (data.get("storage") or {}).items():
                self.storage.setdefault(thread, {})  # type: ignore[attr-defined]
                for ns, ids in nss.items():
                    self.storage[thread].setdefault(ns, {})  # type: ignore[attr-defined]
                    for cid, leaf in ids.items():
                        self.storage[thread][ns][cid] = (  # type: ignore[attr-defined]
                            _unb64(leaf["c"]),
                            _unb64(leaf["m"]),
                            leaf.get("p"),
                        )
            for entry in data.get("writes") or []:
                k = entry["k"]
                self.writes.setdefault(k, {})  # type: ignore[attr-defined]
                self.writes[k][entry["taskId"]] = (  # type: ignore[attr-defined]
                    entry["channel"],
                    entry["type"],
                    _unb64(entry["value"]),
                )

    def _schedule_flush(self) -> None:
        with self._lock:
            if self._timer is not None:
                return
            self._timer = threading.Timer(_FLUSH_DEBOUNCE_SEC, self._do_flush)
            self._timer.daemon = True
            self._timer.start()

    def flush_now(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._do_flush()

    def _do_flush(self) -> None:
        with self._lock:
            self._timer = None
            storage_out: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
            for thread, nss in self.storage.items():  # type: ignore[attr-defined]
                storage_out[thread] = {}
                for ns, ids in nss.items():
                    storage_out[thread][ns] = {}
                    for cid, leaf in ids.items():
                        storage_out[thread][ns][cid] = {
                            "c": _b64(leaf[0]),
                            "m": _b64(leaf[1]),
                            "p": leaf[2],
                        }
            writes_out: list[dict[str, Any]] = []
            for k, task_map in self.writes.items():  # type: ignore[attr-defined]
                for task_id, tup in task_map.items():
                    writes_out.append(
                        {
                            "k": k,
                            "taskId": task_id,
                            "channel": tup[0],
                            "type": tup[1],
                            "value": _b64(tup[2]),
                        }
                    )
            payload = json.dumps({"storage": storage_out, "writes": writes_out})
            while len(payload) > _MAX_PAYLOAD_BYTES:
                if not self._evict_oldest(storage_out):
                    break
                payload = json.dumps({"storage": storage_out, "writes": writes_out})
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(payload, "utf-8")
            except OSError as e:
                print(f"ameno FileCheckpointer: flush failed: {e}")

    def _evict_oldest(self, storage_out: dict[str, Any]) -> bool:
        threads = sorted(storage_out.keys())
        if len(threads) <= 1:
            return False
        oldest = threads[0]
        del storage_out[oldest]
        self.storage.pop(oldest, None)  # type: ignore[attr-defined]
        return True

    # ── MemorySaver overrides ─────────────────────────────────────────

    def put(self, config, checkpoint, metadata, new_versions=None):  # type: ignore[no-untyped-def]
        r = super().put(config, checkpoint, metadata, new_versions)
        self._schedule_flush()
        return r

    def put_writes(self, config, writes, task_id, task_path=""):  # type: ignore[no-untyped-def]
        r = super().put_writes(config, writes, task_id, task_path)
        self._schedule_flush()
        return r

    def delete_thread(self, thread_id):  # type: ignore[no-untyped-def]
        r = super().delete_thread(thread_id)
        self._schedule_flush()
        return r
