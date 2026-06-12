"""Tests for pure functions in handler modules (bpmn, classify_t3, gmail_contact, news_intel, ingest)."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() registers cleanly without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load(name: str) -> types.ModuleType:
    """Load a handler module by file path (bypasses handlers/__init__)."""
    mod_key = f"_handler_{name}"
    if mod_key in sys.modules:
        return sys.modules[mod_key]
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(mod_key, src)
    assert spec is not None and spec.loader is not None
    mod = types.ModuleType(mod_key)
    # Pre-register so exec_module's @udf registrations are idempotent
    # across multiple test files loading the same handler.
    sys.modules[mod_key] = mod
    # Clear any NSIDs already registered from a prior load of this file.
    try:
        from kotodama import registry as _reg  # noqa: PLC0415
        to_del = [
            k for k, v in _reg._HANDLERS.items()
            if getattr(getattr(v, "fn", None), "__code__", None)
            and str(src) in v.fn.__code__.co_filename
        ]
        for k in to_del:
            del _reg._HANDLERS[k]
    except Exception:
        pass
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── bpmn ────────────────────────────────────────────────────────────────────

BM = _load("bpmn")


def test_bpmn_esc_escapes_special_chars():
    assert BM._esc("a&b") == "a&amp;b"
    assert BM._esc("<tag>") == "&lt;tag&gt;"
    assert BM._esc('"quoted"') == "&quot;quoted&quot;"
    assert BM._esc("plain") == "plain"
    assert BM._esc(42) == "42"


def test_bpmn_compile_minimal_process():
    doc = {"id": "proc1", "name": "Test Process", "flow": [
        {"id": "start", "type": "startEvent", "next": "end"},
        {"id": "end", "type": "endEvent"},
    ]}
    xml = BM._compile_json_to_xml(doc)
    assert '<?xml version="1.0"' in xml
    assert 'id="proc1"' in xml
    assert 'name="Test Process"' in xml
    assert "<bpmn:startEvent" in xml
    assert "<bpmn:endEvent" in xml
    assert "<bpmn:sequenceFlow" in xml


def test_bpmn_compile_service_task():
    doc = {"id": "p2", "name": "P2", "flow": [
        {"id": "s1", "type": "startEvent", "next": "task1"},
        {"id": "task1", "type": "serviceTask", "nsid": "com.etzhayyim.test.foo", "resultAs": "result", "next": "e1"},
        {"id": "e1", "type": "endEvent"},
    ]}
    xml = BM._compile_json_to_xml(doc)
    assert "serviceTask" in xml
    assert "com.etzhayyim.test.foo" in xml


def test_bpmn_compile_exclusive_gateway():
    doc = {"id": "p3", "name": "P3", "flow": [
        {"id": "s", "type": "startEvent", "next": "gw"},
        {"id": "gw", "type": "exclusiveGateway", "then": "e1", "else": "e2", "condition": "x > 0"},
        {"id": "e1", "type": "endEvent"},
        {"id": "e2", "type": "endEvent"},
    ]}
    xml = BM._compile_json_to_xml(doc)
    assert "exclusiveGateway" in xml
    assert "sequenceFlow" in xml


def test_bpmn_compile_json_to_xml_udf_valid_input():
    body = json.dumps({"id": "p", "name": "P", "flow": []})
    out = json.loads(BM.compile_json_to_xml(body))
    assert "xml" in out
    assert "byteSize" in out
    assert out["byteSize"] > 0


def test_bpmn_compile_json_to_xml_udf_invalid_json():
    out = json.loads(BM.compile_json_to_xml("not-json"))
    assert "error" in out


def test_bpmn_compile_json_to_xml_udf_missing_id():
    body = json.dumps({"name": "P", "flow": []})
    out = json.loads(BM.compile_json_to_xml(body))
    assert "error" in out


def test_bpmn_compile_xrpc_wrapper():
    body = json.dumps({"json": {"id": "p", "name": "P", "flow": []}})
    out = json.loads(BM.compile_json_to_xml(body))
    assert "xml" in out


def test_bpmn_validate_xml_valid():
    body = json.dumps({"id": "p", "name": "P", "flow": []})
    xml = json.loads(BM.compile_json_to_xml(body))["xml"]
    out = json.loads(BM.validate_xml(xml))
    assert out.get("valid") is True


def test_bpmn_validate_xml_empty():
    out = json.loads(BM.validate_xml(""))
    assert "error" in out or out.get("valid") is False


def test_bpmn_validate_xml_missing_process():
    out = json.loads(BM.validate_xml("<?xml version='1.0'?><bpmn:definitions></bpmn:definitions>"))
    assert out.get("valid") is False


# ─── classify_t3 ─────────────────────────────────────────────────────────────

CL = _load("classify_t3")


def test_classify_t3_err_returns_json_with_error():
    out = json.loads(CL._err("bad input"))
    assert out["error"] == "bad input"


def test_classify_t3_skip_returns_skipped():
    out = json.loads(CL._skip("not-gray-zone", t1Score=30))
    assert out["skipped"] is True
    assert out["reason"] == "not-gray-zone"
    assert out["t1Score"] == 30


def test_classify_t3_build_user_prompt_includes_fields():
    fields = {
        "t1Score": 72,
        "fromAddr": "spam@bad.com",
        "subject": "You won!",
        "replyTo": "reply@elsewhere.com",
        "spf": "fail",
        "dkim": "fail",
        "dmarc": "fail",
        "bodyUrls": ["http://evil.com"],
    }
    prompt = CL._build_user_prompt(fields)
    assert "72" in prompt
    assert "spam@bad.com" in prompt
    assert "You won!" in prompt
    assert "http://evil.com" in prompt


def test_classify_t3_build_user_prompt_no_urls():
    fields = {"t1Score": 65, "fromAddr": "x@y.com", "subject": "hello"}
    prompt = CL._build_user_prompt(fields)
    assert "65" in prompt
    assert "x@y.com" in prompt


def test_classify_t3_phishing_t3_below_gray_zone_skips():
    out = json.loads(CL.phishing_t3(json.dumps({"t1Score": 30})))
    assert out.get("skipped") is True
    assert out["reason"] == "not-gray-zone"


def test_classify_t3_phishing_t3_above_gray_zone_skips():
    out = json.loads(CL.phishing_t3(json.dumps({"t1Score": 90})))
    assert out.get("skipped") is True


def test_classify_t3_phishing_t3_missing_score_errors():
    out = json.loads(CL.phishing_t3(json.dumps({})))
    assert "error" in out


def test_classify_t3_phishing_t3_invalid_json_errors():
    out = json.loads(CL.phishing_t3("not-json"))
    assert "error" in out


def test_classify_t3_phishing_t3_invalid_score_type_errors():
    out = json.loads(CL.phishing_t3(json.dumps({"t1Score": "notanint"})))
    assert "error" in out


def test_classify_t3_phishing_t3_gray_zone_calls_llm():
    fake_result = {
        "ok": True,
        "data": {"score": 80, "verdict": "phishing", "rationale": "Suspicious links"},
        "model": "test-model",
        "usage": {},
        "latencyMs": 100,
    }
    with patch.object(CL.llm, "call_tier_json", return_value=fake_result):
        out = json.loads(CL.phishing_t3(json.dumps({
            "t1Score": 72, "fromAddr": "x@bad.com", "subject": "Win!",
        })))
    assert out["verdict"] == "phishing"
    assert out["llmScore"] == 80
    assert out["t1Score"] == 72


# ─── gmail_contact ────────────────────────────────────────────────────────────

GC = _load("gmail_contact")


def test_gmail_parse_from_bare_email():
    name, email = GC._parse_from("alice@example.com")
    assert email == "alice@example.com"
    assert name == ""


def test_gmail_parse_from_display_name_and_angle():
    name, email = GC._parse_from('"Alice Smith" <alice@example.com>')
    assert email == "alice@example.com"
    assert name == "Alice Smith"


def test_gmail_parse_from_empty():
    name, email = GC._parse_from("")
    assert email == ""
    assert name == ""


def test_gmail_sanitize_path_segment_simple():
    assert GC.sanitize_path_segment("alice@example.com") == "alice-at-example-com"


def test_gmail_sanitize_path_segment_complex():
    result = GC.sanitize_path_segment("a.b+tag@x.co.jp")
    assert result == "a-b-tag-at-x-co-jp"


def test_gmail_sanitize_path_segment_uppercase():
    result = GC.sanitize_path_segment("ALICE@EXAMPLE.COM")
    assert result == "alice-at-example-com"


def test_gmail_sanitize_path_segment_max_length():
    long_email = "a" * 100 + "@example.com"
    result = GC.sanitize_path_segment(long_email)
    assert len(result) <= 63


def test_gmail_upsert_contact_missing_email_id():
    out = json.loads(GC.upsert_contact(json.dumps({"fromAddr": "x@y.com"})))
    assert "error" in out
    assert "emailId" in out["error"]


def test_gmail_upsert_contact_missing_from_addr():
    out = json.loads(GC.upsert_contact(json.dumps({"emailId": "email-abc"})))
    assert "error" in out
    assert "fromAddr" in out["error"]


def test_gmail_upsert_contact_invalid_json():
    out = json.loads(GC.upsert_contact("not-json"))
    assert "error" in out


def test_gmail_upsert_contact_no_at_sign():
    out = json.loads(GC.upsert_contact(json.dumps({
        "emailId": "email-001", "fromAddr": "notanemail"
    })))
    assert "error" in out


# ─── news_intel ───────────────────────────────────────────────────────────────

NI = _load("news_intel")


def test_news_intel_clamp01_in_range():
    assert NI._clamp01(0.5) == 0.5
    assert NI._clamp01(0.0) == 0.0
    assert NI._clamp01(1.0) == 1.0


def test_news_intel_clamp01_below_zero():
    assert NI._clamp01(-0.5) == 0.0


def test_news_intel_clamp01_above_one():
    assert NI._clamp01(1.5) == 1.0


def test_news_intel_source_credibility_government():
    score = NI.source_credibility("government", False, True)
    assert 0.0 <= score <= 1.0
    assert score >= 0.7


def test_news_intel_source_credibility_unknown_type():
    score = NI.source_credibility("unknown_type_xyz", False, False)
    assert 0.0 <= score <= 1.0


def test_news_intel_source_credibility_primary_adds_bonus():
    base = NI.source_credibility("newspaper", False, False)
    with_primary = NI.source_credibility("newspaper", True, False)
    assert with_primary > base


def test_news_intel_source_credibility_official_adds_bonus():
    base = NI.source_credibility("newspaper", False, False)
    with_official = NI.source_credibility("newspaper", False, True)
    assert with_official > base


def test_news_intel_priority_zero_evidence():
    score = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    assert 0.0 <= score <= 1.0


def test_news_intel_priority_high_evidence():
    score = NI.intel_priority(10, 5, 5, 1.0, 0.9)
    assert score > 0.5


def test_news_intel_priority_old_news_lower_score():
    fresh = NI.intel_priority(3, 2, 2, 1.0, 0.5)
    stale = NI.intel_priority(3, 2, 2, 100.0, 0.5)
    assert fresh > stale


def test_news_intel_priority_clamped_to_one():
    score = NI.intel_priority(100, 100, 100, 0.0, 1.0)
    assert score <= 1.0


# ─── ingest ──────────────────────────────────────────────────────────────────

IN = _load("ingest")


def test_ingest_loads_valid_json():
    result = IN._loads('{"key": "value"}')
    assert result == {"key": "value"}


def test_ingest_loads_invalid_json_raises():
    import pytest
    with pytest.raises(Exception):
        IN._loads("not-json")


def test_ingest_loads_empty_returns_empty():
    result = IN._loads("")
    assert result == {}


def test_ingest_dump_returns_json_string():
    out = IN._dump({"ok": True, "count": 5})
    assert json.loads(out) == {"ok": True, "count": 5}


def test_ingest_require_str_present():
    params = {"collection": "com.etzhayyim.apps.news.article"}
    result = IN._require_str(params, "collection")
    assert result == "com.etzhayyim.apps.news.article"


def test_ingest_require_str_missing():
    import pytest
    with pytest.raises(ValueError, match="collection"):
        IN._require_str({}, "collection")


def test_ingest_mode_default():
    assert IN._mode({}) == "delta"


def test_ingest_mode_explicit():
    assert IN._mode({"mode": "backfill"}) == "backfill"
    assert IN._mode({"mode": "repair"}) == "repair"
    assert IN._mode({"mode": "verify"}) == "verify"


def test_ingest_plan_returns_error_without_collection():
    out = json.loads(IN.ingest_plan("{}"))
    assert "error" in out


def test_ingest_plan_invalid_json():
    out = json.loads(IN.ingest_plan("not-json"))
    assert "error" in out


def test_ingest_start_returns_error_without_collection():
    out = json.loads(IN.ingest_start("{}"))
    assert "error" in out


def test_ingest_status_returns_error_without_run_id():
    out = json.loads(IN.ingest_status("{}"))
    assert "error" in out


def test_ingest_validate_returns_error_without_collection():
    out = json.loads(IN.ingest_validate("{}"))
    assert "error" in out
