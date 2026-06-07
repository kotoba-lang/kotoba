"""Unit + determinism tests for FeedPostCell (kotoba-datomic §4 L3)."""

from __future__ import annotations

import pytest

from .cell import verdict_for


def _baseline_record(**overrides):
    rec = {
        "$type": "app.bsky.feed.post",
        "text": "hello kotoba-datomic",
        "createdAt": "2026-05-23T00:00:00Z",
    }
    rec.update(overrides)
    return rec


def test_approve_simple_post():
    out = verdict_for(_baseline_record())
    assert out["verdict_kind"] == "approve"
    assert out["verdict_reason"] == "ok"
    assert out["verdict_evidence"] == []
    assert out["verdict_record"]["verdict"] == "approve"


def test_reject_schema_missing_created_at():
    rec = {"$type": "app.bsky.feed.post", "text": "no createdAt"}
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    cats = {e["category"] for e in out["verdict_evidence"]}
    assert "schema" in cats


def test_reject_schema_text_too_long():
    rec = _baseline_record(text="x" * 3001)
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["evidence"] == "text-exceeds-3000" for e in out["verdict_evidence"])


def test_reject_weapons_2a():
    rec = _baseline_record(text="we sell assault rifle replicas commercially")
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["category"] == "2a" for e in out["verdict_evidence"])


def test_allow_weapons_2a_with_historical_context():
    rec = _baseline_record(
        text="historical analysis of munition treaties since 1925 geneva protocol"
    )
    out = verdict_for(rec)
    assert out["verdict_kind"] == "approve", out


def test_reject_advertising():
    rec = _baseline_record(text="use my affiliate link for a 30% discount code")
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["category"] == "advertising" for e in out["verdict_evidence"])


def test_reject_eschatology_assertion_en():
    rec = _baseline_record(text="the rapture is coming, prepare")
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["category"] == "eschatology" for e in out["verdict_evidence"])


def test_reject_eschatology_assertion_ja():
    rec = _baseline_record(text="末法到来。世界は終わる")
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["category"] == "ja-prohibited" for e in out["verdict_evidence"])


def test_escalate_gore_with_educational_context():
    rec = _baseline_record(
        text="documentary on war crime — historical record",
        labels={"values": [{"val": "gore"}]},
    )
    out = verdict_for(rec)
    assert out["verdict_kind"] == "escalate"
    assert out["verdict_reason"] == "council-required"


def test_reject_gore_without_educational_context():
    rec = _baseline_record(
        text="content warning",
        labels={"values": [{"val": "gore"}]},
    )
    out = verdict_for(rec)
    assert out["verdict_kind"] == "reject"
    assert any(e["category"] == "gore" for e in out["verdict_evidence"])


def test_determinism_same_input_same_verdict_cid():
    rec = _baseline_record(text="determinism check 1")
    a = verdict_for(rec, record_cid="bafyrei-fake-1")
    b = verdict_for(rec, record_cid="bafyrei-fake-1")
    assert a["verdict_cid_input"] == b["verdict_cid_input"]
    assert a["verdict_kind"] == b["verdict_kind"]


def test_record_cid_changes_verdict_cid_input():
    rec = _baseline_record()
    a = verdict_for(rec, record_cid="bafy-aaa")
    b = verdict_for(rec, record_cid="bafy-bbb")
    assert a["verdict_cid_input"] != b["verdict_cid_input"]


def test_no_clock_dependency_emit_record_uses_ctx_now():
    rec = _baseline_record()
    out = verdict_for(rec, ctx={"now": "2026-05-23T01:02:03Z"})
    assert out["verdict_record"]["createdAt"] == "2026-05-23T01:02:03Z"


def test_external_rego_decision_overrides_python_mirror():
    rec = _baseline_record(text="this would be fine but ctx says block")
    ctx_decision = {
        "allow": False,
        "reason": "external-rego-block",
        "violations": [{"category": "external", "evidence": "OPA sidecar said no"}],
        "obligations": ["audit_charter_block"],
    }
    out = verdict_for(rec, ctx={"rego": {"decision": ctx_decision}})
    assert out["verdict_kind"] == "reject"
    cats = {e["category"] for e in out["verdict_evidence"]}
    assert "external" in cats


@pytest.mark.parametrize(
    "text,expected_kind",
    [
        ("hello kotoba-datomic", "approve"),
        ("assault rifle wholesale", "reject"),
        ("limited time offer click my referral", "reject"),
        ("historical treaty review (munition)", "approve"),
    ],
)
def test_table_driven(text, expected_kind):
    out = verdict_for(_baseline_record(text=text))
    assert out["verdict_kind"] == expected_kind, out
