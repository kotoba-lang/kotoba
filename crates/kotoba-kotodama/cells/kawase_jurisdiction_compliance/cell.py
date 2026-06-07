"""
kawase_jurisdiction_compliance — G14 pre-flight gate per ADR-2605282200.

Pregel graph (R1 wiring):

    receive_send_preflight     → resolve_did_jurisdiction(sender)  →
    resolve_did_jurisdiction(recipient) → lookup_jurisdiction_attestation →
    if missing_or_expired: reject(JurisdictionNotActivated)        →
    else allow(send_intent) → forward_to_kawase_pool_match

Reads `jurisdictionAttestation` Lexicon records (Council Lv7+ unanimity
required per record) + chigiri.ipLicenseClaim cross-actor multi-juris
analysis. R1 jurisdictions activated by Founder seat 1 = USA + JPN; EU
+ UK + KOR + CHE unlock as Bootstrap Council Seats 2-5 close (RFP
2026-06-19).

Per ADR-2605282200 G14 the check happens BEFORE any on-chain dispatch
— the contract has no direct jurisdiction check; the Pregel cell is the
sole enforcement point.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        "kawase_jurisdiction_compliance cell scaffold-only — Council Lv7+ unanimity "
        "(5/5) per-jurisdiction attestation required before activation per "
        "ADR-2605282200 G14."
    )
