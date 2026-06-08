"""Round-trip + reconciliation tests for camt.053 / camt.054."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    DEFAULT_VERSIONS,
    Iso20022CodecError,
    build_camt053,
    build_camt054,
    parse_camt053,
    parse_camt054,
    to_datoms,
    urn_for,
)
from kotoba_iso20022.datoms import NS
from kotoba_iso20022.model import (
    Account,
    AccountNotification,
    AccountStatement,
    Amount,
    BankToCustomerDebitCreditNotification,
    BankToCustomerStatement,
    CashBalance,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    RemittanceInfo,
    StatementEntry,
)

_GH = GroupHeader(message_id="CAMT-1", creation_datetime="2026-06-08T23:00:00Z", number_of_txs=0)
_ACCT = Account(iban="DE89370400440532013000", currency="EUR")


def _entry() -> StatementEntry:
    return StatementEntry(
        amount=Amount(Decimal("1000.00"), "EUR"),
        credit_debit="CRDT",
        status="BOOK",
        booking_date="2026-06-08",
        value_date="2026-06-09",
        account_servicer_reference="ACCTSVCR-77",
        end_to_end_id="E2E-0001",
        remittance_info=RemittanceInfo(unstructured=("kawase-yui on-ramp",)),
    )


class TestCamt053:
    def test_roundtrip(self) -> None:
        msg = BankToCustomerStatement(
            group_header=_GH,
            statements=(
                AccountStatement(
                    statement_id="STMT-1",
                    creation_datetime="2026-06-08T23:00:00Z",
                    account=_ACCT,
                    balances=(
                        CashBalance("OPBD", Amount(Decimal("0.00"), "EUR"), "CRDT", "2026-06-08"),
                        CashBalance("CLBD", Amount(Decimal("1000.00"), "EUR"), "CRDT", "2026-06-08"),
                    ),
                    entries=(_entry(),),
                ),
            ),
        )
        back = parse_camt053(build_camt053(msg))
        stmt = back.statements[0]
        assert stmt.account.iban == "DE89370400440532013000"
        assert len(stmt.balances) == 2
        assert stmt.balances[1].balance_type == "CLBD"
        assert stmt.balances[1].amount == Amount(Decimal("1000.00"), "EUR")
        e = stmt.entries[0]
        assert e.credit_debit == "CRDT"
        assert e.status == "BOOK"
        assert e.value_date == "2026-06-09"
        assert e.end_to_end_id == "E2E-0001"
        assert e.remittance_info.unstructured == ("kawase-yui on-ramp",)

    def test_official_namespace(self) -> None:
        msg = BankToCustomerStatement(
            group_header=_GH,
            statements=(
                AccountStatement("S", "2026-06-08T23:00:00Z", _ACCT, (), (_entry(),)),
            ),
        )
        root = ET.fromstring(build_camt053(msg))
        assert root.tag == f"{{{urn_for(DEFAULT_VERSIONS['camt.053'])}}}Document"


class TestCamt054:
    def test_roundtrip(self) -> None:
        msg = BankToCustomerDebitCreditNotification(
            group_header=_GH,
            notifications=(
                AccountNotification(
                    notification_id="NTF-1",
                    creation_datetime="2026-06-08T23:05:00Z",
                    account=_ACCT,
                    entries=(_entry(),),
                ),
            ),
        )
        back = parse_camt054(build_camt054(msg))
        ntf = back.notifications[0]
        assert ntf.notification_id == "NTF-1"
        assert ntf.entries[0].end_to_end_id == "E2E-0001"

    def test_bad_namespace_raises(self) -> None:
        msg = BankToCustomerDebitCreditNotification(
            group_header=_GH,
            notifications=(AccountNotification("N", "2026-06-08T23:05:00Z", _ACCT, (_entry(),)),),
        )
        xml = build_camt054(msg, version="camt.054.001.08")
        with pytest.raises(Iso20022CodecError):
            parse_camt054(xml, version="camt.054.001.10")


def test_camt054_entry_reconciles_against_pacs008_ingress() -> None:
    # An inbound pacs.008 lands first as ingress, keyed by EndToEndId.
    pacs = FIToFICustomerCreditTransfer(
        group_header=GroupHeader("M", "2026-06-08T09:30:00Z", 1, settlement_method="CLRG"),
        transactions=(
            CreditTransferTransaction(
                end_to_end_id="E2E-0001",
                interbank_amount=Amount(Decimal("1000.00"), "EUR"),
            ),
        ),
    )
    # Later a camt.054 credit notification arrives for the same EndToEndId.
    camt = BankToCustomerDebitCreditNotification(
        group_header=_GH,
        notifications=(AccountNotification("N", "2026-06-08T23:05:00Z", _ACCT, (_entry(),)),),
    )
    ingress_entity = f"{NS}/tx:E2E-0001"
    pacs_datoms = to_datoms(pacs)
    camt_datoms = to_datoms(camt)
    # Both reference the SAME content-addressed transaction entity.
    assert any(d.entity == ingress_entity for d in pacs_datoms)
    assert any(d.entity == ingress_entity for d in camt_datoms)
    # The camt side asserts the booked-entry reconciliation facts.
    camt_facts = {(d.attribute, d.value) for d in camt_datoms if d.entity == ingress_entity}
    assert (f"{NS}.entry/creditDebit", "CRDT") in camt_facts
    assert (f"{NS}.entry/status", "BOOK") in camt_facts
    assert (f"{NS}.entry/reportedBy", "camt.054") in camt_facts
