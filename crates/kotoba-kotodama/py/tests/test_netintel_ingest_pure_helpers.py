"""Tests for pure/early-return paths in netintel ingest modules:
ingest/fingerprint.py, ingest/scan_banner.py, ingest/whois_rdap.py."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path
from unittest.mock import patch

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


def _load(mod_name: str, rel: str) -> types.ModuleType:
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = _py_src / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = types.ModuleType(mod_name)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


FP = _load("_ingest_fingerprint", "kotodama/ingest/fingerprint.py")
SB = _load("_ingest_scan_banner", "kotodama/ingest/scan_banner.py")
WR = _load("_ingest_whois_rdap", "kotodama/ingest/whois_rdap.py")


# ─── ingest_fingerprint_delta early-return ───────────────────────────────────

def test_fingerprint_no_proxy_url_returns_error(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = FP.ingest_fingerprint_delta()
    assert result["ok"] is False
    assert "SCAN_PROXY_URL" in result["error"]


def test_fingerprint_no_proxy_url_zero_counts(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = FP.ingest_fingerprint_delta()
    assert result["hostsProbed"] == 0
    assert result["rowsWritten"] == 0


def test_fingerprint_no_proxy_url_returns_dict(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = FP.ingest_fingerprint_delta()
    assert isinstance(result, dict)


def test_fingerprint_no_proxy_url_not_ok(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = FP.ingest_fingerprint_delta()
    assert result["ok"] is False
    assert "error" in result


# ─── ingest_scan_banner early-return ─────────────────────────────────────────

def test_scan_banner_no_proxy_url_returns_error(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = SB.ingest_scan_banner()
    assert result["ok"] is False
    assert "SCAN_PROXY_URL" in result["error"]


def test_scan_banner_no_proxy_url_zero_ips(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = SB.ingest_scan_banner()
    assert result["ipsScanned"] == 0
    assert result["rowsWritten"] == 0


def test_scan_banner_no_proxy_url_returns_dict(monkeypatch) -> None:
    monkeypatch.delenv("SCAN_PROXY_URL", raising=False)
    result = SB.ingest_scan_banner()
    assert isinstance(result, dict)


def test_scan_banner_empty_proxy_url_returns_error(monkeypatch) -> None:
    monkeypatch.setenv("SCAN_PROXY_URL", "")
    result = SB.ingest_scan_banner()
    assert result["ok"] is False


# ─── _rdap_fetch parsing (mock _http_json) ───────────────────────────────────

def _rdap_payload() -> dict:
    return {
        "handle": "example.com",
        "ldhName": "example.com",
        "entities": [
            {
                "roles": ["registrar"],
                "handle": "IANA-9999",
                "vcardArray": [
                    "vcard",
                    [["fn", {}, "text", "Example Registrar Inc"]],
                ],
            }
        ],
        "nameservers": [
            {"ldhName": "NS1.EXAMPLE.COM"},
            {"ldhName": "NS2.EXAMPLE.COM"},
        ],
        "events": [
            {"eventAction": "registration", "eventDate": "2000-01-01T00:00:00Z"},
            {"eventAction": "last changed", "eventDate": "2023-06-01T00:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2025-01-01T00:00:00Z"},
        ],
        "status": ["active", "client transfer prohibited"],
        "secureDNS": {"delegationSigned": True},
    }


def test_rdap_fetch_no_data_returns_empty_dict() -> None:
    with patch.object(WR, "_http_json", return_value=None):
        result = WR._rdap_fetch("example.com")
    assert result == {}


def test_rdap_fetch_extracts_registrar() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert result["registrar"] == "Example Registrar Inc"


def test_rdap_fetch_extracts_nameservers() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert "ns1.example.com" in result["nameservers"]
    assert "ns2.example.com" in result["nameservers"]


def test_rdap_fetch_extracts_created_date() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert result["created_date_rdap"] == "2000-01-01T00:00:00Z"


def test_rdap_fetch_extracts_updated_date() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert result["updated_date_rdap"] == "2023-06-01T00:00:00Z"


def test_rdap_fetch_extracts_expiration() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert result["expires_date_rdap"] == "2025-01-01T00:00:00Z"


def test_rdap_fetch_dnssec_signed() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert result["dnssec"] == "signed"


def test_rdap_fetch_dnssec_unsigned() -> None:
    payload = _rdap_payload()
    payload["secureDNS"] = {"delegationSigned": False}
    with patch.object(WR, "_http_json", return_value=payload):
        result = WR._rdap_fetch("example.com")
    assert result["dnssec"] == "unsigned"


def test_rdap_fetch_status_joined() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert "active" in result["status"]
    assert "client transfer prohibited" in result["status"]


def test_rdap_fetch_empty_payload_returns_dict() -> None:
    with patch.object(WR, "_http_json", return_value={}):
        result = WR._rdap_fetch("example.com")
    assert isinstance(result, dict)


def test_rdap_fetch_returns_dict() -> None:
    with patch.object(WR, "_http_json", return_value=_rdap_payload()):
        result = WR._rdap_fetch("example.com")
    assert isinstance(result, dict)
