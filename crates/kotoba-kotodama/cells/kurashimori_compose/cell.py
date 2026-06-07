"""KurashimoriComposeCell — kurashimori R0 Pregel cell.

Per ADR-2605312500 (暮らし守 kurashimori — citizen consumer-protection concierge).

Purpose: pull the chigiri template + resolved remedyTarget and help the member
draft a cooling-off 通知 / refund demand / complaint → `remedyDraft`. Drafting-
assistance only.

Constitutional ceiling (CRITICAL — IMMUTABLE): G5 UPL/司法書士法 — drafting-assist
only, NEVER 作成代理 (the only representable assistMode is 'drafting-assist');
G10 the draft uses lawful, non-threatening language (no 威迫); G6 the draft lands
ONLY in an com.etzhayyim.encrypted.* DID-bound envelope (never inline); G8 the
member must confirm before send; Murakumo-only inference (ADR-2605215000).
Output Lexicon(s): com.etzhayyim.kurashimori.remedyDraft.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
CHIGIRI_TEMPLATE_FEED_DID: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or CHIGIRI_TEMPLATE_FEED_DID is None
):
    raise RuntimeError(
        "kurashimori R0 scaffold: activate via Council ADR-2605312500 "
        "post-ratification — Council has not attested the kurashimori master "
        "charter (Lv6+ ≥3), and/or CHIGIRI_TEMPLATE_FEED_DID is unset (the G5 "
        "template source). Do not deploy. DRAFTING-ASSIST-ONLY / NO-作成代理 "
        "(G5) / LAWFUL-NON-HARASSMENT (G10) / PII-ENCRYPTED (G6) / "
        "MEMBER-CONFIRMS (G8) ceiling is constitutional."
    )


# from kotodama.organism import PregelCell
#
# class KurashimoriComposeCell(PregelCell):
#     process_step = "kurashimori_compose"
#     pregel_tier = "B"
#     murakumo_node = "gad"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kurashimori R1")


__all__ = ["KurashimoriComposeCell"]
