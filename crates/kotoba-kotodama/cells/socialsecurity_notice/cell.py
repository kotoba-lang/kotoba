"""SocialSecurityNoticeCell - §1.16 Social Security pipeline R0 cell (Stage 3 NOTIFY).

Per ADR-2605302358 (§1.16 Social Security real-world delivery pipeline) +
ADR-2605172200 (openmail - atproto MST-native mail + SMTP bridge + on-chain postage).
Doctrine: ADR-2605302357.

Purpose: send a REAL email to a consented member via openmail: welcome + vow
confirmation (their CID + SBT id) + how to receive Level-0 in-kind benefits.
This is the concrete channel that reaches the human in their inbox.

Constitutional ceiling (CRITICAL - IMMUTABLE):
  - G5 OPT-IN + CONSENT-GATED + NON-VEXATIOUS: no unsolicited mass mail;
    unsubscribe always honored; rate-limited (no inbox/agency DoS).
  - G6 recipient PII only via com.etzhayyim.encrypted.* envelope (ADR-2605181100);
    never inline.
  - G3 NO PLATFORM-HELD MAIL KEY: member or community-operator DID signs
    (ADR-2605231525). On-chain postage (Postage.sol), Public-Fund-funded.
  - G11 LIVE-ACTION GATE: sent=false in R0 (no send) / R1 (dry-run to test
    addresses); real send only post Council Lv7+ §1.16 ratify, to consented members.
Output Lexicon(s): com.etzhayyim.socialsecurity.noticeEmail.

R0 scaffold - import-time RuntimeError until R2 (real email to consented members).
"""

from __future__ import annotations

COUNCIL_SS_IDENTITY_RATIFY_TX_HASH: str | None = None
OPENMAIL_POSTAGE_SIGNER_DID: str | None = None  # member / community-operator DID; never platform key

if (
    COUNCIL_SS_IDENTITY_RATIFY_TX_HASH is None
    or OPENMAIL_POSTAGE_SIGNER_DID is None
):
    raise RuntimeError(
        "socialsecurity_notice R0 scaffold: activate via Council ADR-2605302357 "
        "§3 identity-level ratify (Lv7+) + openmail postage signer DID "
        "(member/community-operator, ADR-2605172200 + 2605231525). Do not deploy. "
        "Mail is OPT-IN / NON-VEXATIOUS / unsubscribe-honored (G5), PII only in "
        "encrypted envelopes (G6), NO platform-held mail key (G3), sent=false "
        "until post-ratify (G11)."
    )


# from kotodama.organism import PregelCell
#
# class SocialSecurityNoticeCell(PregelCell):
#     process_step = "socialsecurity_notice"
#     pregel_tier = "B"
#     murakumo_node = "naphtali"
#
#     def super_step(self, msg, prior):
#         # 1. confirm opt-in consent (no unsolicited mail); check unsubscribe state
#         # 2. resolve recipient PII via encrypted envelope ref (never inline)
#         # 3. send via openmail (member/operator-signed; on-chain postage)
#         # 4. emit com.etzhayyim.socialsecurity.noticeEmail (sent=false R0/R1)
#         raise NotImplementedError("socialsecurity_notice R2")


__all__ = ["SocialSecurityNoticeCell"]
