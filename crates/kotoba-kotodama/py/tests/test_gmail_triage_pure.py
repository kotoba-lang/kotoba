"""Pure-logic tests for gmail.triage.v1 LangGraph agent.

No DB, no LLM, no Zeebe. Exercises:
  - _phish_score (rule-based scoring)
  - _domain_of / _allowlisted (sender allowlist)
  - _has_label (Gmail label CSV parsing)
  - _sanitize_addr (yabai vertex_id key)
  - _yabai_evidence_meta (ADR-0032 mapping)
  - _node_t1 (SQL rules classifier, classification + score + reasons)
  - _has_gray (conditional edge gate)
  - StateGraph compile (smoke test that LangGraph wires up)
"""

from __future__ import annotations

import asyncio

import pytest

from kotodama.agents.gmail_triage import (
    _allowlisted,
    _domain_of,
    _has_gray,
    _has_label,
    _node_t1,
    _phish_score,
    _reputation_score_bump,
    _sanitize_addr,
    _yabai_evidence_meta,
    gmail_triage_graph,
)


# ── _domain_of / _allowlisted ──────────────────────────────────────────


def test_domain_of_with_angle_brackets():
    assert _domain_of('"Alice" <alice@example.com>') == "example.com"


def test_domain_of_bare_address():
    assert _domain_of("bob@etzhayyim.com") == "etzhayyim.com"


def test_domain_of_empty():
    assert _domain_of("") == ""


def test_allowlisted_exact():
    assert _allowlisted("noreply@github.com") is True


def test_allowlisted_subdomain():
    assert _allowlisted("notifications@subdomain.github.com") is True


def test_allowlisted_negative():
    assert _allowlisted("attacker@phishing.example.tld") is False


# ── _has_label ─────────────────────────────────────────────────────────


def test_has_label_spam_caps():
    assert _has_label("INBOX,SPAM,UNREAD", "SPAM") is True


def test_has_label_lowercase():
    assert _has_label("inbox,trash", "TRASH") is True


def test_has_label_partial_no_match():
    # "SPAMMY" is not "SPAM"
    assert _has_label("INBOX,SPAMMY", "SPAM") is False


def test_has_label_empty():
    assert _has_label("", "SPAM") is False


# ── _phish_score ───────────────────────────────────────────────────────


def test_phish_score_clean():
    score, reasons = _phish_score("pass", "pass", "pass", "", "user@etzhayyim.com", "Welcome", "")
    assert score == 0
    assert reasons == []


def test_phish_score_auth_fail_triple():
    score, reasons = _phish_score("fail", "fail", "fail", "", "x@y.tld", "Hello", "")
    assert score == 65  # 20+20+25
    assert any("spf=" in r for r in reasons)
    assert any("dkim=" in r for r in reasons)
    assert any("dmarc=" in r for r in reasons)


def test_phish_score_reply_to_mismatch():
    score, _ = _phish_score(
        "pass", "pass", "pass",
        "attacker@evil.tld", "support@bank.example",
        "Account update", "",
    )
    assert score >= 15


def test_phish_score_keyword_hit():
    score, reasons = _phish_score(
        "pass", "pass", "pass", "", "x@y.tld",
        "URGENT: verify your password now", "",
    )
    assert score >= 15
    assert "subject-keyword" in reasons


def test_phish_score_url_with_unknown_host_bonus():
    score, reasons = _phish_score(
        "pass", "pass", "pass", "", "x@y.tld",
        "ok", '["https://random-attacker.tld/path"]',
    )
    assert score >= 15  # 10 url + 5 url-host bonus
    assert any(r.startswith("url-host:") for r in reasons)


def test_phish_score_url_allowlisted_host_no_bonus():
    score, _ = _phish_score(
        "pass", "pass", "pass", "", "x@y.tld",
        "ok", '["https://github.com/foo"]',
    )
    assert score == 10  # base url, no host bonus


def test_phish_score_caps_at_100():
    score, _ = _phish_score(
        "fail", "fail", "fail",
        "a@evil.tld", "b@target.tld",
        "URGENT verify password account suspend",
        '["https://attacker.tld"]',
    )
    assert score == 100


# ── _sanitize_addr ─────────────────────────────────────────────────────


def test_sanitize_addr_basic():
    assert _sanitize_addr("alice@example.com") == "alice_at_example.com"


def test_sanitize_addr_strips_special():
    out = _sanitize_addr('"X" <a+b@foo.bar.tld>')
    assert "@" not in out
    assert "<" not in out
    assert ">" not in out


def test_sanitize_addr_unknown():
    # Empty input falls through to "_at_unknown" → strip leading underscores
    assert _sanitize_addr("") == "at_unknown"


def test_sanitize_addr_max_len():
    long = "a" * 300 + "@example.com"
    out = _sanitize_addr(long)
    assert len(out) <= 120


# ── _yabai_evidence_meta ───────────────────────────────────────────────


def test_evidence_meta_spam():
    cat, conf, sev = _yabai_evidence_meta("spam")
    assert cat == "FraudSignal"
    assert conf == 0.85
    assert sev == 8


def test_evidence_meta_trash():
    cat, conf, sev = _yabai_evidence_meta("trash")
    assert cat == "IntelExtraction"
    assert conf == 0.60
    assert sev == 4


def test_evidence_meta_gray():
    cat, conf, sev = _yabai_evidence_meta("gray")
    assert cat == "FraudSignal"
    assert conf == 0.55
    assert sev == 5


def test_evidence_meta_clean():
    cat, conf, sev = _yabai_evidence_meta("clean")
    assert cat == ""
    assert conf == 0.0
    assert sev == 0


# ── _node_t1 (rule classifier) ─────────────────────────────────────────


def _row(**overrides) -> dict:
    base = {
        "vertex_id": "at://did:web:gmail.etzhayyim.com/com.etzhayyim.apps.gmail.email/email-x",
        "email_id": "email-x",
        "from_addr": "x@y.tld",
        "reply_to": "",
        "subject": "Hello",
        "snippet": "",
        "body_urls_json": "",
        "labels": "INBOX",
        "spf_result": "pass",
        "dkim_result": "pass",
        "dmarc_result": "pass",
        "account_email": "jun784@gmail.com",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_t1_spam_label_wins():
    state = {"claimed": [_row(labels="INBOX,SPAM")]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "spam"
    assert out["claimed"][0]["score"] == 85
    assert "gmail-label:SPAM" in out["claimed"][0]["reasons"]
    assert out["grayIds"] == []


@pytest.mark.asyncio
async def test_t1_trash_label():
    state = {"claimed": [_row(labels="INBOX,TRASH")]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "trash"
    assert out["claimed"][0]["score"] == 60


@pytest.mark.asyncio
async def test_t1_allowlisted_clean():
    state = {"claimed": [_row(from_addr="ito@shimoda-bs.jp", subject="urgent verify password")]}
    out = await _node_t1(state)
    # Allowlist beats keyword hit
    assert out["claimed"][0]["classification"] == "clean"
    assert out["claimed"][0]["score"] == 0


@pytest.mark.asyncio
async def test_t1_heuristic_high_score_spam():
    state = {"claimed": [_row(
        from_addr="attacker@phish.tld",
        reply_to="evil@elsewhere.tld",
        subject="URGENT verify password account suspend",
        spf_result="fail",
        dkim_result="fail",
        dmarc_result="fail",
        body_urls_json='["https://random.tld"]',
    )]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "spam"
    assert out["claimed"][0]["score"] >= 70


@pytest.mark.asyncio
async def test_t1_heuristic_gray_zone():
    # 20+20+25 = 65, falls into 40-69 gray zone
    state = {"claimed": [_row(
        from_addr="x@unknown.tld",
        spf_result="fail",
        dkim_result="fail",
        dmarc_result="fail",
    )]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "gray"
    assert 40 <= out["claimed"][0]["score"] < 70
    assert len(out["grayIds"]) == 1


@pytest.mark.asyncio
async def test_t1_heuristic_low_clean():
    state = {"claimed": [_row(
        from_addr="x@unknown.tld",
        subject="Notes",
    )]}
    out = await _node_t1(state)
    assert out["claimed"][0]["classification"] == "clean"
    assert out["claimed"][0]["score"] < 40


# ── _has_gray (conditional edge) ───────────────────────────────────────


def test_has_gray_routes_to_t3():
    assert _has_gray({"grayIds": ["foo", "bar"]}) == "t3"


def test_has_gray_routes_to_synth_when_empty():
    assert _has_gray({"grayIds": []}) == "synth"


def test_has_gray_routes_to_synth_when_missing():
    assert _has_gray({}) == "synth"


# ── _reputation_score_bump (Phase 3 T2) ────────────────────────────────


def test_reputation_bump_no_history():
    delta, reasons = _reputation_score_bump({})
    assert delta == 0
    assert reasons == []


def test_reputation_bump_low_count_no_bump():
    delta, reasons = _reputation_score_bump({"evidence_count_24h": 2, "max_severity_24h": 5})
    assert delta == 0
    assert reasons == []


def test_reputation_bump_3_offenses():
    delta, reasons = _reputation_score_bump({"evidence_count_24h": 3, "max_severity_24h": 5})
    assert delta == 15
    assert any("cnt24h=3" in r for r in reasons)


def test_reputation_bump_5_offenses():
    delta, reasons = _reputation_score_bump({"evidence_count_24h": 5, "max_severity_24h": 5})
    assert delta == 25
    assert any("cnt24h=5" in r for r in reasons)


def test_reputation_bump_high_severity():
    delta, reasons = _reputation_score_bump({"evidence_count_24h": 1, "max_severity_24h": 8})
    assert delta == 10
    assert any("maxSev=8" in r for r in reasons)


def test_reputation_bump_compound():
    # 5 offenses (+25) + sev 9 (+10) = 35
    delta, reasons = _reputation_score_bump({"evidence_count_24h": 5, "max_severity_24h": 9})
    assert delta == 35
    assert len(reasons) == 2


# ── StateGraph compile smoke ───────────────────────────────────────────


def test_graph_registered_in_registry():
    from kotodama.primitives import langgraph_registry

    assert langgraph_registry.get("gmail.triage.v1") is gmail_triage_graph


def test_graph_has_expected_nodes():
    # CompiledStateGraph exposes .get_graph() with nodes set
    g = gmail_triage_graph.get_graph()
    nodes = set(g.nodes.keys())
    # Phase 1 + Phase 3 nodes
    assert {"claim", "t1", "t2_rep", "t3", "synth", "register", "mark"}.issubset(nodes)
