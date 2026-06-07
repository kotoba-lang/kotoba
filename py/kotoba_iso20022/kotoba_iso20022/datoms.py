"""ISO 20022 message → kotoba EAVT Datom mapping (ingress/interop wire).

Per CLAUDE.md the kotoba Datom log is first-class canonical state and the
AT-Protocol MST is "ingress/interop wire". This module is the *traditional
finance* analogue of that wire: it lands an inbound ISO 20022 message as a
set of append-only EAVT facts so a real-world bank transfer becomes
auditable kotoba history (Wellbecoming ``as-of``, no mutation, no deletion).

A Datom here is the 4-tuple ``(entity, attribute, value, op)`` with ``op``
always ``True`` (assertion) — retraction is never emitted for an ingress
record, mirroring kawase-yui G11 (no reverse / no unwind). Entities are
content-addressable handles derived from the message's own immutable
identifiers (UETR / EndToEndId / MsgId), NOT random ids, so re-ingesting
the same message is idempotent.

This is pure mapping: it does not write to kotoba, touch a chain, or move
money. The caller (a kawase-yui ingress cell, gated) is responsible for
the actual transact under G2/G13.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    BankToCustomerDebitCreditNotification,
    BankToCustomerStatement,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    FIToFICustomerCreditTransfer,
    FIToFIPaymentStatusReport,
    PaymentReturn,
    StatementEntry,
)

__all__ = ("Datom", "NS", "to_datoms", "tx_entity_of")

NS = "com.etzhayyim.iso20022"


def tx_entity_of(tx: CreditTransferTransaction) -> str:
    """Public content-addressable entity handle for a transaction.

    Keyed on the most stable immutable reference (UETR → TxId →
    EndToEndId), so the same transaction always maps to the same kotoba
    entity across pain.001 / pacs.008 / camt ingress and pacs.002 status.
    """
    ref = tx.uetr or tx.tx_id or tx.end_to_end_id
    return f"{NS}/tx:{ref}"

AnyMessage = (
    CustomerCreditTransferInitiation
    | FIToFICustomerCreditTransfer
    | FIToFIPaymentStatusReport
    | BankToCustomerStatement
    | BankToCustomerDebitCreditNotification
    | PaymentReturn
)


@dataclass(frozen=True)
class Datom:
    """A single append-only EAVT assertion."""

    entity: str
    attribute: str
    value: str
    op: bool = True  # assertion; ingress never retracts (kawase-yui G11)

    def as_tuple(self) -> tuple[str, str, str, bool]:
        return (self.entity, self.attribute, self.value, self.op)


def _tx_entity(tx: CreditTransferTransaction) -> str:
    """Stable content-addressable entity handle for a transaction."""
    return tx_entity_of(tx)


def _tx_datoms(entity: str, tx: CreditTransferTransaction) -> list[Datom]:
    out: list[Datom] = [Datom(entity, f"{NS}.tx/endToEndId", tx.end_to_end_id)]
    if tx.uetr:
        out.append(Datom(entity, f"{NS}.tx/uetr", tx.uetr))
    if tx.tx_id:
        out.append(Datom(entity, f"{NS}.tx/txId", tx.tx_id))
    amt = tx.interbank_amount or tx.instructed_amount
    if amt is not None:
        out.append(Datom(entity, f"{NS}.tx/amount", str(amt.value)))
        out.append(Datom(entity, f"{NS}.tx/currency", amt.currency))
    if tx.interbank_settlement_date:
        out.append(Datom(entity, f"{NS}.tx/settlementDate", tx.interbank_settlement_date))
    if tx.charge_bearer:
        out.append(Datom(entity, f"{NS}.tx/chargeBearer", tx.charge_bearer))
    if tx.debtor:
        out.append(Datom(entity, f"{NS}.tx/debtorName", tx.debtor.name))
    if tx.debtor_account and tx.debtor_account.iban:
        out.append(Datom(entity, f"{NS}.tx/debtorIban", tx.debtor_account.iban))
    if tx.debtor_agent and tx.debtor_agent.bicfi:
        out.append(Datom(entity, f"{NS}.tx/debtorAgentBic", tx.debtor_agent.bicfi))
    if tx.creditor:
        out.append(Datom(entity, f"{NS}.tx/creditorName", tx.creditor.name))
    if tx.creditor_account and tx.creditor_account.iban:
        out.append(Datom(entity, f"{NS}.tx/creditorIban", tx.creditor_account.iban))
    if tx.creditor_agent and tx.creditor_agent.bicfi:
        out.append(Datom(entity, f"{NS}.tx/creditorAgentBic", tx.creditor_agent.bicfi))
    if tx.remittance_info:
        for i, line in enumerate(tx.remittance_info.unstructured):
            out.append(Datom(entity, f"{NS}.tx/remittance[{i}]", line))
    return out


def to_datoms(msg: AnyMessage) -> list[Datom]:
    """Map an ISO 20022 message to append-only kotoba EAVT Datoms."""
    gh = msg.group_header
    msg_entity = f"{NS}/msg:{gh.message_id}"
    out: list[Datom] = [
        Datom(msg_entity, f"{NS}.msg/messageId", gh.message_id),
        Datom(msg_entity, f"{NS}.msg/creationDateTime", gh.creation_datetime),
    ]

    if isinstance(msg, CustomerCreditTransferInitiation):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "pain.001"))
        for pmt in msg.payments:
            for tx in pmt.transactions:
                ent = _tx_entity(tx)
                out.append(Datom(msg_entity, f"{NS}.msg/hasTx", ent))
                out.extend(_tx_datoms(ent, tx))
    elif isinstance(msg, FIToFICustomerCreditTransfer):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "pacs.008"))
        for tx in msg.transactions:
            ent = _tx_entity(tx)
            out.append(Datom(msg_entity, f"{NS}.msg/hasTx", ent))
            out.extend(_tx_datoms(ent, tx))
    elif isinstance(msg, FIToFIPaymentStatusReport):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "pacs.002"))
        out.append(Datom(msg_entity, f"{NS}.msg/originalMessageId", msg.original_message_id))
        for sts in msg.statuses:
            ref = (
                sts.original_uetr or sts.original_tx_id
                or sts.original_end_to_end_id or sts.status_id
            )
            ent = f"{NS}/tx:{ref}"
            out.append(Datom(ent, f"{NS}.tx/status", sts.transaction_status))
            if sts.status_reason_code:
                out.append(Datom(ent, f"{NS}.tx/statusReason", sts.status_reason_code))
    elif isinstance(msg, BankToCustomerStatement):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "camt.053"))
        for stmt in msg.statements:
            for entry in stmt.entries:
                out.extend(_entry_datoms(msg_entity, entry, "camt.053"))
    elif isinstance(msg, BankToCustomerDebitCreditNotification):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "camt.054"))
        for ntf in msg.notifications:
            for entry in ntf.entries:
                out.extend(_entry_datoms(msg_entity, entry, "camt.054"))
    elif isinstance(msg, PaymentReturn):
        out.append(Datom(msg_entity, f"{NS}.msg/definition", "pacs.004"))
        for rtx in msg.transactions:
            oref = rtx.original_uetr or rtx.original_tx_id or rtx.original_end_to_end_id
            if oref is None:
                continue
            ent = f"{NS}/tx:{oref}"
            # the return lands on the SAME entity as the original transfer
            out.append(Datom(ent, f"{NS}.tx/status", "RTND"))
            ramt = rtx.returned_interbank_amount
            out.append(Datom(ent, f"{NS}.tx/returnedAmount", str(ramt.value)))
            out.append(Datom(ent, f"{NS}.tx/returnedCurrency", ramt.currency))
            if rtx.return_reason_code:
                out.append(Datom(ent, f"{NS}.tx/returnReason", rtx.return_reason_code))
    else:  # pragma: no cover - exhaustive by construction
        raise TypeError(f"unsupported message type: {type(msg)!r}")

    return out


def _entry_datoms(msg_entity: str, entry: StatementEntry, definition: str) -> list[Datom]:
    """Map a camt Ntry to reconciliation Datoms.

    When the entry carries an EndToEndId it lands on the SAME content-
    addressed transaction entity as the original pain.001/pacs.008 ingress,
    so a statement/notification *reconciles* against the earlier message
    (the off-ramp closing the loop) rather than creating a parallel record.
    Entries without an EndToEndId get their own AcctSvcrRef-keyed entity.
    """
    ref = entry.end_to_end_id or entry.account_servicer_reference
    ent = f"{NS}/tx:{ref}" if ref else msg_entity
    out: list[Datom] = [
        Datom(ent, f"{NS}.entry/amount", str(entry.amount.value)),
        Datom(ent, f"{NS}.entry/currency", entry.amount.currency),
        Datom(ent, f"{NS}.entry/creditDebit", entry.credit_debit),
        Datom(ent, f"{NS}.entry/status", entry.status),
        Datom(ent, f"{NS}.entry/reportedBy", definition),
    ]
    if entry.booking_date:
        out.append(Datom(ent, f"{NS}.entry/bookingDate", entry.booking_date))
    if entry.value_date:
        out.append(Datom(ent, f"{NS}.entry/valueDate", entry.value_date))
    if entry.account_servicer_reference:
        out.append(Datom(ent, f"{NS}.entry/acctSvcrRef", entry.account_servicer_reference))
    return out
