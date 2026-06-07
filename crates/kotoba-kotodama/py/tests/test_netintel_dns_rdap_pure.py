"""Tests for _rdap_domain and _doh_records in ingest/netintel_dns.py.

_http_json is mocked so no real HTTP requests are made.
"""

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


DNS = _load("_ingest_netintel_dns", "kotodama/ingest/netintel_dns.py")


def _rdap_payload() -> dict:
    return {
        "handle": "example.com",
        "ldhName": "example.com",
        "entities": [
            {
                "roles": ["registrar"],
                "handle": "REG-1",
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
            {"eventAction": "last changed", "eventDate": "2023-06-15T00:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2025-01-01T00:00:00Z"},
        ],
        "status": ["active", "client transfer prohibited"],
        "secureDNS": {"delegationSigned": True},
    }


# ─── _rdap_domain ─────────────────────────────────────────────────────────────

def test_rdap_domain_no_data_returns_empty_dict() -> None:
    with patch.object(DNS, "_http_json", return_value=None):
        result = DNS._rdap_domain("example.com")
    assert result == {}


def test_rdap_domain_extracts_registrar() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert result["registrar"] == "Example Registrar Inc"


def test_rdap_domain_extracts_nameservers_lowercase() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert "ns1.example.com" in result["nameservers"]
    assert "ns2.example.com" in result["nameservers"]


def test_rdap_domain_extracts_registration_date() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert result["registration_date"] == "2000-01-01T00:00:00Z"


def test_rdap_domain_extracts_last_changed() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert result["last_changed_date"] == "2023-06-15T00:00:00Z"


def test_rdap_domain_extracts_expiration_date() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert result["expiration_date"] == "2025-01-01T00:00:00Z"


def test_rdap_domain_dnssec_signed() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert result["dnssec"] == "signed"


def test_rdap_domain_dnssec_unsigned() -> None:
    payload = _rdap_payload()
    payload["secureDNS"] = {"delegationSigned": False}
    with patch.object(DNS, "_http_json", return_value=payload):
        result = DNS._rdap_domain("example.com")
    assert result["dnssec"] == "unsigned"


def test_rdap_domain_status_joined() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert "active" in result["status"]
    assert "client transfer prohibited" in result["status"]


def test_rdap_domain_returns_dict() -> None:
    with patch.object(DNS, "_http_json", return_value=_rdap_payload()):
        result = DNS._rdap_domain("example.com")
    assert isinstance(result, dict)


def test_rdap_domain_empty_payload_returns_dict() -> None:
    with patch.object(DNS, "_http_json", return_value={}):
        result = DNS._rdap_domain("example.com")
    assert isinstance(result, dict)


def test_rdap_domain_registrar_falls_back_to_handle() -> None:
    payload = _rdap_payload()
    payload["entities"][0]["vcardArray"] = ["vcard", []]
    with patch.object(DNS, "_http_json", return_value=payload):
        result = DNS._rdap_domain("example.com")
    assert result["registrar"] == "REG-1"


def test_rdap_domain_no_registrar_entity_returns_empty_string() -> None:
    payload = _rdap_payload()
    payload["entities"][0]["roles"] = ["tech"]
    with patch.object(DNS, "_http_json", return_value=payload):
        result = DNS._rdap_domain("example.com")
    assert result["registrar"] == ""


# ─── _doh_records (mock _http_json) ──────────────────────────────────────────

def test_doh_records_returns_dict_with_record_types() -> None:
    with patch.object(DNS, "_http_json", return_value=None):
        result = DNS._doh_records("example.com")
    assert set(result.keys()) >= {"A", "AAAA", "MX", "NS", "TXT"}


def test_doh_records_empty_when_no_http_response() -> None:
    with patch.object(DNS, "_http_json", return_value=None):
        result = DNS._doh_records("example.com")
    assert result["A"] == ""
    assert result["NS"] == ""


def test_doh_records_extracts_a_records() -> None:
    def fake_http(url, **kw):
        if "type=A" in url:
            return {"Answer": [{"data": "1.2.3.4"}, {"data": "5.6.7.8"}]}
        return None
    with patch.object(DNS, "_http_json", side_effect=fake_http):
        result = DNS._doh_records("example.com")
    assert "1.2.3.4" in result["A"]
    assert "5.6.7.8" in result["A"]


def test_doh_records_strips_trailing_dot_from_ns() -> None:
    def fake_http(url, **kw):
        if "type=NS" in url:
            return {"Answer": [{"data": "ns1.example.com."}]}
        return None
    with patch.object(DNS, "_http_json", side_effect=fake_http):
        result = DNS._doh_records("example.com")
    assert result["NS"] == "ns1.example.com"
