"""ToritsugiSubmitCell — toritsugi R0 Pregel cell.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge).

Purpose: THE ONLY active-outbound cell. Default mode hands the applicationDraft
back to the member for self-submission (mode=member-self-submit). The 代行
(mode=agent-on-behalf) path — filing the member's OWN procedure via the official
channel — is the GATED R3 exception and is OFF until the R3 gate is satisfied.
Emits `com.etzhayyim.toritsugi.submissionRecord`.

Constitutional ceiling (CRITICAL — IMMUTABLE): G10 lawful-channel-only (the only
external mutation is a lawful submission via an OFFICIAL channel with member
authorization; never unauthorized access / circumvention); G14
verified-procedure-only (refuse unverified-seed / stale procedures); G15
member-self-submission default (代行 requires per-submission consent +
行政書士法 clearance + Council Lv7+ — `councilGateRef`); no platform-held
signing key (ADR-2605231525; member/community-operator-signed); Murakumo-only
inference (ADR-2605215000). Output Lexicon(s):
com.etzhayyim.toritsugi.submissionRecord.

R0 scaffold — import-time RuntimeError until R2 (self-submit) / R3 (代行).
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R2/R3 activation gate (ADR-2605312030 §8 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# This is the highest-gated cell. Scaffold-only until ALL hold:
#
#   1. Council Lv6+ ≥4 + 30-day public comment for R2 (member-self-submit:
#      toritsugi assembles + hands back, the member files).
#   2. For mode=agent-on-behalf (代行, R3): ADDITIONALLY a Council Lv7+
#      unanimity gate AND a 行政書士法 clearance reference must exist on-chain
#      (G15). Until then DAIKOU_R3_GATE_TX stays None and agent-on-behalf is
#      structurally unreachable.
#   3. The submission targets a council-verified / maintainer-verified
#      procedure only (G14) — enforced at run time against the procedure entry.
#
# Any None below → import-time RuntimeError. DAIKOU_R3_GATE_TX is listed last so
# that even after R2 self-submit is enabled, 代行 stays gated.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SELF_SUBMIT_PUBLIC_COMMENT_TX: str | None = None
DAIKOU_R3_GATE_TX: str | None = None  # Council Lv7+ + 行政書士法 clearance (G15)

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or SELF_SUBMIT_PUBLIC_COMMENT_TX is None
    or DAIKOU_R3_GATE_TX is None
):
    raise RuntimeError(
        "toritsugi R0 scaffold: activate via Council ADR-2605312030 "
        "post-ratification — the active-outbound submit cell stays disabled "
        "until R2 (Council Lv6+ ≥4 + 30-day public comment) for "
        "member-self-submit, and 代行 (agent-on-behalf) ADDITIONALLY requires "
        "the R3 gate (Council Lv7+ unanimity + 行政書士法 clearance, "
        "DAIKOU_R3_GATE_TX). Do not deploy. LAWFUL-CHANNEL-ONLY (G10) / "
        "VERIFIED-PROCEDURE-ONLY (G14) / SELF-SUBMIT-DEFAULT (G15) / "
        "NO-PLATFORM-HELD-KEY (ADR-2605231525) ceiling is constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the gates are removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class ToritsugiSubmitCell(PregelCell):
#     process_step = "toritsugi_submit"
#     pregel_tier = "B"
#     murakumo_node = "naphtali"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("toritsugi R2/R3")


__all__ = ["ToritsugiSubmitCell"]
