"""MoushibumiVoterInfoCell — moushibumi R0 Pregel cell.

Per ADR-2605312400 (申文 moushibumi — citizen democratic-participation concierge).

Purpose: serve NEUTRAL election-mechanics information — voting dates, 期日前投票 /
不在者投票 procedure, pointers to the official 選挙公報 — so a member can
participate as an informed citizen.

Constitutional ceiling (CRITICAL — IMMUTABLE): G3 公職選挙法 + political-
neutrality — INFO ONLY; NO campaigning / canvassing (§138 戸別訪問) / candidate
or party endorsement / ranking / vote solicitation / GOTV targeting / partisan
steering; neutral reference to official sources only (protects §1.12 / 1 SBT =
1 vote). G8 non-fabrication; Murakumo-only inference (ADR-2605215000).
Output: read-side info only (no member-mutating Lexicon).

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
ELECTION_INFO_SOURCE_DID: str | None = None  # official 総務省/選管 source feed

if (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH is None
    or ELECTION_INFO_SOURCE_DID is None
):
    raise RuntimeError(
        "moushibumi R0 scaffold: activate via Council ADR-2605312400 "
        "post-ratification — Council has not attested the moushibumi master "
        "charter (Lv6+ ≥3), and/or ELECTION_INFO_SOURCE_DID is unset (the "
        "official 総務省/選管 info source). Do not deploy. 公職選挙法/"
        "POLITICAL-NEUTRALITY (G3, INFO-ONLY, no campaigning) / NON-FABRICATION "
        "(G8) ceiling is constitutional."
    )


# from kotodama.organism import PregelCell
#
# class MoushibumiVoterInfoCell(PregelCell):
#     process_step = "moushibumi_voter_info"
#     pregel_tier = "B"
#     murakumo_node = "reuben"
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("moushibumi R1")


__all__ = ["MoushibumiVoterInfoCell"]
