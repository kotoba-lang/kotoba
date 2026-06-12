"""akashi creative normalization R0 scaffold.

Purpose:
    Normalize source-disclosed advertiser, creative, and delivery facts into
    kotoba records without inventing missing fields.

ADR:
    ADR-2606022300

Constitutional ceiling:
    No political profiling, no target lists, no private-person inference.
"""

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SOURCE_POLICY_REVIEW_TX: str | None = None
AKASHI_R1_ACTIVATION_TX: str | None = None

if not (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH
    and SOURCE_POLICY_REVIEW_TX
    and AKASHI_R1_ACTIVATION_TX
):
    raise RuntimeError(
        "akashi R0 scaffold: activate via Council ADR-2606022300 R1 "
        "ratification before creative normalization execution"
    )


class AkashiNormalizeCreativeCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiNormalizeCreativeCell"]
