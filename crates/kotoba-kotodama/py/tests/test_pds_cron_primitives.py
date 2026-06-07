"""Tests for PDS cron primitives (heartbeat, domain_coverage, discover_cache,
key_rotation, mitama_cron, outbox)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest  # noqa: E402
from kotodama.primitives import pds_heartbeat as PH  # noqa: E402
from kotodama.primitives import pds_domain_coverage as PDC  # noqa: E402
from kotodama.primitives import pds_discover_cache as PDSC  # noqa: E402
from kotodama.primitives import pds_key_rotation as PKR  # noqa: E402
from kotodama.primitives import pds_mitama_cron as PMC  # noqa: E402
from kotodama.primitives import pds_outbox as PO  # noqa: E402


def _make_stub_db(module_path: str):
    m = MagicMock()
    cur = MagicMock()
    m.return_value.__enter__ = MagicMock(return_value=cur)
    m.return_value.__exit__ = MagicMock(return_value=False)
    return m, cur


# ─── pds_heartbeat ────────────────────────────────────────────────────────────

class TestPdsHeartbeat:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_heartbeat.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_heartbeat_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "appsTotal": 10, "batchIndex": 0, "batchSize": 10,
                "heartbeatOk": 10, "heartbeatFail": 0, "shinkaStatus": 200}
        result = PH.write_heartbeat_tick(tick, flush=False)
        assert result["uri"].startswith("at://")
        assert PH.PDS_DID in result["uri"]

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PH.task_pds_heartbeat_run(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert "error" in result
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PH.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.heartbeat.run"]


# ─── pds_domain_coverage ─────────────────────────────────────────────────────

class TestPdsDomainCoverage:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_domain_coverage.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_domain_coverage_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "newHandles": 5, "totalHandles": 100, "errors": 0}
        result = PDC.write_domain_coverage_tick(tick, flush=False)
        assert result["uri"].startswith("at://")

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PDC.task_pds_domain_coverage_expand(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PDC.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.domainCoverage.expand"]


# ─── pds_discover_cache ───────────────────────────────────────────────────────

class TestPdsDiscoverCache:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_discover_cache.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_discover_cache_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "cached": 50, "errors": 0}
        result = PDSC.write_discover_cache_tick(tick, flush=False)
        assert result["uri"].startswith("at://")

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PDSC.task_pds_discover_cache_warm(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PDSC.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.discoverCache.warm"]


# ─── pds_key_rotation ────────────────────────────────────────────────────────

class TestPdsKeyRotation:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_key_rotation.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_key_rotation_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "rotatedCount": 3, "errors": 0}
        result = PKR.write_key_rotation_tick(tick, flush=False)
        assert result["uri"].startswith("at://")

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PKR.task_pds_signing_keys_rotate_stale(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PKR.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.signingKeys.rotateStale"]


# ─── pds_mitama_cron ─────────────────────────────────────────────────────────

class TestPdsMitamaCron:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_mitama_cron.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_mitama_cron_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "synced": 12, "errors": 0}
        result = PMC.write_mitama_cron_resync_tick(tick, flush=False)
        assert result["uri"].startswith("at://")

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PMC.task_pds_mitama_cron_triggers_resync(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PMC.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.mitama.cronTriggers.resync"]


# ─── pds_outbox ───────────────────────────────────────────────────────────────

class TestPdsOutbox:
    @pytest.fixture()
    def _stub_db(self):
        with patch("kotodama.primitives.pds_outbox.sync_cursor") as m:
            cur = MagicMock()
            m.return_value.__enter__ = MagicMock(return_value=cur)
            m.return_value.__exit__ = MagicMock(return_value=False)
            yield cur

    def test_write_outbox_sync_tick_returns_uri(self, _stub_db):
        tick = {"ts": "2026-04-29T10:00:00Z", "ok": True, "httpStatus": 200,
                "synced": 7, "errors": 0}
        result = PO.write_outbox_sync_tick(tick, flush=False)
        assert result["uri"].startswith("at://")

    def test_task_no_secret_returns_error(self, _stub_db):
        result = asyncio.run(PO.task_pds_write_outbox_sync(
            pdsUrl="https://atproto.etzhayyim.com", flush=False
        ))
        assert result["ok"] is False
        assert result["auditUri"].startswith("at://")

    def test_register_exposes_one_task(self):
        registered = []

        class FakeWorker:
            def task(self, *, task_type, single_value, timeout_ms):
                registered.append(task_type)
                def deco(fn): return fn
                return deco

        PO.register(FakeWorker(), timeout_ms=120_000)
        assert registered == ["pds.writeOutbox.sync"]
