"""Maturity helpers for constructing conformant ISO 20022 messages.

Small, well-tested conveniences that remove the two most common ways a
hand-built message fails CBPR+ conformance: a miscounted ``NbOfTxs`` and a
mismatched ``CtrlSum`` (both flagged by ``conformance.CBPR-001``/``008``).
Also a UETR generator so callers don't have to wire UUIDv4 themselves.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from .model import CreditTransferTransaction, GroupHeader, Party, SettlementMethod

__all__ = ("new_uetr", "control_sum_of", "pacs008_group_header", "pain001_group_header")


def new_uetr() -> str:
    """Generate a fresh CBPR+ UETR (lowercase UUIDv4)."""
    return str(uuid.uuid4())


def control_sum_of(transactions: Sequence[CreditTransferTransaction]) -> Decimal:
    """Sum the settlement (or instructed) amounts of ``transactions``.

    Uses ``interbank_amount`` when present (pacs.008), else
    ``instructed_amount`` (pain.001). Transactions with neither contribute
    zero. Mixed currencies are summed numerically as-is — callers should
    only pass a single-currency batch (CBPR+ CtrlSum is single-currency).
    """
    total = Decimal("0")
    for tx in transactions:
        amt = tx.interbank_amount or tx.instructed_amount
        if amt is not None:
            total += amt.value
    return total


def pacs008_group_header(
    message_id: str,
    creation_datetime: str,
    transactions: Sequence[CreditTransferTransaction],
    *,
    settlement_method: SettlementMethod = "CLRG",
) -> GroupHeader:
    """Build a pacs.008 ``GrpHdr`` with ``NbOfTxs``/``CtrlSum`` derived from
    the transactions, so the result satisfies CBPR-001 and CBPR-008."""
    return GroupHeader(
        message_id=message_id,
        creation_datetime=creation_datetime,
        number_of_txs=len(transactions),
        control_sum=control_sum_of(transactions),
        settlement_method=settlement_method,
    )


def pain001_group_header(
    message_id: str,
    creation_datetime: str,
    transactions: Sequence[CreditTransferTransaction],
    *,
    initiating_party: Party | None = None,
) -> GroupHeader:
    """Build a pain.001 ``GrpHdr`` with derived ``NbOfTxs``/``CtrlSum``."""
    return GroupHeader(
        message_id=message_id,
        creation_datetime=creation_datetime,
        number_of_txs=len(transactions),
        control_sum=control_sum_of(transactions),
        initiating_party=initiating_party,
    )
