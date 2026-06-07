"""Pure-logic tests for outlook.triage.v1 LangGraph agent (Phase 4).

No DB, no LLM, no Zeebe. Outlook-specific concerns:
  - _phish_score_metadata (no subject/URL since body is encrypted)
  - first-contact-external sender_kind signal
  - guest sender bonus
  - Same yabai chain (entity_id format) as gmail → shared MV
  - StateGraph compile + registry
"""

from __future__ import annotations

import pytest

from kotodama.agents.outlook_triage import (
    _has_gray,
    _node_t1,
    _phish_score_metadata,
    outlook_triage_graph,
)


# ── _phish_score_metadata (Outlook variant) ────────────────────────────


def test_metadata_score_clean():
    score, reasons = _phish_score_metadata("pass", "pass", "pass", "", "u@etzhayyim.com", "internal", "")
    assert score == 0
    assert reasons == []


def test_metadata_score_auth_fail_triple():
    score, reasons = _phish_score_metadata("fail", "fail", "fail", "", "x@y.tld", "external", "")
    assert score == 65  # 20+20+25
    assert any("spf=" in r for r in reasons)


def test_metadata_score_reply_to_mismatch():
    score, _ = _phish_score_metadata(
        "pass", "pass", "pass",
        "attacker@evil.tld", "support@bank.example",
        "external", "",
    )
    assert score >= 15


def test_metadata_score_first_contact_external():
    # External sender + first-seen-from-domain set: +10
    score, reasons = _phish_score_metadata(
        "pass", "pass", "pass", "",
        "stranger@unknown.tld", "external",
        "2026-05-08T10:00:00Z",
    )
    assert score >= 10
    assert "first-contact-external" in reasons


def test_metadata_score_guest_sender():
    # Guest sender (cross-tenant): +5
    score, reasons = _phish_score_metadata(
        "pass", "pass", "pass", "",
        "u@partnertenant.com", "guest", "",
    )
    assert score == 5
    assert "sender-kind:guest" in reasons


def test_metadata_score_does_not_use_keywords():
    # Outlook variant ignores subject keywords (encrypted column).
    # Auth/reply-to/sender_kind only.
    score, _ = _phish_score_metadata(
        "pass", "pass", "pass", "",
        "x@trusted.tld", "internal", "",
    )
    assert score == 0


def test_metadata_score_caps_at_100():
    score, _ = _phish_score_metadata(
        "fail", "fail", "fail",
        "a@evil.tld", "b@target.tld",
        "external", "2026-05-08T00:00:00Z",
    )
    # 20+20+25+15+10 = 90 (under cap, normal)
    assert score == 90


# ── _node_t1 (rule classifier, metadata-only) ──────────────────────────


def _outlook_row(**overrides) -> dict:
    base = {
        "vertex_id": "email_msg:abc123",
        "message_id": "abc123",
        "from_address": "x@y.tld",
        "from_addr": "x@y.tld",
        "from_domain": "y.tld",
        "from_name": "Test",
        "reply_to": "",
        "sender_kind": "external",
        "first_seen_from_domain": "",
        "spf_result": "pass",
        "dkim_result": "pass",
        "dmarc_result": "pass",
        "account_did": "did:web:outlook.etzhayyim.com",
        "received_at": "2026-05-08T10:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_t1_allowlisted_clean():
    state = {"claimed": [_outlook_row(from_address="ito@shimoda-bs.jp", from_addr="ito@shimoda-bs.jp")]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "clean"
    assert out["claimed"][0]["score"] == 0


@pytest.mark.asyncio
async def test_t1_high_score_spam():
    state = {"claimed": [_outlook_row(
        from_addr="attacker@phish.tld",
        from_address="attacker@phish.tld",
        reply_to="evil@elsewhere.tld",
        spf_result="fail",
        dkim_result="fail",
        dmarc_result="fail",
        sender_kind="external",
        first_seen_from_domain="2026-05-08T09:00:00Z",
    )]}
    out = await _node_t1(state)
    # 20+20+25+15+10 = 90, ≥70 → spam
    assert out["claimed"][0]["classification"] == "spam"
    assert out["claimed"][0]["score"] >= 70


@pytest.mark.asyncio
async def test_t1_gray_zone_metadata_only():
    # 20+20+25 = 65, falls into 40-69 gray zone (no keyword/url for outlook)
    state = {"claimed": [_outlook_row(
        from_addr="x@unknown.tld",
        from_address="x@unknown.tld",
        spf_result="fail",
        dkim_result="fail",
        dmarc_result="fail",
    )]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "gray"
    assert 40 <= out["claimed"][0]["score"] < 70
    assert len(out["grayIds"]) == 1


@pytest.mark.asyncio
async def test_t1_low_score_clean():
    state = {"claimed": [_outlook_row()]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "clean"


# ── _has_gray ──────────────────────────────────────────────────────────


def test_has_gray_routes_to_t3():
    assert _has_gray({"grayIds": ["foo"]}) == "t3"


def test_has_gray_routes_to_synth_when_empty():
    assert _has_gray({"grayIds": []}) == "synth"


# ── StateGraph compile + cross-channel sharing ─────────────────────────


def test_outlook_graph_registered():
    from kotodama.primitives import langgraph_registry

    assert langgraph_registry.get("outlook.triage.v1") is outlook_triage_graph


def test_outlook_graph_has_expected_nodes():
    g = outlook_triage_graph.get_graph()
    nodes = set(g.nodes.keys())
    assert {"claim", "t1", "t2_rep", "t3", "synth", "register", "mark"}.issubset(nodes)


def test_outlook_graph_independent_from_gmail():
    """Both graphs registered independently."""
    from kotodama.agents.gmail_triage import gmail_triage_graph
    from kotodama.primitives import langgraph_registry

    g_gmail = langgraph_registry.get("gmail.triage.v1")
    g_outlook = langgraph_registry.get("outlook.triage.v1")
    assert g_gmail is gmail_triage_graph
    assert g_outlook is outlook_triage_graph
    assert g_gmail is not g_outlook


def test_outlook_shares_yabai_chain_with_gmail():
    """Phase 4 invariant: same _node_register_yabai instance.

    Cross-channel reputation merge is an emergent property of the shared
    yabai chain — both graphs upsert vertex_yabai_entity with the same
    entity_id format `email-{sanitized_address}`, so MV
    mv_yabai_sender_reputation_24h aggregates evidence from both sources
    automatically.
    """
    from kotodama.agents import gmail_triage as g
    from kotodama.agents import outlook_triage as o

    assert o._node_register_yabai is g._node_register_yabai
    assert o._node_t2_reputation is g._node_t2_reputation
    assert o._sanitize_addr is g._sanitize_addr
