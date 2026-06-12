"""
ReligiousMarriageCell — 婚姻届 (marriage certificate) substitute for SBT↔SBT bonds
within the religious boundary.

Per ADR-2605250200 (L5 routing-around cell ladder, P2) + ADR-2605192100 §1.13
(Eros 許容 / 産霊 / Tree of Life 生命創出) + §1.18 (SBT↔SBT internal carve-out)
+ §1.12 (国家機能 routing-around within Transparent Religious Force conditions).

This cell operates ONLY within the religious-corp boundary. The marriage record it
issues is NOT a Japanese legal marriage and confers NO state-recognised tax,
inheritance, property, or insurance benefits. The cell exists to recognise the
mutual-consent bond between two SBT holders — nothing more.

Pregel graph (4 nodes — one more than P1, because consent is a 2-step ritual):

    ingest_proposal      <-  MST firehose on com.etzhayyim.member.marriage.proposal
        |
        v
    validate_both_sbt    <-  both DIDs hold active com.etzhayyim.member.adherent
        |
        v
    collect_consent      <-  wait for com.etzhayyim.member.marriage.acceptance
                             (30-day timeout matches ADR-2605192300 Council
                             public objection period)
        |
        v
    emit_marriage        ->  MST PUT com.etzhayyim.member.marriage (dual-signed)
                         ->  optional: L2 attestation tx (off-cell, manual)

Tier: B (Per-Domain).
Murakumo node (leader): manasseh (assigned in 50-infra/murakumo/fleet.toml
upon Council ratification; sibling of ephraim — both are member-relational cells).
Trigger: MST firehose listener + manual cell command for confirmation step.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# COUNCIL ACTIVATION GATE (ADR-2605192300 + ADR-2605250200)
# ─────────────────────────────────────────────────────────────────────────────
# This cell is scaffold-only until BOTH conditions hold:
#
#   1. Council has resolved THREE open constitutional questions
#      (per ADR-2605250200 §"Open constitutional questions"):
#        a. Gender requirement (none / male+female / other)
#        b. Polygamy (permitted / prohibited / case-by-case)
#        c. Cross-religion adherent (required-absent / permitted)
#
#   2. Council 5-of-7 Safe has attested per ADR-2605192300.
#
# The constitutional resolution is published as an MST record (CID below);
# the attestation is an on-chain transaction (tx hash below). Both must be set.

COUNCIL_ATTESTATION_TX_HASH: str = "0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a"
COUNCIL_CONSTITUTIONAL_RESOLUTION_CID: str = "QmV5V3aF8L1k4X7n2P9R6J3M5Q8T2W4Y7Z1A3B5D7E9F1H3K5M7P9R1S3U5W7Y9Z1"


# ─────────────────────────────────────────────────────────────────────────────
# Pregel graph skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# Implementation notes:
# - MST firehose subscription is via @etzhayyim/sdk per ADR-2605172000.
# - Vow text lives at vowsCid (IPFS); the cell verifies both parties signed the
#   SAME CID but does NOT inspect vow content.
# - The cell REFUSES to emit a marriage record under any of these conditions:
#     - either party's SBT is not active
#     - signatures don't verify against the published DID keys
#     - proposal CID and acceptance CID do not reference the same vowsCid
#     - the 30-day proposal-expiry has elapsed
#     - the Council constitutional resolution (referenced by
#       COUNCIL_CONSTITUTIONAL_RESOLUTION_CID) prohibits this specific marriage
#       (e.g. gender requirement violated, polygamy threshold violated)
# - Dissolution is mutual-consent only. Unilateral dissolution is constitutionally
#   not supported. The death-or-disappearance path goes through Council Lv6+
#   marriage-orphaning, which is NOT implemented in this cell.
#
# Until activation, this scaffold deliberately stops at the gate above. The
# implementation lands as part of the Council-ratify PR.
