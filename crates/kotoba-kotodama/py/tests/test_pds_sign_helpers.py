"""Tests for _sign_body and _utc_now_iso pure helpers shared across
primitives/pds_heartbeat.py, pds_key_rotation.py, pds_outbox.py,
pds_discover_cache.py, pds_mitama_cron.py, pds_domain_coverage.py."""

from __future__ import annotations

import hashlib
import hmac
import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Import directly — these primitives don't use @udf
from kotodama.primitives import pds_heartbeat as PH  # noqa: E402
from kotodama.primitives import pds_key_rotation as PK  # noqa: E402
from kotodama.primitives import pds_outbox as PO  # noqa: E402
from kotodama.primitives import pds_discover_cache as PDC  # noqa: E402
from kotodama.primitives import pds_mitama_cron as PMC  # noqa: E402
from kotodama.primitives import pds_domain_coverage as PDCOV  # noqa: E402


# ─── pds_heartbeat._sign_body ────────────────────────────────────────────────

def test_hb_sign_body_returns_64_hex() -> None:
    result = PH._sign_body("secret", b"body")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_hb_sign_body_deterministic() -> None:
    a = PH._sign_body("secret", b"body")
    b = PH._sign_body("secret", b"body")
    assert a == b


def test_hb_sign_body_different_secrets_differ() -> None:
    a = PH._sign_body("secret1", b"body")
    b = PH._sign_body("secret2", b"body")
    assert a != b


def test_hb_sign_body_different_bodies_differ() -> None:
    a = PH._sign_body("secret", b"body1")
    b = PH._sign_body("secret", b"body2")
    assert a != b


def test_hb_sign_body_matches_stdlib_hmac() -> None:
    expected = hmac.new("sec".encode("utf-8"), b"data", hashlib.sha256).hexdigest()
    assert PH._sign_body("sec", b"data") == expected


# ─── pds_heartbeat._utc_now_iso ──────────────────────────────────────────────

def test_hb_utc_now_iso_format() -> None:
    result = PH._utc_now_iso()
    assert result.endswith("Z")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result)


def test_hb_utc_now_iso_no_microseconds() -> None:
    result = PH._utc_now_iso()
    assert "." not in result


# ─── pds_key_rotation._sign_body ─────────────────────────────────────────────

def test_kr_sign_body_returns_64_hex() -> None:
    result = PK._sign_body("secret", b"body")
    assert len(result) == 64


def test_kr_sign_body_deterministic() -> None:
    a = PK._sign_body("key", b"payload")
    b = PK._sign_body("key", b"payload")
    assert a == b


def test_kr_sign_body_same_as_heartbeat_for_same_input() -> None:
    a = PH._sign_body("shared_key", b"shared_body")
    b = PK._sign_body("shared_key", b"shared_body")
    assert a == b


# ─── pds_key_rotation._utc_now_iso ───────────────────────────────────────────

def test_kr_utc_now_iso_format() -> None:
    result = PK._utc_now_iso()
    assert result.endswith("Z")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result)


# ─── pds_outbox / discover_cache / mitama_cron / domain_coverage ─────────────

def test_po_sign_body_matches_hmac() -> None:
    expected = hmac.new("key".encode("utf-8"), b"payload", hashlib.sha256).hexdigest()
    assert PO._sign_body("key", b"payload") == expected


def test_pdc_sign_body_matches_hmac() -> None:
    expected = hmac.new("key".encode("utf-8"), b"payload", hashlib.sha256).hexdigest()
    assert PDC._sign_body("key", b"payload") == expected


def test_pmc_sign_body_matches_hmac() -> None:
    expected = hmac.new("key".encode("utf-8"), b"payload", hashlib.sha256).hexdigest()
    assert PMC._sign_body("key", b"payload") == expected


def test_pdcov_sign_body_matches_hmac() -> None:
    expected = hmac.new("key".encode("utf-8"), b"payload", hashlib.sha256).hexdigest()
    assert PDCOV._sign_body("key", b"payload") == expected


def test_po_utc_now_iso_format() -> None:
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", PO._utc_now_iso())


def test_pdc_utc_now_iso_format() -> None:
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", PDC._utc_now_iso())


def test_pmc_utc_now_iso_format() -> None:
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", PMC._utc_now_iso())


def test_pdcov_utc_now_iso_format() -> None:
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", PDCOV._utc_now_iso())
