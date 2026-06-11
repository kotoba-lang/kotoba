"""Murakumo cell for the yabai Tor/Torrent CTI persistence path.

The cell runs the existing yabai offline-safe pipeline, transacts to Kotoba
only when operator credentials are present, and always writes a local NDJSON
execution marker so Mac mini fleet runs remain auditable during outages.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Any

ACTOR_DID = "did:web:etzhayyim.com:actor:yabai"
CELL_NAME = "YabaiTorTorrentCtiPersistenceCell"


def _repo_root() -> pathlib.Path:
    configured = os.environ.get("ETZHAYYIM_ROOT") or os.environ.get("ETZ_REPO")
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "20-actors" / "yabai").exists():
            return parent
    raise RuntimeError("repository root not found for yabai actor")


def _state_dir(repo: pathlib.Path) -> pathlib.Path:
    configured = os.environ.get("YABAI_STATE_DIR")
    candidates = []
    if configured:
        candidates.append(pathlib.Path(configured).expanduser())
    candidates.extend([
        pathlib.Path("/var/lib/etzhayyim/yabai"),
        repo / "20-actors" / "yabai" / "out",
    ])
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise RuntimeError("no writable yabai state directory")


def _guardrails() -> None:
    rw_url = os.environ.get("RW_URL", "")
    if "runpod" in rw_url.lower() or shutil.which("runpod"):
        raise RuntimeError("refusing yabai Murakumo cell on runpod/RisingWave runtime")


async def _run(cmd: list[str], cwd: pathlib.Path, env: dict[str, str]) -> dict[str, Any]:
    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _append_marker(path: pathlib.Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


async def yabai_tor_torrent_persistence_cell() -> dict[str, Any]:
    _guardrails()
    repo = _repo_root()
    actor = repo / "20-actors" / "yabai"
    methods = actor / "methods"
    state = _state_dir(repo)
    marker_path = state / "cti-correlator-runs.ndjson"

    env = os.environ.copy()
    env.setdefault("KOTOBA_AUDIT_STRICT", "1")
    env.setdefault("PYTHONUTF8", "1")

    started = int(time.time())
    record: dict[str, Any] = {
        "ts": started,
        "cell": CELL_NAME,
        "actor_did": ACTOR_DID,
        "node": os.environ.get("ETZHAYYIM_NODE_NAME") or os.environ.get("ETZHAYYIM_NODE"),
        "mode": "live" if (env.get("YABAI_GRAPH_CID") and (env.get("KOTOBA_TOKEN") or env.get("KOTOBA_CACAO_B64"))) else "dry-run",
        "boundary": "public Tor-exit indicators + case-bound BitTorrent evidence only; no de-anonymization",
    }

    steps = [
        [sys.executable, str(methods / "ingest.py")],
        [sys.executable, str(methods / "analyze.py")],
        [sys.executable, str(methods / "transact.py")],
    ]
    results = []
    try:
        for step in steps:
            result = await _run(step, actor, env)
            results.append(result)
            if result["returncode"] != 0:
                record.update({"ok": False, "failed_step": step[-1], "results": results})
                _append_marker(marker_path, record)
                if env.get("YABAI_REQUIRE_LIVE") == "1":
                    raise RuntimeError(f"yabai persistence failed at {step[-1]}")
                return record

        if record["mode"] != "live" and env.get("YABAI_REQUIRE_LIVE") == "1":
            record.update({"ok": False, "failed_step": "transact.py", "results": results, "error": "live credentials missing"})
            _append_marker(marker_path, record)
            raise RuntimeError("YABAI_REQUIRE_LIVE=1 but no graph/auth credentials were present")

        record.update({"ok": True, "duration_s": int(time.time()) - started, "results": results})
        _append_marker(marker_path, record)
        return record
    except Exception as caught:
        record.update({"ok": False, "duration_s": int(time.time()) - started, "error": str(caught), "results": results})
        _append_marker(marker_path, record)
        raise
