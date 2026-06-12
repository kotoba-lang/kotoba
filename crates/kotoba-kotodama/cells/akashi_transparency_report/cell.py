"""akashi transparency report R0 scaffold.

Purpose:
    Produce aggregate, source-cited public ad transparency reports.

ADR:
    ADR-2606022300

Constitutional ceiling:
    Aggregate reporting only; no commercial ad-intel or target-list product.
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
        "ratification before transparency report execution"
    )


class AkashiTransparencyReportCell:
    """Reserved R1 cell; intentionally unreachable while R0 gates are unset."""


__all__ = ["AkashiTransparencyReportCell"]
