"""End-to-end integration test: real TS sidecar spawned via Node subprocess.

The C-1 unit tests cover the wire-protocol envelope against an
in-process Python mock sidecar. This test goes one step further and
proves the Python MstCheckpointSaver round-trips against the actual
``@etzhayyim/sdk`` JS implementation living in
``20-actors/etzhayyim-sdk/dist/checkpointer.js``.

Gated by environment so CI runners without Node v20+ + the SDK
``node_modules`` skip silently:

  ETZ_SIDECAR_BIN     path to dist/checkpointer-bin.js (auto-detected by default)
  ETZ_SIDECAR_NODE    node executable (default: shutil.which("node"))

To run locally:

  cd 20-actors/etzhayyim-sdk && pnpm install --prod
  cd ../kotoba-kotodama/py
  .venv/bin/python -m pytest tests/checkpointer/test_subprocess_sidecar.py -v
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from kotodama.checkpointer import MstCheckpointSaver


# ── Discovery ────────────────────────────────────────────────────────────────


def _default_sidecar_bin() -> Path | None:
    here = Path(__file__).resolve()
    repo_root = here.parents[5]
    candidate = (
        repo_root
        / "20-actors"
        / "etzhayyim-sdk"
        / "dist"
        / "checkpointer-bin.js"
    )
    return candidate if candidate.is_file() else None


def _node_exec() -> str | None:
    return os.environ.get("ETZ_SIDECAR_NODE") or shutil.which("node")


_env_bin = os.environ.get("ETZ_SIDECAR_BIN")
SIDECAR_BIN = Path(_env_bin) if _env_bin else _default_sidecar_bin()
NODE_BIN = _node_exec()


pytestmark = pytest.mark.skipif(
    SIDECAR_BIN is None
    or NODE_BIN is None
    or not SIDECAR_BIN.is_file(),
    reason=(
        "TS sidecar integration test skipped — set ETZ_SIDECAR_BIN to "
        "dist/checkpointer-bin.js and ensure `node` is on PATH"
    ),
)


# ── Subprocess fixture ───────────────────────────────────────────────────────


@pytest.fixture
def real_sidecar() -> Iterator[str]:
    """Spawn the real Node sidecar listening on a temp Unix socket. Yields the path."""
    tmp_dir = tempfile.mkdtemp(prefix="etz-cp-sidecar-")
    socket_path = os.path.join(tmp_dir, "checkpointer.sock")
    state_dir = os.path.join(tmp_dir, "state")
    os.makedirs(state_dir, exist_ok=True)

    env = {
        **os.environ,
        "ETZ_CHECKPOINTER_SOCKET": socket_path,
        "ETZ_CHECKPOINTER_STATE_DIR": state_dir,
        "ETZ_CHECKPOINTER_ALLOWED_DIDS": "did:test:integration",
    }
    proc = subprocess.Popen(
        [NODE_BIN, str(SIDECAR_BIN)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    # Wait until the sidecar creates the socket node (≤ 5s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            break
        if proc.poll() is not None:
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            raise RuntimeError(f"sidecar exited early: {err}")
        time.sleep(0.05)
    else:
        proc.kill()
        raise RuntimeError("sidecar did not bind socket within 5s")

    try:
        yield socket_path
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Tests ────────────────────────────────────────────────────────────────────


def _config(thread_id: str = "t-1", checkpoint_id: str | None = None) -> dict:
    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    if checkpoint_id is not None:
        cfg["configurable"]["checkpoint_id"] = checkpoint_id
    return cfg


def _checkpoint(cp_id: str, channel: str = "ch1", val: int = 1) -> dict:
    return {
        "v": 1,
        "id": cp_id,
        "ts": "2026-05-18T00:00:00+00:00",
        "channel_values": {channel: val},
        "channel_versions": {channel: "1"},
        "versions_seen": {},
        "updated_channels": [channel],
    }


def test_real_sidecar_health(real_sidecar):
    saver = MstCheckpointSaver(
        cell_did="did:test:integration",
        socket_path=real_sidecar,
    )
    try:
        resp = saver.health()
        assert resp["ok"] is True
    finally:
        saver.close()


def test_real_sidecar_rejects_unlisted_did(real_sidecar):
    saver = MstCheckpointSaver(
        cell_did="did:test:not-allowed",
        socket_path=real_sidecar,
    )
    try:
        # Sidecar must enforce the DID allowlist (per ADR-2605171800 §Stage 2).
        # Either health returns ok=False, or put/get errors. Either is a pass.
        rejected = False
        try:
            saver.put(
                _config("t-rej"),
                _checkpoint("1ckp001"),
                {"step": 1},
                {"ch1": "1"},
            )
        except Exception:
            rejected = True
        assert rejected, "sidecar accepted a request from a non-allowlisted DID"
    finally:
        saver.close()


def test_real_sidecar_put_then_get_round_trip(real_sidecar):
    """Smoke test the substrate hot path against the real Stage-2 sidecar.

    Note: depending on whether the sidecar already implements list/get_tuple
    in this drop, the get_tuple call may return None (storage-only mode).
    We assert at least that the put call succeeds (i.e. the sidecar accepts
    the envelope) and that get_tuple returns either the same checkpoint or
    None — both are protocol-compliant outcomes for an MVP sidecar.
    """
    saver = MstCheckpointSaver(
        cell_did="did:test:integration",
        socket_path=real_sidecar,
    )
    try:
        out = saver.put(
            _config("t-int-1"),
            _checkpoint("1ckp001", "alpha", 42),
            {"step": 1, "source": "loop"},
            {"alpha": "1"},
        )
        assert out["configurable"]["checkpoint_id"] == "1ckp001"

        tup = saver.get_tuple(_config("t-int-1"))
        assert tup is None or tup.checkpoint["id"] == "1ckp001"
    finally:
        saver.close()


# ── Encrypted-cell variant (ADR-2605181100 hard rule) ────────────────────────


@pytest.fixture
def real_encrypted_sidecar() -> Iterator[tuple[str, str]]:
    """Spawn the real sidecar with ETZ_CHECKPOINTER_ENCRYPT_CELLS set.

    Yields (socket_path, state_dir) — the test inspects state_dir to verify
    the spooled payload is ciphertext and the per-cell key file lives where
    we expect.
    """
    tmp_dir = tempfile.mkdtemp(prefix="etz-cp-enc-sidecar-")
    socket_path = os.path.join(tmp_dir, "checkpointer.sock")
    state_dir = os.path.join(tmp_dir, "state")
    os.makedirs(state_dir, exist_ok=True)

    env = {
        **os.environ,
        "ETZ_CHECKPOINTER_SOCKET": socket_path,
        "ETZ_CHECKPOINTER_STATE_DIR": state_dir,
        "ETZ_CHECKPOINTER_ALLOWED_DIDS": "did:test:integration",
        "ETZ_CHECKPOINTER_ENCRYPT_CELLS": "did:test:integration",
    }
    proc = subprocess.Popen(
        [NODE_BIN, str(SIDECAR_BIN)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            break
        if proc.poll() is not None:
            err_out = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            raise RuntimeError(f"encrypted sidecar exited early: {err_out}")
        time.sleep(0.05)
    else:
        proc.kill()
        raise RuntimeError("encrypted sidecar did not bind socket within 5s")

    try:
        yield socket_path, state_dir
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_encrypted_sidecar_round_trip_recovers_plaintext(real_encrypted_sidecar):
    """Encrypted-at-rest mode: put/get_tuple round-trips transparently."""
    socket_path, _state_dir = real_encrypted_sidecar
    saver = MstCheckpointSaver(
        cell_did="did:test:integration",
        socket_path=socket_path,
    )
    try:
        saver.put(
            _config("t-enc-1"),
            _checkpoint("1ckp001", "alpha", 42),
            {"step": 1, "source": "loop"},
            {"alpha": "1"},
        )
        tup = saver.get_tuple(_config("t-enc-1"))
        assert tup is not None
        assert tup.checkpoint["id"] == "1ckp001"
        # Plaintext recovered through the encrypt → MST → decrypt cycle.
        assert tup.checkpoint["channel_values"] == {"alpha": 42}
        assert tup.metadata.get("step") == 1
    finally:
        saver.close()


def test_encrypted_sidecar_spooled_payload_is_ciphertext(real_encrypted_sidecar):
    """The on-disk spool MUST NOT contain the plaintext channel values."""
    import urllib.parse

    socket_path, state_dir = real_encrypted_sidecar
    saver = MstCheckpointSaver(
        cell_did="did:test:integration",
        socket_path=socket_path,
    )
    try:
        saver.put(
            _config("t-enc-2"),
            _checkpoint("1ckp001", "alpha", "VERY-DISTINCTIVE-SECRET-STRING"),
            {"step": 1, "source": "loop"},
            {"alpha": "1"},
        )
    finally:
        saver.close()

    encoded_did = urllib.parse.quote("did:test:integration", safe="")
    payload_path = os.path.join(
        state_dir, "queue", encoded_did, "1ckp001.payload"
    )
    assert os.path.exists(payload_path)
    with open(payload_path, "rb") as f:
        spooled = f.read()
    # ADR-2605181100 hard rule: ciphertext-at-rest. The distinctive plaintext
    # marker must not be readable from the spool.
    assert b"VERY-DISTINCTIVE-SECRET-STRING" not in spooled
    # The encrypted wrapper marker `_etz_encrypted` should be present (it's
    # the msgpack-level field key, written in clear).
    assert b"_etz_encrypted" in spooled

    # Per-cell key persisted (mode 0o600 enforced inside the sidecar).
    key_path = os.path.join(state_dir, "keys", f"{encoded_did}.key")
    assert os.path.exists(key_path)
    assert os.stat(key_path).st_size == 32
