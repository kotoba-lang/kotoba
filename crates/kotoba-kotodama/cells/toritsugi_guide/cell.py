"""ToritsugiGuideCell — toritsugi R0 Pregel cell.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge).

Purpose: pull the chigiri procedure template (ADR-2605262700) + the resolved
toritsugi.procedure and render a step-by-step 案内 + 必要書類 checklist into the
member's procedureGuide session. Guidance only.

Constitutional ceiling (CRITICAL — IMMUTABLE): G5 行政書士法 / UPL boundary —
toritsugi provides 情報提供 + 案内 + 伴走 only; it renders NO legal/tax advice
and performs NO 官公署提出書類の作成代理 reserved to 行政書士/弁護士/税理士
(characterization + 作成代理 + appeals route to chigiri + licensed counsel;
tax → toritate); G8 non-fabrication (cite 根拠法令 + provenance); Murakumo-only
inference (ADR-2605215000). Output Lexicon(s):
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
#   2. The chigiri procedure-template feed DID is registered (the only
#      permitted source of procedure templates; G5 UPL boundary).
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
CHIGIRI_TEMPLATE_FEED_DID: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or CHIGIRI_TEMPLATE_FEED_DID is None
):
    raise RuntimeError(
        "toritsugi R0 scaffold: activate via Council ADR-2605312030 "
        "post-ratification — Council has not attested the toritsugi master "
        "charter (Lv6+ ≥3), and/or CHIGIRI_TEMPLATE_FEED_DID is unset "
        "(the G5 procedure-template source). Do not deploy. "
        "行政書士法/UPL-BOUNDARY (G5, no advice + no 作成代理) / "
        "NON-FABRICATION (G8) ceiling is constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class ToritsugiGuideCell(PregelCell):
#     process_step = "toritsugi_guide"
#     pregel_tier = "B"
#     murakumo_node = "gad"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("toritsugi R1")


__all__ = ["ToritsugiGuideCell"]
