"""KizashiTriageReferralCell — kizashi R0 Pregel cell.

Per ADR-2605312700 (兆 kizashi). Cell §3 #5; Murakumo node `naphtali`.

Purpose: route a non-diagnostic attribution to the clinical-adjudication actors
(mitate / iyashi / kokoro) and escalate red-flag signs immediately. Emits
`com.etzhayyim.kizashi.triageReferral`.

Constitutional ceiling (CRITICAL — IMMUTABLE): G5 emergency red-flag → immediate
受診/救急 routing via the shared emergency-keyword lexicon (mitate/iyashi/kokoro),
never "wait for next scan"; G3 kizashi can only REFER — targetActor is
const-enum {mitate, iyashi, kokoro}; it cannot close a clinical loop itself;
G6 sharing scan provenance requires consent; G14 Murakumo-only inference.
Output Lexicon(s): com.etzhayyim.kizashi.triageReferral.

R0 scaffold — import-time RuntimeError until R2.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R2 activation gate (ADR-2605312700 §7 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥4 + 30-day public objection (ships with R2).
#   2. mitate R1 active — the sign→diagnosis handoff + shared G5
#      emergency-keyword lexicon must be production-deployed.
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
MITATE_EMERGENCY_KEYWORD_LEXICON_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or MITATE_EMERGENCY_KEYWORD_LEXICON_REF is None
):
    raise RuntimeError(
        "kizashi R0 scaffold: activate via Council ADR-2605312700 "
        "post-ratification — Council charter unattested (Lv6+ ≥4 + public, R2), "
        "and/or MITATE_EMERGENCY_KEYWORD_LEXICON_REF unset (the shared G5 "
        "emergency-keyword lexicon requires mitate R1 active). Do not deploy. "
        "REFER-ONLY (G3) + EMERGENCY-ESCALATION (G5) ceiling is constitutional — "
        "kizashi routes to mitate/iyashi/kokoro, never self-treats."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class KizashiTriageReferralCell(PregelCell):
#     process_step = "kizashi_triage_referral"
#     pregel_tier = "B"
#     murakumo_node = "naphtali"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kizashi R2")


__all__ = ["KizashiTriageReferralCell"]
