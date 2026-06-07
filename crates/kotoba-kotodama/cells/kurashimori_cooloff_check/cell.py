"""KurashimoriCooloffCheckCell — kurashimori R0 Pregel cell.

Per ADR-2605312500 (暮らし守 kurashimori — citizen consumer-protection concierge).

Purpose: compute whether a member's contract is within a statutory cooling-off
window (contract date + type + the remedyTarget's 日数/起算 → deadline) →
`coolingOffAssessment`. An INFORMATIONAL date computation.

Constitutional ceiling (CRITICAL — IMMUTABLE): G5 — this is a DATE COMPUTATION,
explicitly NOT a legal opinion or rights-determination (coolingOffAssessment.
isLegalOpinion const false); borderline/complex cases route to chigiri +
licensed counsel. G8 non-fabrication (uses verified 日数 only; member confirms
input facts); G6 contract detail only in com.etzhayyim.encrypted.* (never
inline); Murakumo-only inference (ADR-2605215000).
Output Lexicon(s): com.etzhayyim.kurashimori.coolingOffAssessment.

R0 scaffold — import-time RuntimeError until R1. The PURE, tested computation
core already lands in the sibling module ``cooloff.py`` (importable WITHOUT this
gated wrapper); once Council ratifies (Lv6+ ≥3, post Bootstrap Council RFP
2026-06-19) ``super_step`` will call ``cooloff.compute_assessment`` /
``cooloff.to_assessment_record``. Landing that core does NOT activate this cell —
the activation gate below remains the sole switch.
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
MEMBER_CONSENT_SCHEMA_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or MEMBER_CONSENT_SCHEMA_REF is None
):
    raise RuntimeError(
        "kurashimori R0 scaffold: activate via Council ADR-2605312500 "
        "post-ratification — Council has not attested the kurashimori master "
        "charter (Lv6+ ≥3), and/or MEMBER_CONSENT_SCHEMA_REF is unset (the G3 "
        "consent binding). Do not deploy. INFORMATIONAL-DATE-COMPUTATION / "
        "NOT-A-LEGAL-OPINION (G5, isLegalOpinion const false) / "
        "NON-FABRICATION (G8) / PII-ENCRYPTED (G6) ceiling is constitutional."
    )


# from kotodama.organism import PregelCell
#
# class KurashimoriCooloffCheckCell(PregelCell):
#     process_step = "kurashimori_cooloff_check"
#     pregel_tier = "B"
#     murakumo_node = "reuben"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kurashimori R1")


__all__ = ["KurashimoriCooloffCheckCell"]
