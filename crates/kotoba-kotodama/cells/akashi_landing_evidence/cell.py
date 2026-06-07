"""akashi landing evidence R0 scaffold.

Purpose:
    Preserve disclosed landing URL/domain/redirect/hash evidence from public ad
    disclosures.

ADR:
    ADR-2606022300

Constitutional ceiling:
    Rate-limited public evidence only; no covert browsing or tracking.
"""

COUNCIL_CHARTER_ATTESTATION_TX_HASH: str | None = None
SOURCE_POLICY_REVIEW_TX: str | None = None
LANDING_FETCH_RATE_LIMIT_REVIEW_TX: str | None = None
AKASHI_R1_ACTIVATION_TX: str | None = None

if not (
    COUNCIL_CHARTER_ATTESTATION_TX_HASH
    and SOURCE_POLICY_REVIEW_TX
    and LANDING_FETCH_RATE_LIMIT_REVIEW_TX
    and AKASHI_R1_ACTIVATION_TX
):
    raise RuntimeError(
        "akashi R0 scaffold: activate via Council ADR-2606022300 R1 "
        "ratification before landing evidence execution"
    )


class AkashiLandingEvidenceCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiLandingEvidenceCell"]
