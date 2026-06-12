"""KizashiModalityRegistryCell — kizashi R0 Pregel cell.

Per ADR-2605312700 (兆 kizashi — non-invasive multimodal body-scan /
sign-sensing substrate). Cell §3 #6; Murakumo node `asher`.

Purpose: maintain the PUBLIC modality capability ledger — bind each sensing
modality to its declared evidenceGrade + regulatoryClass + canDetect /
cannotDetect + ionizing + phaseGate. Emits `com.etzhayyim.kizashi.modalityCapability`.
This is the G10 anti-pseudoscience gate: a modality not ledgered here with a
defensible evidence grade may NEVER emit a `modalityObservation`. Seed lives at
20-actors/kizashi/registry/modalities.seed.json (all `unverified-seed`).

Constitutional ceiling (CRITICAL — IMMUTABLE): G10 verified-modality-only
(bio-resonance / aura / 全身波動 / quantum scanners are grade-X EXCLUDED and may
never emit); G4 regulated/energy-emitting modalities are R3-gated to a
licensed-medical-device pathway; G9 ALARA (ionizing = referral, never routine
pod); Murakumo-only inference (ADR-2605215000). Activates FIRST among kizashi
cells (no observation can fire before the ledger gates it).
Output Lexicon(s): com.etzhayyim.kizashi.modalityCapability.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605312700 §7 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 ratify of ADR-2605312700.
#   2. The modalityCapability ledger is Council-attested (each entry's
#      evidenceGrade + regulatoryClass verified; G10).
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
MODALITY_LEDGER_COUNCIL_ATTESTATION_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or MODALITY_LEDGER_COUNCIL_ATTESTATION_REF is None
):
    raise RuntimeError(
        "kizashi R0 scaffold: activate via Council ADR-2605312700 "
        "post-ratification — Council has not attested the kizashi master charter "
        "(Lv6+ ≥3), and/or the modalityCapability ledger is not yet "
        "Council-attested (MODALITY_LEDGER_COUNCIL_ATTESTATION_REF unset; each "
        "modality's evidenceGrade + regulatoryClass must be verified per G10). "
        "Do not deploy. VERIFIED-MODALITY-ONLY / ANTI-PSEUDOSCIENCE (G10) ceiling "
        "is constitutional — grade-X entries (bio-resonance / aura / 波動) never emit."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class KizashiModalityRegistryCell(PregelCell):
#     process_step = "kizashi_modality_registry"
#     pregel_tier = "B"
#     murakumo_node = "asher"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kizashi R1")


__all__ = ["KizashiModalityRegistryCell"]
