"""akashi disclosure fetch R0 scaffold.

Purpose:
    Fetch already-public platform disclosure pages, APIs, or bulk exports and
    emit com.etzhayyim.akashi.adDisclosureSnapshot records.

ADR:
    ADR-2606022300

Constitutional ceiling:
    No login, sockpuppet account, anti-bot bypass, or live fetch in R0.
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
        "ratification before disclosure fetch execution"
    )


class AkashiDisclosureFetchCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiDisclosureFetchCell"]
