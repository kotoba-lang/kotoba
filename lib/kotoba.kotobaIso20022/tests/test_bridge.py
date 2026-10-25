"""Tests for the ISO 20022 → kawase ingressAttestation bridge.

Also checks each produced record against the actual Lexicon JSON
(required fields + no-float discipline).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from kotoba_iso20022 import RECORD_TYPE, ingress_attestations
from kotoba_iso20022.model import (
    Account,
    AccountNotification,
    Agent,
    Amount,
    BankToCustomerDebitCreditNotification,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    FIToFIPaymentStatusReport,
    GroupHeader,
    Party,
    RemittanceInfo,
    StatementEntry,
    TransactionStatus,
)

GOOD_UETR = "dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"

# Load the vendored compatibility contract so a standalone checkout is closed.
_LEXICON = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "contracts/lexicons/com/etzhayyim/iso20022/ingressAttestation.json"
    ).read_text()
)
_REQUIRED = _LEXICON["defs"]["main"]["record"]["required"]


def _assert_lexicon_shape(rec: dict) -> None:
    assert rec["$type"] == RECORD_TYPE
    for field in _REQUIRED:
        assert field in rec, f"missing required field {field}"
    # No floats anywhere (amount must be string, not float).
    assert isinstance(rec["amount"], str)
    for v in rec.values():
        assert not isinstance(v, float)


def _pacs008() -> FIToFICustomerCreditTransfer:
    tx = CreditTransferTransaction(
        end_to_end_id="E2E-0001",
        uetr=GOOD_UETR,
        interbank_amount=Amount(Decimal("1000.00"), "EUR"),
        debtor=Party("Alice Cohen"),
        debtor_agent=Agent(bicfi="DEUTDEFF"),
        creditor=Party("Bob Levi"),
        creditor_agent=Agent(bicfi="NWBKGB2L"),
    )
    return FIToFICustomerCreditTransfer(
        group_header=GroupHeader("MSG-1", "2026-06-08T09:30:00Z", 1, settlement_method="CLRG"),
        transactions=(tx,),
    )


class TestPacs008Bridge:
    def test_one_record_per_tx_with_lexicon_shape(self) -> None:
        recs = ingress_attestations(
            _pacs008(), ingested_at="2026-06-08T23:00:00Z", cbpr_conformant=True
        )
        assert len(recs) == 1
        rec = recs[0]
        _assert_lexicon_shape(rec)
        assert rec["messageDefinition"] == "pacs.008.001.08"
        assert rec["endToEndId"] == "E2E-0001"
        assert rec["uetr"] == GOOD_UETR
        assert rec["amount"] == "1000.00"
        assert rec["currency"] == "EUR"
        assert rec["reportedBy"] == "pacs.008"
        assert rec["debtorAgentBic"] == "DEUTDEFF"
        assert rec["creditorAgentBic"] == "NWBKGB2L"
        assert rec["cbprConformant"] is True

    def test_party_names_omitted_by_default(self) -> None:
        rec = ingress_attestations(_pacs008(), ingested_at="2026-06-08T23:00:00Z")[0]
        assert "debtorName" not in rec
        assert "creditorName" not in rec

    def test_party_names_opt_in(self) -> None:
        rec = ingress_attestations(
            _pacs008(), ingested_at="2026-06-08T23:00:00Z", include_party_names=True
        )[0]
        assert rec["debtorName"] == "Alice Cohen"
        assert rec["creditorName"] == "Bob Levi"

    def test_linked_deposit_cid_for_reconciliation(self) -> None:
        rec = ingress_attestations(
            _pacs008(), ingested_at="2026-06-08T23:00:00Z",
            linked_deposit_cid="bafyreideposit",
        )[0]
        assert rec["linkedDepositCid"] == "bafyreideposit"

    def test_tx_entity_matches_datom_entity(self) -> None:
        from kotoba_iso20022 import to_datoms
        rec = ingress_attestations(_pacs008(), ingested_at="2026-06-08T23:00:00Z")[0]
        datom_entities = {d.entity for d in to_datoms(_pacs008())}
        assert rec["txEntity"] in datom_entities


class TestCamt054Bridge:
    def test_entry_records(self) -> None:
        entry = StatementEntry(
            amount=Amount(Decimal("1000.00"), "EUR"),
            credit_debit="CRDT",
            status="BOOK",
            end_to_end_id="E2E-0001",
            remittance_info=RemittanceInfo(unstructured=("on-ramp",)),
        )
        msg = BankToCustomerDebitCreditNotification(
            group_header=GroupHeader("CAMT-1", "2026-06-08T23:00:00Z", 0),
            notifications=(
                AccountNotification("N", "2026-06-08T23:05:00Z",
                                    Account(iban="DE89370400440532013000"), (entry,)),
            ),
        )
        rec = ingress_attestations(msg, ingested_at="2026-06-08T23:10:00Z")[0]
        _assert_lexicon_shape(rec)
        assert rec["reportedBy"] == "camt.054"
        assert rec["creditDebit"] == "CRDT"
        assert rec["status"] == "BOOK"
        # reconciles onto the same entity a prior pacs.008 ingress used
        assert rec["txEntity"] == "com.etzhayyim.iso20022/tx:E2E-0001"


def test_status_report_rejected() -> None:
    report = FIToFIPaymentStatusReport(
        group_header=GroupHeader("STS-1", "2026-06-08T09:31:00Z", 0),
        original_message_id="MSG-1",
        original_message_name_id="pacs.008.001.08",
        statuses=(TransactionStatus(status_id="S1", transaction_status="ACSC"),),
    )
    with pytest.raises(TypeError):
        ingress_attestations(report, ingested_at="2026-06-08T23:10:00Z")
