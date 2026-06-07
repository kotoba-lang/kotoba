"""KizashiScanSessionCell — kizashi R0 Pregel cell.

Per ADR-2605312700 (兆 kizashi). Cell §3 #1; Murakumo node `naphtali`.

Purpose: orchestrate a non-invasive multimodal scan session — verify per-scan
consent, drive per-modality capture (R0..R2: non-ionizing non-regulated only),
emit the encrypted session attestation. Emits
`com.etzhayyim.kizashi.scanSessionAttestation`.

Constitutional ceiling (CRITICAL — IMMUTABLE): G2 biometric scan = 要配慮 PII,
encrypted envelope MANDATORY (ADR-2605181100), 30-day rotating pseudonym DID
(ADR-2605181200; N10 — not an identity database); G6 per-scan consent
(default-deny, revocable; minors via guardian + hagukumi); G4 R0..R2 admit only
non-ionizing non-regulated modalities (regulated = R3 licensed pathway);
G11 real member scans require Council + licensed oversight + R3.
Output Lexicon(s): com.etzhayyim.kizashi.scanSessionAttestation.

R0 scaffold — import-time RuntimeError until R2.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R2 activation gate (ADR-2605312700 §7 "Roadmap" — scan_session ships R2)
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥4 + 30-day public objection (scan_session ships with R2).
#   2. The encrypted-records envelope backend is live (G2).
#   3. A medical-device regulatory-pathway assessment is filed (G4) and a
#      ≥20-participant consented research protocol is Council-reviewed.
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
ENCRYPTED_ENVELOPE_BACKEND_REF: str | None = None
MEDICAL_DEVICE_PATHWAY_ASSESSMENT_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or ENCRYPTED_ENVELOPE_BACKEND_REF is None
    or MEDICAL_DEVICE_PATHWAY_ASSESSMENT_REF is None
):
    raise RuntimeError(
        "kizashi R0 scaffold: activate via Council ADR-2605312700 "
        "post-ratification — Council charter unattested (Lv6+ ≥4 + public, R2), "
        "and/or ENCRYPTED_ENVELOPE_BACKEND_REF unset (G2 biometric PII), and/or "
        "MEDICAL_DEVICE_PATHWAY_ASSESSMENT_REF unset (G4 — required before any "
        "real capture). Do not deploy. NO HARDWARE exists at R0/R1; "
        "ENCRYPTED-ENVELOPE (G2) + CONSENT (G6) + DEVICE-BOUNDARY (G4) ceiling "
        "is constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class KizashiScanSessionCell(PregelCell):
#     process_step = "kizashi_scan_session"
#     pregel_tier = "B"
#     murakumo_node = "naphtali"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kizashi R2")


__all__ = ["KizashiScanSessionCell"]
