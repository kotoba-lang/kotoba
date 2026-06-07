"""akashi cross-platform link R0 scaffold.

Purpose:
    Link public ad disclosures by source IDs, advertiser names, landing domains,
    and creative hashes without adjudicating legality or intent.

ADR:
    ADR-2606022300

Constitutional ceiling:
    Non-adjudicating factual links only.
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
        "ratification before cross-platform link execution"
    )


class AkashiCrossPlatformLinkCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiCrossPlatformLinkCell"]
