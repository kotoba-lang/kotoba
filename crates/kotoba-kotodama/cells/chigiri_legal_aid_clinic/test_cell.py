"""Constitutional-guard regression tests for ChigiriLegalAidClinicCell.

Locks in the gates of ADR-2605302200 / 2605302330 / 2605302345:
  G14 — no advice is ever produced (classifier label-only).
  G15 — the matter charges the adherent nothing (zero compensation).
  G16 — no advance past intake without in-jurisdiction Public-Fund counsel.

These exercise the cell's pure node/guard functions + the concrete ports
directly (no live graph / network), so they run deterministically in CI.
"""

from __future__ import annotations

import pytest

from .cell import (
    PRACTICE_AREAS,
    _assert_no_advice,
    assert_zero_compensation,
    assign_counsel,
    check_jurisdiction,
    emit_matter_record,
    route_after_counsel,
    triage_classify,
)
from .ports import JurisdictionPolicyPort, KotobaMstPort, PublicFundCounselPort


# ── G14: no advice ────────────────────────────────────────────────────


def test_g14_valid_label_normalizes():
    assert _assert_no_advice("Housing") == "housing"


@pytest.mark.parametrize("leak", [
    "You should sue your landlord under Art. 90",
    "I advise you to settle",
    "housing dispute, file within 30 days",  # multi-token → not a bare label
    "",
])
def test_g14_advice_leak_rejected(leak):
    with pytest.raises(ValueError):
        _assert_no_advice(leak)


def test_g14_triage_constrained_to_enum():
    class StubMurakumo:
        def classify(self, summary_cid, labels, summary_text=""):
            return "you should counter-sue"  # advice leak from the model
    # the port itself would already coerce; the cell re-validates to a label
    out = triage_classify({"practice_area": "labor"}, StubMurakumo())
    assert out["practice_area"] in PRACTICE_AREAS
    assert out["lane"] == "advice"


# ── G15: zero compensation ────────────────────────────────────────────


def test_g15_assert_zero_compensation_pins_true():
    assert assert_zero_compensation({})["zero_compensation"] is True


def test_g15_emitted_record_is_gratuitous():
    class StubMst:
        def put(self, nsid, record):
            assert record["zeroCompensation"] is True
            assert not ({"fee", "price", "amount", "tithe"} & set(record))
            return "at://kotoba/matter"
    out = emit_matter_record({
        "adherent_did": "did:web:a", "jurisdiction": "jpn", "lane": "advice",
        "supervising_counsel_did": "did:web:lawyer", "counsel_license_jurisdiction": "jpn",
    }, StubMst())
    assert out["intake_state"] == "counsel-assigned"


def test_g15_port_put_rejects_consideration():
    port = KotobaMstPort(url="http://localhost:1")  # guard fires before any I/O
    with pytest.raises(ValueError):
        port.put("com.etzhayyim.chigiri.legalAidMatter",
                 {"adherentDid": "did:a", "fee": 1000})


# ── G16: in-jurisdiction Public-Fund counsel before advancing ─────────


def test_g16_jurisdiction_enabled_vs_verify_required():
    pol = JurisdictionPolicyPort(None)
    assert pol.lookup("jpn")["enableState"] == "enabled"
    assert pol.lookup("aut")["enableState"] == "verify-required"  # Austria not activated
    assert pol.lookup("zz")["enableState"] == "verify-required"


def test_g16_check_jurisdiction_rejects_verify_required():
    out = check_jurisdiction({"jurisdiction": "aut", "jurisdiction_enabled": False}, None)
    assert out["jurisdiction_enabled"] is False
    assert "verify-required" in out["rejection_reason"]


def test_g16_assign_counsel_requires_matching_license():
    registry = {"jpn": [{"did": "did:web:lawyer", "license_jurisdiction": "jpn"}]}
    port = PublicFundCounselPort(registry)
    ok = assign_counsel({"jurisdiction": "jpn", "practice_area": "housing"}, port)
    assert ok["supervising_counsel_did"] == "did:web:lawyer"
    assert ok["counsel_retained_via_public_fund"] is True
    # no counsel onboarded in this jurisdiction → held at intake
    held = assign_counsel({"jurisdiction": "fra", "practice_area": "housing"}, port)
    assert "supervising_counsel_did" not in held
    assert "no Public-Fund counsel" in held["rejection_reason"]


@pytest.mark.parametrize("state,expected", [
    ({"supervising_counsel_did": "did:l", "counsel_retained_via_public_fund": True,
      "counsel_license_jurisdiction": "jpn", "jurisdiction": "jpn",
      "zero_compensation": True}, "emit_matter_record"),
    ({"jurisdiction": "jpn", "zero_compensation": True}, "emit_rejection"),  # no counsel
    ({"supervising_counsel_did": "did:l", "counsel_retained_via_public_fund": True,
      "counsel_license_jurisdiction": "usa", "jurisdiction": "jpn",
      "zero_compensation": True}, "emit_rejection"),                         # license != matter
    ({"supervising_counsel_did": "did:l", "counsel_retained_via_public_fund": True,
      "counsel_license_jurisdiction": "jpn", "jurisdiction": "jpn",
      "zero_compensation": False}, "emit_rejection"),                        # comp not asserted
])
def test_g16_g15_final_gate(state, expected):
    assert route_after_counsel(state) == expected
