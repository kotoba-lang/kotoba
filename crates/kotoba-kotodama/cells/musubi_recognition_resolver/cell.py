"""MusubiRecognitionResolverCell — musubi R0 Pregel cell.

Per ADR-2605263400 (結 musubi — covenant-ceremony Tier-B actor).

Purpose: given a member's jurisdiction (+ optional ceremony-type label e.g.
marriage / naming / funeral), ROUTE to the registry's INFORMATIONAL ceremony-
recognition entries — which map whether a SEPARATE civil-registration step is
required and what it is → `ceremonyRecognition`. A PURE registry query.

Constitutional boundary (CRITICAL — IMMUTABLE): musubi performs covenant
ceremonies (Reformed 万人祭司 — NO clergy class, no officiant authority) and DOES
NOT confer civil status. This cell is INFORMATIONAL routing only — it surfaces
where a separate civil step must be performed by the member themselves; it gives
NO legal advice, NO eligibility / means-test / rights determination, and NEVER
claims to register a civil marriage. ceremonyRecognition.isLegalOpinion const
false AND ceremonyRecognition.confersCivilStatus const false (no code path to
True). G8 non-fabrication (uses the registry's cited legalBasis + provenance
only; unknown jurisdiction → empty, never a guess); Murakumo-only inference
(ADR-2605215000).
Output Lexicon(s): com.etzhayyim.musubi.ceremonyRecognition.

R0 scaffold — import-time RuntimeError until R1. The PURE, tested resolver core
already lands in the sibling module ``recognition_resolver.py`` (importable
WITHOUT this gated wrapper); once Council ratifies (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19) ``super_step`` will call
``recognition_resolver.resolve_recognitions`` /
``recognition_resolver.to_recognition_routing_record``. Landing that core does
NOT activate this cell — the activation gate below remains the sole switch.
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
MEMBER_CONSENT_SCHEMA_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or MEMBER_CONSENT_SCHEMA_REF is None
):
    raise RuntimeError(
        "musubi R0 scaffold: activate via Council ADR-2605263400 "
        "post-ratification — Council has not attested the musubi master "
        "charter (Lv6+ ≥3), and/or MEMBER_CONSENT_SCHEMA_REF is unset (the "
        "consent binding). Do not deploy. INFORMATIONAL-RECOGNITION-ROUTING / "
        "NOT-A-LEGAL-OPINION (isLegalOpinion const false) / "
        "DOES-NOT-CONFER-CIVIL-STATUS (confersCivilStatus const false; musubi "
        "performs covenant ceremonies, Reformed 万人祭司, NO clergy class) / "
        "NON-FABRICATION (G8) ceiling is constitutional."
    )


# from kotodama.organism import PregelCell
#
# class MusubiRecognitionResolverCell(PregelCell):
#     process_step = "musubi_recognition_resolver"
#     pregel_tier = "B"
#     murakumo_node = "reuben"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("musubi R1")


__all__ = ["MusubiRecognitionResolverCell"]
