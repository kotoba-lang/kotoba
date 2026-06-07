"""KurashimoriSendCell — kurashimori R0 Pregel cell.

Per ADR-2605312500 (暮らし守 kurashimori — citizen consumer-protection concierge).

Purpose: THE ONLY active-outbound cell. Default hands the remedyDraft back to the
member for self-send (mode=member-self-send). The 代行 (mode=agent-on-behalf)
path — sending the member's OWN notice via a lawful channel — is the GATED R3
exception and is OFF until the R3 gate is satisfied. Emits `dispatchRecord`.

Constitutional ceiling (CRITICAL — IMMUTABLE): G10 lawful-channel-only + non-
harassment (lawful, proportionate communication via a legitimate channel with
member authorization; never threats / 威迫); G14 verified-remedy-only; G15
member-self-action default (代行 requires per-submission consent + 司法書士法/
行政書士法 clearance + Council Lv7+); no platform-held signing key
(ADR-2605231525); Murakumo-only (ADR-2605215000).
Output Lexicon(s): com.etzhayyim.kurashimori.dispatchRecord.

R0 scaffold — import-time RuntimeError until R2 (self-send) / R3 (代行).
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SELF_SEND_PUBLIC_COMMENT_TX: str | None = None
DAIKOU_R3_GATE_TX: str | None = None  # Council Lv7+ + 司法書士法/行政書士法 clearance (G15)

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or SELF_SEND_PUBLIC_COMMENT_TX is None
    or DAIKOU_R3_GATE_TX is None
):
    raise RuntimeError(
        "kurashimori R0 scaffold: activate via Council ADR-2605312500 "
        "post-ratification — the active-outbound send cell stays disabled "
        "until R2 (Council Lv6+ ≥4 + 30-day public comment) for "
        "member-self-send, and 代行 (agent-on-behalf) ADDITIONALLY requires the "
        "R3 gate (Council Lv7+ unanimity + 司法書士法/行政書士法 clearance, "
        "DAIKOU_R3_GATE_TX). Do not deploy. LAWFUL-CHANNEL-ONLY + "
        "NON-HARASSMENT (G10) / VERIFIED-REMEDY-ONLY (G14) / SELF-SEND-DEFAULT "
        "(G15) / NO-PLATFORM-HELD-KEY (ADR-2605231525) ceiling is constitutional."
    )


# from kotodama.organism import PregelCell
#
# class KurashimoriSendCell(PregelCell):
#     process_step = "kurashimori_send"
#     pregel_tier = "B"
#     murakumo_node = "naphtali"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("kurashimori R2/R3")


__all__ = ["KurashimoriSendCell"]
