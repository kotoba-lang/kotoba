"""ToritsugiIntakeCell — toritsugi R0 Pregel cell.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge).

Purpose: take a member's consent + DID/SBT binding + need/life-event and open an
`com.etzhayyim.toritsugi.procedureGuide` session for a single procedure. The
member is the named 申請者本人 from this point on.

Constitutional ceiling (CRITICAL — IMMUTABLE): G3 consent-gated + identity-bound,
OWN procedure only; G4 the member is always the named 申請者本人 (no
impersonation; toritsugi is an unofficial assistant, never an official 自治体
channel); kotoba-EAVT-native (ADR-2605262130). Output Lexicon(s):
com.etzhayyim.toritsugi.procedureGuide.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605312030 §8 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 multisig has attested ADR-2605312030.
#   2. The member-consent intake schema is live (G3).
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
        "OWN-PROCEDURE-ONLY (G3) / MEMBER-IS-APPLICANT (G4) ceiling is "
        "constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class ToritsugiIntakeCell(PregelCell):
#     process_step = "toritsugi_intake"
#     pregel_tier = "B"
#     murakumo_node = "reuben"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("toritsugi R1")


__all__ = ["ToritsugiIntakeCell"]
