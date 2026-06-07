"""ToritsugiDraftCell — toritsugi R0 Pregel cell.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge).

Purpose: assist the member in filling the 様式/フォーム for a procedure and emit
an `com.etzhayyim.toritsugi.applicationDraft` artifact the member reviews + owns.
This is INPUT-ASSISTANCE, not 作成代理.

Constitutional ceiling (CRITICAL — IMMUTABLE): G5 行政書士法 / UPL boundary —
input-assist only, NEVER 官公署提出書類の作成代理 (the only representable
`assistMode` is "input-assist"); G6 the draft's PII content lands ONLY in an
com.etzhayyim.encrypted.* DID-bound envelope (ADR-2605181100; never inline PII);
G8 the member must confirm (`memberConfirmed`) before any submission;
Murakumo-only inference (ADR-2605215000). Output Lexicon(s):
com.etzhayyim.toritsugi.applicationDraft.

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605312030 §8 "Roadmap")
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 multisig has attested ADR-2605312030.
#   2. The encrypted-records envelope backend is live (G6 — drafts carry PII
#      and must never land in plaintext on MST).
#
# Any None below → import-time RuntimeError.

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
ENCRYPTED_ENVELOPE_BACKEND_REF: str | None = None

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or ENCRYPTED_ENVELOPE_BACKEND_REF is None
):
    raise RuntimeError(
        "toritsugi R0 scaffold: activate via Council ADR-2605312030 "
        "post-ratification — Council has not attested the toritsugi master "
        "charter (Lv6+ ≥3), and/or ENCRYPTED_ENVELOPE_BACKEND_REF is unset "
        "(the G6 PII envelope backend, ADR-2605181100). Do not deploy. "
        "INPUT-ASSIST-ONLY / NO-作成代理 (G5) / PII-ENCRYPTED (G6) / "
        "MEMBER-CONFIRMS (G8) ceiling is constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class ToritsugiDraftCell(PregelCell):
#     process_step = "toritsugi_draft"
#     pregel_tier = "B"
#     murakumo_node = "gad"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("toritsugi R1")


__all__ = ["ToritsugiDraftCell"]
