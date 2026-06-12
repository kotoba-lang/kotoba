"""Pure helper tests for PDS cron primitives.

All pds_* modules share the same pure helper functions:
  _utc_now_iso()  → ISO 8601 UTC timestamp
  _sign_body(secret, body)  → HMAC-SHA256 hex digest

Tests cross all 5 modules:
  pds_discover_cache, pds_heartbeat, pds_domain_coverage,
  pds_key_rotation, pds_mitama_cron, pds_outbox
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_discover_cache as DC
from kotodama.primitives import pds_heartbeat as HB
from kotodama.primitives import pds_domain_coverage as DCV
from kotodama.primitives import pds_key_rotation as KR
from kotodama.primitives import pds_mitama_cron as MC
from kotodama.primitives import pds_outbox as OB


# ─── _utc_now_iso ─────────────────────────────────────────────────────────────

def test_discover_cache_utc_now_iso_returns_string() -> None:
    assert isinstance(DC._utc_now_iso(), str)


def test_discover_cache_utc_now_iso_contains_t() -> None:
    assert "T" in DC._utc_now_iso()


def test_discover_cache_utc_now_iso_ends_with_z() -> None:
    assert DC._utc_now_iso().endswith("Z")


def test_heartbeat_utc_now_iso_returns_string() -> None:
    assert isinstance(HB._utc_now_iso(), str)


def test_heartbeat_utc_now_iso_contains_t() -> None:
    assert "T" in HB._utc_now_iso()


def test_domain_coverage_utc_now_iso_returns_string() -> None:
    assert isinstance(DCV._utc_now_iso(), str)


def test_key_rotation_utc_now_iso_returns_string() -> None:
    assert isinstance(KR._utc_now_iso(), str)


def test_mitama_cron_utc_now_iso_returns_string() -> None:
    assert isinstance(MC._utc_now_iso(), str)


def test_outbox_utc_now_iso_returns_string() -> None:
    assert isinstance(OB._utc_now_iso(), str)


def test_utc_now_iso_has_date_prefix() -> None:
    ts = DC._utc_now_iso()
    # Should start with a year like "202"
    assert ts[:3] == "202"


def test_utc_now_iso_length() -> None:
    ts = DC._utc_now_iso()
    assert len(ts) >= 20  # "2026-01-01T00:00:00Z" = 20 chars


# ─── _sign_body ───────────────────────────────────────────────────────────────

def test_discover_cache_sign_body_returns_string() -> None:
    assert isinstance(DC._sign_body("secret", b"payload"), str)


def test_discover_cache_sign_body_is_hex() -> None:
    result = DC._sign_body("secret", b"payload")
    int(result, 16)  # raises ValueError if not hex


def test_discover_cache_sign_body_length_64() -> None:
    assert len(DC._sign_body("secret", b"payload")) == 64


def test_discover_cache_sign_body_deterministic() -> None:
    a = DC._sign_body("secret", b"payload")
    b = DC._sign_body("secret", b"payload")
    assert a == b


def test_discover_cache_sign_body_differs_by_secret() -> None:
    a = DC._sign_body("secret1", b"payload")
    b = DC._sign_body("secret2", b"payload")
    assert a != b


def test_discover_cache_sign_body_differs_by_payload() -> None:
    a = DC._sign_body("secret", b"payload1")
    b = DC._sign_body("secret", b"payload2")
    assert a != b


def test_heartbeat_sign_body_returns_string() -> None:
    assert isinstance(HB._sign_body("key", b"data"), str)


def test_heartbeat_sign_body_length_64() -> None:
    assert len(HB._sign_body("key", b"data")) == 64


def test_heartbeat_sign_body_deterministic() -> None:
    assert HB._sign_body("key", b"data") == HB._sign_body("key", b"data")


def test_domain_coverage_sign_body_returns_string() -> None:
    assert isinstance(DCV._sign_body("key", b"data"), str)


def test_key_rotation_sign_body_returns_string() -> None:
    assert isinstance(KR._sign_body("key", b"data"), str)


def test_mitama_cron_sign_body_returns_string() -> None:
    assert isinstance(MC._sign_body("key", b"data"), str)


def test_outbox_sign_body_returns_string() -> None:
    assert isinstance(OB._sign_body("key", b"data"), str)


def test_sign_body_empty_secret_still_returns_hex() -> None:
    result = DC._sign_body("", b"payload")
    assert len(result) == 64


def test_sign_body_empty_payload_returns_hex() -> None:
    result = DC._sign_body("secret", b"")
    assert len(result) == 64


def test_sign_body_all_modules_same_result_for_same_input() -> None:
    args = ("secret", b"payload")
    results = {
        DC._sign_body(*args),
        HB._sign_body(*args),
        DCV._sign_body(*args),
        KR._sign_body(*args),
        MC._sign_body(*args),
        OB._sign_body(*args),
    }
    # All modules should produce identical HMAC-SHA256 for same inputs
    assert len(results) == 1


# ─── module-level constants ────────────────────────────────────────────────────

def test_discover_cache_has_pds_did() -> None:
    assert hasattr(DC, "PDS_DID") or hasattr(DC, "DISCOVER_CACHE_COLLECTION")


def test_heartbeat_has_collection_constant() -> None:
    assert hasattr(HB, "HEARTBEAT_COLLECTION") or hasattr(HB, "PDS_DID")


def test_key_rotation_has_collection_constant() -> None:
    assert hasattr(KR, "KEY_ROTATION_COLLECTION") or hasattr(KR, "PDS_DID")
