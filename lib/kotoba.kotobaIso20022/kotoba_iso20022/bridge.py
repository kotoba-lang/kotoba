"""Bridge: ISO 20022 message → kawase-yui ``ingressAttestation`` records.

This is the actor-integration glue. The codec parses the open ISO 20022
wire; :mod:`kotoba_iso20022.datoms` lands it as EAVT facts; this module
shapes the same value-events into ``com.etzhayyim.iso20022.ingressAttestation``
AT-Protocol records (the Lexicon at
``00-contracts/lexicons/com/etzhayyim/iso20022/``) so a kawase corridor can
attest an external bank transfer and, where it corresponds to an on-chain
on-ramp, reconcile it against a ``com.etzhayyim.kawase.depositAttestation``
via ``linkedDepositCid``.

PII discipline (kawase-yui G10): party names are 要配慮 PII and are omitted
by default; ``include_party_names=True`` is opt-in and intended only for a
consent-bound / encrypted path. Only institution BICs (ISO 9362) are
first-class. This module produces records; it does not transact, sign, or
move money (kawase G2/G13 stay with the gated ingress cell).
"""

from __future__ import annotations

from .datoms import tx_entity_of
from .model import (
    BankToCustomerDebitCreditNotification,
    BankToCustomerStatement,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    FIToFICustomerCreditTransfer,
    StatementEntry,
)

__all__ = ("ingress_attestations", "RECORD_TYPE", "LEXICON_VERSION", "ValueBearingMessage")

# The message kinds that carry a settlement value-event (vs. a status report).
ValueBearingMessage = (
    CustomerCreditTransferInitiation
    | FIToFICustomerCreditTransfer
    | BankToCustomerStatement
    | BankToCustomerDebitCreditNotification
)
Record = dict[str, object]

RECORD_TYPE = "com.etzhayyim.iso20022.ingressAttestation"
LEXICON_VERSION = 1

# Source message → the `reportedBy` family token recorded on each record.
_REPORTED_BY = {
    CustomerCreditTransferInitiation: "pain.001",
    FIToFICustomerCreditTransfer: "pacs.008",
    BankToCustomerStatement: "camt.053",
    BankToCustomerDebitCreditNotification: "camt.054",
}


def _base_record(
    *,
    message_definition: str,
    message_id: str,
    end_to_end_id: str,
    tx_entity: str,
    amount: str,
    currency: str,
    reported_by: str,
    ingested_at: str,
    uetr: str | None = None,
    cbpr_conformant: bool | None = None,
    linked_deposit_cid: str | None = None,
    datom_count: int | None = None,
) -> Record:
    rec: Record = {
        "$type": RECORD_TYPE,
        "v": LEXICON_VERSION,
        "messageDefinition": message_definition,
        "messageId": message_id,
        "endToEndId": end_to_end_id,
        "txEntity": tx_entity,
        "amount": amount,
        "currency": currency,
        "reportedBy": reported_by,
        "ingestedAt": ingested_at,
    }
    if uetr:
        rec["uetr"] = uetr
    if cbpr_conformant is not None:
        rec["cbprConformant"] = cbpr_conformant
    if linked_deposit_cid:
        rec["linkedDepositCid"] = linked_deposit_cid
    if datom_count is not None:
        rec["datomCount"] = datom_count
    return rec


def _from_transaction(
    tx: CreditTransferTransaction,
    *,
    message_definition: str,
    message_id: str,
    reported_by: str,
    ingested_at: str,
    include_party_names: bool,
    cbpr_conformant: bool | None,
    linked_deposit_cid: str | None,
) -> Record | None:
    amt = tx.interbank_amount or tx.instructed_amount
    if amt is None:
        return None
    rec = _base_record(
        message_definition=message_definition,
        message_id=message_id,
        end_to_end_id=tx.end_to_end_id,
        tx_entity=tx_entity_of(tx),
        amount=str(amt.value),
        currency=amt.currency,
        reported_by=reported_by,
        ingested_at=ingested_at,
        uetr=tx.uetr,
        cbpr_conformant=cbpr_conformant,
        linked_deposit_cid=linked_deposit_cid,
    )
    if tx.debtor_agent and tx.debtor_agent.bicfi:
        rec["debtorAgentBic"] = tx.debtor_agent.bicfi
    if tx.creditor_agent and tx.creditor_agent.bicfi:
        rec["creditorAgentBic"] = tx.creditor_agent.bicfi
    if include_party_names:
        if tx.debtor and tx.debtor.name:
            rec["debtorName"] = tx.debtor.name
        if tx.creditor and tx.creditor.name:
            rec["creditorName"] = tx.creditor.name
    return rec


def _from_entry(
    entry: StatementEntry,
    *,
    message_definition: str,
    message_id: str,
    reported_by: str,
    ingested_at: str,
    cbpr_conformant: bool | None,
    linked_deposit_cid: str | None,
) -> Record | None:
    ref = entry.end_to_end_id or entry.account_servicer_reference
    if ref is None:
        return None
    rec = _base_record(
        message_definition=message_definition,
        message_id=message_id,
        end_to_end_id=entry.end_to_end_id or ref,
        tx_entity=f"com.etzhayyim.iso20022/tx:{ref}",
        amount=str(entry.amount.value),
        currency=entry.amount.currency,
        reported_by=reported_by,
        ingested_at=ingested_at,
        cbpr_conformant=cbpr_conformant,
        linked_deposit_cid=linked_deposit_cid,
    )
    rec["creditDebit"] = entry.credit_debit
    rec["status"] = entry.status
    return rec


def ingress_attestations(
    msg: ValueBearingMessage,
    *,
    ingested_at: str,
    message_definition: str | None = None,
    include_party_names: bool = False,
    cbpr_conformant: bool | None = None,
    linked_deposit_cid: str | None = None,
) -> list[Record]:
    """Map a value-bearing ISO 20022 message to ``ingressAttestation`` records.

    One record per transaction (pain.001 / pacs.008) or per entry
    (camt.053 / camt.054). ``message_definition`` defaults to the codec's
    default version for the message type. Records validate against the
    ``com.etzhayyim.iso20022.ingressAttestation`` Lexicon.

    Raises :class:`TypeError` for status-only messages (pacs.002 / pain.002),
    whose status is carried by :func:`kotoba_iso20022.to_datoms` instead.
    """
    from .codec import DEFAULT_VERSIONS

    reported_by = _REPORTED_BY.get(type(msg))
    if reported_by is None:
        raise TypeError(
            f"{type(msg).__name__} is not a value-bearing message; "
            "status reports carry status via to_datoms()"
        )
    msgdef = message_definition or DEFAULT_VERSIONS[reported_by]
    mid = msg.group_header.message_id
    out: list[Record] = []

    if isinstance(msg, CustomerCreditTransferInitiation):
        txs = [tx for pmt in msg.payments for tx in pmt.transactions]
        for tx in txs:
            rec = _from_transaction(
                tx, message_definition=msgdef, message_id=mid, reported_by=reported_by,
                ingested_at=ingested_at, include_party_names=include_party_names,
                cbpr_conformant=cbpr_conformant, linked_deposit_cid=linked_deposit_cid,
            )
            if rec:
                out.append(rec)
    elif isinstance(msg, FIToFICustomerCreditTransfer):
        for tx in msg.transactions:
            rec = _from_transaction(
                tx, message_definition=msgdef, message_id=mid, reported_by=reported_by,
                ingested_at=ingested_at, include_party_names=include_party_names,
                cbpr_conformant=cbpr_conformant, linked_deposit_cid=linked_deposit_cid,
            )
            if rec:
                out.append(rec)
    elif isinstance(msg, BankToCustomerStatement):
        for stmt in msg.statements:
            for entry in stmt.entries:
                rec = _from_entry(
                    entry, message_definition=msgdef, message_id=mid,
                    reported_by=reported_by, ingested_at=ingested_at,
                    cbpr_conformant=cbpr_conformant, linked_deposit_cid=linked_deposit_cid,
                )
                if rec:
                    out.append(rec)
    elif isinstance(msg, BankToCustomerDebitCreditNotification):
        for ntf in msg.notifications:
            for entry in ntf.entries:
                rec = _from_entry(
                    entry, message_definition=msgdef, message_id=mid,
                    reported_by=reported_by, ingested_at=ingested_at,
                    cbpr_conformant=cbpr_conformant, linked_deposit_cid=linked_deposit_cid,
                )
                if rec:
                    out.append(rec)

    return out
