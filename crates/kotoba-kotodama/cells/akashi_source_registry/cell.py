"""akashi source registry R0 scaffold.

Purpose:
    Curate already-public advertising disclosure sources and emit
    com.etzhayyim.akashi.sourcePolicySnapshot records.

ADR:
    ADR-2606022300

Constitutional ceiling:
    Planning metadata only. This cell cannot authorize or run collection.
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
        "ratification before source registry execution"
    )


class AkashiSourceRegistryCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiSourceRegistryCell"]
