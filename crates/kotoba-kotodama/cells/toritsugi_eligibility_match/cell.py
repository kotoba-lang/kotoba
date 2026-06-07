"""ToritsugiEligibilityMatchCell — toritsugi R0 Pregel cell.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge).

Purpose: proactively match a CONSENTING member's OWN life-event/profile against
the available 制度/給付/手続き and raise an `com.etzhayyim.toritsugi.benefitMatch`
("you may be eligible for X" — the LINE-公式アカウント notify role). A soft
signal only, NEVER an adjudication of eligibility.

Constitutional ceiling (CRITICAL — IMMUTABLE): G3 consent-gated + OWN-data-only
(never a third party; member-initiated consent + Adherent-SBT/DID binding),
G5 no eligibility/legal determination (soft signal → guide → chigiri/licensed),
G6 any member PII used lands ONLY in com.etzhayyim.encrypted.* (ADR-2605181100;
never inline PII), G8 no fabricated entitlement (cite the criterion + legalBasis),
G12 data-minimization, Murakumo-only inference (ADR-2605215000).
Output Lexicon(s): com.etzhayyim.toritsugi.benefitMatch.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605312030 §8 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 multisig has attested ADR-2605312030.
#   2. The member-consent intake schema is live (G3 — no match without a
#      resolvable member consent + DID/SBT binding for the member's OWN data).
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
MEMBER_CONSENT_SCHEMA_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or MEMBER_CONSENT_SCHEMA_REF is None
):
    raise RuntimeError(
        "toritsugi R0 scaffold: activate via Council ADR-2605312030 "
        "post-ratification — Council has not attested the toritsugi master "
        "charter (Lv6+ ≥3), and/or MEMBER_CONSENT_SCHEMA_REF is unset "
        "(the G3 consent binding). Do not deploy. CONSENT-GATED / "
        "OWN-DATA-ONLY (G3) / NO-ELIGIBILITY-DETERMINATION (G5) ceiling is "
        "constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class ToritsugiEligibilityMatchCell(PregelCell):
#     process_step = "toritsugi_eligibility_match"
#     pregel_tier = "B"
#     murakumo_node = "reuben"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("toritsugi R1")


__all__ = ["ToritsugiEligibilityMatchCell"]
