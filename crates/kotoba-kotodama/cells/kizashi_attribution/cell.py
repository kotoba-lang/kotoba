"""KizashiAttributionCell — kizashi R0 Pregel cell.

Per ADR-2605312700 (兆 kizashi). Cell §3 #3; Murakumo node `gad`.

Purpose: emit a PROBABILISTIC, NON-DIAGNOSTIC cause-contribution report —
candidate contributing factors (never diseases) with calibrated confidence, a
structural disclaimer, and a consult recommendation. "kizashi senses; mitate
diagnoses." Emits `com.etzhayyim.kizashi.attributionReport`.

Constitutional ceiling (CRITICAL — IMMUTABLE — the load-bearing cell):
G3 NON-DIAGNOSTIC (医師法 §17) — the attributionReport schema FORBIDS
diagnosis / prescription / treatmentPlan; a licensed clinician (mitate/iyashi)
owns any diagnosis; G7 uncertainty-honest — confidence + "所見≠確定原因" disclaimer
+ consultRecommendation are required, no false precision; G2 encrypted I/O;
G14 Murakumo-only inference (ADR-2605215000), no vendor medical-AI.
Output Lexicon(s): com.etzhayyim.kizashi.attributionReport.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605312700 §7 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 ratify of ADR-2605312700.
#   2. ≥1 licensed-MD on Council medical advisory (G3 non-diagnostic boundary
#      review — shared with mitate/iyashi).
#   3. The encrypted-records envelope backend is live (G2).
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
LICENSED_MD_COUNCIL_ADVISORY_REF: str | None = None
ENCRYPTED_ENVELOPE_BACKEND_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or LICENSED_MD_COUNCIL_ADVISORY_REF is None
    or ENCRYPTED_ENVELOPE_BACKEND_REF is None
):
    raise RuntimeError(
        "kizashi R0 scaffold: activate via Council ADR-2605312700 "
        "post-ratification — Council charter unattested (Lv6+ ≥3), and/or no "
        "licensed-MD on Council medical advisory (LICENSED_MD_COUNCIL_ADVISORY_REF "
        "unset; required to review the G3 non-diagnostic boundary), and/or "
        "ENCRYPTED_ENVELOPE_BACKEND_REF unset (G2). Do not deploy. "
        "NON-DIAGNOSTIC (G3, 医師法 §17) is the load-bearing ceiling: this cell "
        "emits 兆候 + probabilistic attribution + consult ONLY — never a diagnosis."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class KizashiAttributionCell(PregelCell):
#     process_step = "kizashi_attribution"
#     pregel_tier = "B"
#     murakumo_node = "gad"
#
#     def super_step(self, msg, prior):
#         # NB: any attempt to populate a diagnosis/prescription field is a
#         # schema-level rejection (G3). Output carries confidence + disclaimer
#         # + consultRecommendation (G7) only.
#         raise NotImplementedError("kizashi R1")


__all__ = ["KizashiAttributionCell"]
