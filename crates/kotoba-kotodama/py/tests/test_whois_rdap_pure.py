"""Tests for _rdap_fetch in ingest/whois_rdap.py.

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


WHOIS = _load("_ingest_whois_rdap", "kotodama/ingest/whois_rdap.py")


def _rdap_payload() -> dict:
    return {
        "handle": "example.com",
        "ldhName": "example.com",
        "entities": [
            {
                "roles": ["registrar"],
                "handle": "IANA-292",
                "vcardArray": [
                    "vcard",
                    [["fn", {}, "text", "MarkMonitor Inc."]],
                ],
            }
        ],
        "nameservers": [
            {"ldhName": "A.IANA-SERVERS.NET"},
            {"ldhName": "B.IANA-SERVERS.NET"},
        ],
        "events": [
            {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
            {"eventAction": "last changed", "eventDate": "2023-08-14T07:01:44Z"},
            {"eventAction": "expiration", "eventDate": "2024-08-13T04:00:00Z"},
        ],
        "status": ["client delete prohibited", "client transfer prohibited"],
        "secureDNS": {"delegationSigned": False},
    }


# ─── _rdap_fetch — no data ─────────────────────────────────────────────────

def test_rdap_fetch_no_data_returns_empty_dict() -> None:
    with patch.object(WHOIS, "_http_json", return_value=None):
        result = WHOIS._rdap_fetch("example.com")
    assert result == {}


def test_rdap_fetch_empty_payload_returns_dict() -> None:
    with patch.object(WHOIS, "_http_json", return_value={}):
        result = WHOIS._rdap_fetch("example.com")
    assert isinstance(result, dict)


# ─── _rdap_fetch — registrar extraction ────────────────────────────────────

def test_rdap_fetch_extracts_registrar_name() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["registrar"] == "MarkMonitor Inc."


def test_rdap_fetch_extracts_registrar_iana_id() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["registrar_iana_id"] == "292"


def test_rdap_fetch_no_registrar_entity_returns_empty_registrar() -> None:
    payload = _rdap_payload()
    payload["entities"][0]["roles"] = ["tech"]
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["registrar"] == ""


def test_rdap_fetch_registrar_empty_vcard_returns_empty() -> None:
    payload = _rdap_payload()
    payload["entities"][0]["vcardArray"] = ["vcard", []]
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["registrar"] == ""


# ─── _rdap_fetch — nameservers ─────────────────────────────────────────────

def test_rdap_fetch_nameservers_lowercased() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    ns = result["nameservers"]
    assert "a.iana-servers.net" in ns
    assert "b.iana-servers.net" in ns


def test_rdap_fetch_nameservers_joined_by_comma() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    ns = result["nameservers"]
    assert "," in ns


def test_rdap_fetch_no_nameservers_returns_empty_string() -> None:
    payload = _rdap_payload()
    payload["nameservers"] = []
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["nameservers"] == ""


# ─── _rdap_fetch — dates ────────────────────────────────────────────────────

def test_rdap_fetch_extracts_registration_date() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["created_date_rdap"] == "1995-08-14T04:00:00Z"


def test_rdap_fetch_extracts_last_changed_date() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["updated_date_rdap"] == "2023-08-14T07:01:44Z"


def test_rdap_fetch_extracts_expiration_date() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["expires_date_rdap"] == "2024-08-13T04:00:00Z"


def test_rdap_fetch_missing_events_returns_empty_dates() -> None:
    payload = _rdap_payload()
    payload["events"] = []
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["created_date_rdap"] == ""
    assert result["updated_date_rdap"] == ""
    assert result["expires_date_rdap"] == ""


# ─── _rdap_fetch — status ────────────────────────────────────────────────────

def test_rdap_fetch_status_joined_by_comma() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert "client delete prohibited" in result["status"]
    assert "client transfer prohibited" in result["status"]


def test_rdap_fetch_empty_status_returns_empty_string() -> None:
    payload = _rdap_payload()
    payload["status"] = []
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["status"] == ""


# ─── _rdap_fetch — dnssec ────────────────────────────────────────────────────

def test_rdap_fetch_dnssec_unsigned() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert result["dnssec"] == "unsigned"


def test_rdap_fetch_dnssec_signed() -> None:
    payload = _rdap_payload()
    payload["secureDNS"] = {"delegationSigned": True}
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["dnssec"] == "signed"


def test_rdap_fetch_no_secure_dns_returns_unsigned() -> None:
    payload = _rdap_payload()
    payload["secureDNS"] = {}
    with patch.object(WHOIS, "_http_json", return_value=payload):
        result = WHOIS._rdap_fetch("example.com")
    assert result["dnssec"] == "unsigned"


# ─── _rdap_fetch — raw_excerpt ───────────────────────────────────────────────

def test_rdap_fetch_raw_excerpt_is_string() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert isinstance(result["raw_excerpt"], str)


def test_rdap_fetch_raw_excerpt_max_length() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    assert len(result["raw_excerpt"]) <= 4096


def test_rdap_fetch_returns_dict_with_required_keys() -> None:
    with patch.object(WHOIS, "_http_json", return_value=_rdap_payload()):
        result = WHOIS._rdap_fetch("example.com")
    expected_keys = {
        "registrar", "registrar_iana_id", "nameservers",
        "created_date_rdap", "updated_date_rdap", "expires_date_rdap",
        "status", "dnssec", "raw_excerpt",
    }
    assert expected_keys.issubset(result.keys())
