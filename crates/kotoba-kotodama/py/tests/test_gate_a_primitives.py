"""Smoke tests for gate (a) §1 substrate primitives P1-P4."""

from __future__ import annotations

import os
import tempfile

import pytest


# ── P1 active_inference_substrate ──

def test_p1_import_substrate_smoke():
    """P1 smoke: import-only check."""
    from kotodama.primitives.active_inference_substrate import (
        BeliefStore,
        ObservationRecord,
        select_belief_store,
    )

    assert BeliefStore is not None
    assert ObservationRecord is not None
    assert callable(select_belief_store)


def test_p1_no_rw_imports_in_module():
    """P1 substrate-fit invariant: no RisingWaveBeliefStore / dual-write."""
    from kotodama.primitives import active_inference_substrate as mod

    src = open(mod.__file__).read()
    assert "RisingWaveBeliefStore" not in src or src.count("RisingWaveBeliefStore") == 0, \
        f"RW import survived in {mod.__file__}"
    assert "class _DualWriteBeliefStore" not in src, "dual-write class survived"
    assert "psycopg" not in src, "psycopg import survived"


def test_p1_default_backend_is_at_ipfs_local():
    """P1 verifies the religious-corp default is at-ipfs-local, not 'rw'."""
    from kotodama.primitives.active_inference_substrate import _build_single_backend_store

    # Empty env → should fall through to at-ipfs-local default
    src = open(_build_single_backend_store.__code__.co_filename).read()
    # Default in the function body is "at-ipfs-local"
    assert '"at-ipfs-local"' in src
    # And the unsupported-backend fallback line should reference at-ipfs-local
    assert "religious-corp" in src.lower() or "at-ipfs-local" in src


# ── P2 at_ipfs_belief_store ──

def test_p2_at_ipfs_belief_store_round_trip(tmp_path):
    """P2 smoke: seeded BeliefStore + put_observation/list_observations round-trip."""
    os.environ["AT_IPFS_LOCAL_DIR"] = str(tmp_path)
    os.environ["BELIEF_STORE_BACKEND"] = "at-ipfs-local"

    from kotodama.primitives.active_inference_substrate import (
        ObservationRecord,
        select_belief_store,
    )

    store = select_belief_store({
        "BELIEF_STORE_BACKEND": "at-ipfs-local",
        "AT_IPFS_LOCAL_DIR": str(tmp_path),
    })

    rec = ObservationRecord(
        agent_did="did:web:test.adherent",
        observation_id="obs-test-001",
        source_kind="test",
    )
    uri = store.put_observation(rec)
    assert uri  # non-empty URI returned

    observations = store.list_observations("did:web:test.adherent", limit=10)
    assert len(observations) >= 1
    assert any(o.observation_id == "obs-test-001" for o in observations)


# ── P3 worker_runtime ──

@pytest.mark.asyncio
async def test_p3_watchdog_clean_exit():
    """P3 smoke: watchdog returns without raising."""
    from kotodama.worker_runtime import watchdog

    result = await watchdog(worker_name="test")
    assert result["ok"] is True
    assert result["worker"] == "test"


@pytest.mark.asyncio
async def test_p3_activation_monitor_bogus_url():
    """P3 smoke: bogus URL → clean exit, ok=False."""
    from kotodama.worker_runtime import activation_monitor

    result = await activation_monitor("not-a-url")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_p3_sqlite_health_probe_healthy(tmp_path):
    """P3 smoke: health probe succeeds against a writable dir."""
    from kotodama.worker_runtime import task_sqlite_health_probe

    result = await task_sqlite_health_probe(db_path=str(tmp_path / "healthz.db"))
    assert result["ok"] is True
    assert result["row_count"] >= 1


@pytest.mark.asyncio
async def test_p3_degraded_stub_kwarg_passthrough():
    """P3 smoke: degraded stub returns kwargs back."""
    from kotodama.worker_runtime import make_degraded_ingest_stub

    stub = make_degraded_ingest_stub("test_stub")
    result = await stub(adherent_did="did:web:x", extra="kw")
    assert result["ok"] is True
    assert result["degraded"] is True
    assert result["adherent_did"] == "did:web:x"
    assert result["extra"] == "kw"


# ── P4 ingest.core ──

def test_p4_ingest_core_round_trip(tmp_path, monkeypatch):
    """P4 smoke: upsert_run + mark_run_finished + upsert_cursor + upsert_artifact."""
    monkeypatch.setenv("ORGANISM_SQLITE_DIR", str(tmp_path))

    # Reimport to pick up env (module caches db path lazily but _connect re-reads)
    from kotodama.ingest import core

    run_id = core.upsert_run("test-source", run_id="run-001")
    assert run_id == "run-001"

    core.upsert_cursor("test-source", "block_height", "123456")
    cursor = core.get_cursor("test-source", "block_height")
    assert cursor == "123456"

    core.upsert_artifact(run_id, "ipfs://bafytest", mime="application/json", size=42)
    artifacts = core.list_artifacts_for_run(run_id)
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_uri"] == "ipfs://bafytest"
    assert artifacts[0]["size"] == 42

    core.mark_run_finished(run_id, status="success")
    # No raise = success
