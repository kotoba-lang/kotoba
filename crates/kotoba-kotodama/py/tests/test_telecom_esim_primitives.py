"""Tests for telecom_esim primitives (eSIM/eUICC lifecycle, GSMA SGP.22)."""

from __future__ import annotations

import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import telecom_esim as ES  # noqa: E402


# ─── pure helper tests ────────────────────────────────────────────────────

def test_hash_adds_sha256_prefix():
    h = ES._hash("89012345678901234567")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_preserves_existing_prefix():
    already_hashed = "sha256:" + "a" * 64
    assert ES._hash(already_hashed) == already_hashed


def test_hash_none_returns_none():
    assert ES._hash(None) is None


def test_hash_empty_returns_none():
    assert ES._hash("") is None


def test_vid_format():
    vid = ES._vid("euicc", "test123")
    assert vid.startswith("at://did:web:telecom.etzhayyim.com/")
    assert "test123" in vid


def test_require_passes_when_all_present():
    ES._require({"eid": "abc", "deviceKind": "smartphone"}, ["eid", "deviceKind"])


def test_require_raises_on_missing():
    with pytest.raises(ValueError, match="Missing required fields"):
        ES._require({"eid": "abc"}, ["eid", "deviceKind"])


def test_constants_cover_expected_device_kinds():
    assert "smartphone" in ES.DEVICE_KINDS
    assert "iot" in ES.DEVICE_KINDS
    assert "wearable" in ES.DEVICE_KINDS


def test_constants_cover_profile_types():
    assert "telecom" in ES.PROFILE_TYPES
    assert "iot" in ES.PROFILE_TYPES
    assert "enterprise" in ES.PROFILE_TYPES


# ─── handle_provision_euicc (mocked DB) ──────────────────────────────────

def _make_fake_cursor():
    class FakeCur:
        def execute(self, sql, params=None): pass
        def fetchone(self): return None
        def fetchall(self): return []
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return FakeCur()


def test_provision_euicc_returns_vertex(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_provision_euicc({
        "eid": "89012345678901234567",
        "deviceKind": "smartphone",
    })
    assert "vertexId" in out
    assert out["status"] == "active"
    assert out["eid"].startswith("sha256:")


def test_provision_euicc_unknown_device_kind_falls_back(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_provision_euicc({
        "eid": "89012345678901234567",
        "deviceKind": "unknown_device",
    })
    assert out["status"] == "active"


def test_provision_euicc_requires_eid(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    with pytest.raises(ValueError, match="Missing required fields"):
        ES.handle_provision_euicc({"deviceKind": "smartphone"})


# ─── handle_download_esim_profile (mocked DB) ─────────────────────────────

def test_download_esim_profile_returns_vertex(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_download_esim_profile({
        "downloadId": "dl_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
        "smdpAddress": "smdp.example.com",
    })
    assert "vertexId" in out
    assert out["status"] == "completed"


def test_download_requires_mandatory_fields():
    with pytest.raises(ValueError, match="Missing required fields"):
        ES.handle_download_esim_profile({"eid": "89012345678901234567"})


# ─── handle_enable_esim_profile (mocked DB) ──────────────────────────────

def test_enable_esim_profile_returns_enabled(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_enable_esim_profile({
        "operationId": "op_enable_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
    })
    assert out["status"] == "enabled"


# ─── handle_disable_esim_profile (mocked DB) ─────────────────────────────

def test_disable_esim_profile_returns_disabled(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_disable_esim_profile({
        "operationId": "op_disable_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
        "reason": "userRequest",
    })
    assert out["status"] == "disabled"


# ─── handle_delete_esim_profile (mocked DB) ──────────────────────────────

def test_delete_esim_profile_returns_deleted(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_delete_esim_profile({
        "operationId": "op_delete_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
        "reason": "contractTerminated",
    })
    assert out["status"] == "deleted"


# ─── handle_register_smdp_event (mocked DB) ──────────────────────────────

def test_register_smdp_event_returns_ok(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_register_smdp_event({
        "eventId": "evt_001",
        "eid": "89012345678901234567",
        "smdpAddress": "smdp.example.com",
        "eventType": "profileDownload",
    })
    assert "vertexId" in out
    assert out["status"] == "pending"


# ─── handle_audit_euicc_state (mocked DB) ────────────────────────────────

def test_audit_euicc_state_returns_ok(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_audit_euicc_state({
        "auditId": "audit_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
        "profileState": "enabled",
    })
    assert "vertexId" in out
    assert out["status"] == "recorded"


# ─── handle_transfer_esim_ownership (mocked DB) ──────────────────────────

def test_transfer_esim_ownership_returns_ok(monkeypatch):
    monkeypatch.setattr(ES, "sync_cursor", lambda: _make_fake_cursor())
    out = ES.handle_transfer_esim_ownership({
        "transferId": "xfr_001",
        "eid": "89012345678901234567",
        "iccid": "8981100021234567890",
        "sourceMno": "mno_ntt",
        "targetMno": "mno_kddi",
        "targetSmdpAddress": "smdp.kddi.com",
    })
    assert "vertexId" in out
    assert out["status"] == "initiated"


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_eight_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    ES.register(FakeWorker(), timeout_ms=30_000)
    assert set(registered) == {
        "telecom.esim.euicc.provision",
        "telecom.esim.profile.download",
        "telecom.esim.profile.enable",
        "telecom.esim.profile.disable",
        "telecom.esim.profile.delete",
        "telecom.esim.smds.register",
        "telecom.esim.euicc.audit",
        "telecom.esim.profile.transfer",
    }
