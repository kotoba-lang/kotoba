"""Tests for the ISO 20022 → kotoba EAVT Datom ingress mapping."""

from __future__ import annotations

from decimal import Decimal

from kotoba_iso20022 import to_datoms
from kotoba_iso20022.datoms import NS
from kotoba_iso20022.model import (
    Account,
    Agent,
    Amount,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    FIToFIPaymentStatusReport,
    GroupHeader,
    Party,
    TransactionStatus,
)


def _pacs008() -> FIToFICustomerCreditTransfer:
    tx = CreditTransferTransaction(
        end_to_end_id="E2E-0001",
        tx_id="TX-0001",
        uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
        interbank_amount=Amount(Decimal("1000.00"), "EUR"),
        interbank_settlement_date="2026-06-08",
        charge_bearer="SLEV",
        debtor=Party("Alice Cohen"),
        debtor_account=Account(iban="DE89370400440532013000"),
        debtor_agent=Agent(bicfi="DEUTDEFF"),
        creditor=Party("Bob Levi"),
        creditor_account=Account(iban="GB29NWBK60161331926819"),
        creditor_agent=Agent(bicfi="NWBKGB2L"),
    )
    return FIToFICustomerCreditTransfer(
        group_header=GroupHeader(
            message_id="MSG-1", creation_datetime="2026-06-08T09:30:00Z", number_of_txs=1
        ),
        transactions=(tx,),
    )


def test_entity_is_content_addressed_on_uetr() -> None:
    datoms = to_datoms(_pacs008())
    tx_entity = f"{NS}/tx:dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"
    assert any(d.entity == tx_entity for d in datoms)


def test_all_ops_are_assertions() -> None:
    # ingress never retracts (kawase-yui G11 mirror)
    assert all(d.op is True for d in to_datoms(_pacs008()))


def test_idempotent_entity_handles() -> None:
    # re-mapping the same message yields identical (e, a, v) tuples
    a = [d.as_tuple() for d in to_datoms(_pacs008())]
    b = [d.as_tuple() for d in to_datoms(_pacs008())]
    assert a == b


def test_core_facts_present() -> None:
    facts = {(d.attribute, d.value) for d in to_datoms(_pacs008())}
    assert (f"{NS}.tx/amount", "1000.00") in facts
    assert (f"{NS}.tx/currency", "EUR") in facts
    assert (f"{NS}.tx/debtorIban", "DE89370400440532013000") in facts
    assert (f"{NS}.tx/creditorAgentBic", "NWBKGB2L") in facts
    assert (f"{NS}.msg/definition", "pacs.008") in facts


def test_pacs002_status_lands_on_same_tx_entity() -> None:
    report = FIToFIPaymentStatusReport(
        group_header=GroupHeader(
            message_id="STS-1", creation_datetime="2026-06-08T09:31:00Z", number_of_txs=0
        ),
        original_message_id="MSG-1",
        original_message_name_id="pacs.008.001.08",
        statuses=(
            TransactionStatus(
                status_id="S1",
                original_uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
                transaction_status="ACSC",
            ),
        ),
    )
    datoms = to_datoms(report)
    tx_entity = f"{NS}/tx:dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"
    assert any(
        d.entity == tx_entity and d.attribute == f"{NS}.tx/status" and d.value == "ACSC"
        for d in datoms
    )
