"""Round-trip + structural tests for the ISO 20022 codec."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    DEFAULT_VERSIONS,
    Iso20022CodecError,
    build_pacs002,
    build_pacs008,
    build_pain001,
    parse_pacs002,
    parse_pacs008,
    parse_pain001,
    urn_for,
)
from kotoba_iso20022.model import (
    Account,
    Agent,
    Amount,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    FIToFICustomerCreditTransfer,
    FIToFIPaymentStatusReport,
    GroupHeader,
    Party,
    PaymentInstruction,
    RemittanceInfo,
    TransactionStatus,
)


def _alice_to_bob_tx(*, interbank: bool) -> CreditTransferTransaction:
    amt = Amount(Decimal("1000.00"), "EUR")
    return CreditTransferTransaction(
        end_to_end_id="E2E-0001",
        instruction_id="INSTR-0001",
        tx_id="TX-0001" if interbank else None,
        uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
        instructed_amount=None if interbank else amt,
        interbank_amount=amt if interbank else None,
        interbank_settlement_date="2026-06-08" if interbank else None,
        charge_bearer="SLEV" if interbank else None,
        debtor=Party("Alice Cohen", identifier="DE-ALICE"),
        debtor_account=Account(iban="DE89370400440532013000"),
        debtor_agent=Agent(bicfi="DEUTDEFF"),
        creditor_agent=Agent(bicfi="NWBKGB2L"),
        creditor=Party("Bob Levi"),
        creditor_account=Account(iban="GB29NWBK60161331926819"),
        remittance_info=RemittanceInfo(unstructured=("kawase-yui on-ramp", "ref 42")),
    )


def _group_header(*, pacs: bool) -> GroupHeader:
    return GroupHeader(
        message_id="MSG-2026-0608-0001",
        creation_datetime="2026-06-08T09:30:00Z",
        number_of_txs=1,
        control_sum=Decimal("1000.00"),
        initiating_party=None if pacs else Party("etzhayyim kawase-yui"),
        settlement_method="CLRG" if pacs else None,
    )


class TestPain001:
    def test_roundtrip(self) -> None:
        msg = CustomerCreditTransferInitiation(
            group_header=_group_header(pacs=False),
            payments=(
                PaymentInstruction(
                    payment_info_id="PMT-0001",
                    requested_execution_date="2026-06-08",
                    debtor=Party("Alice Cohen"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=(_alice_to_bob_tx(interbank=False),),
                ),
            ),
        )
        xml = build_pain001(msg)
        back = parse_pain001(xml)
        tx = back.payments[0].transactions[0]
        assert back.group_header.message_id == "MSG-2026-0608-0001"
        assert tx.end_to_end_id == "E2E-0001"
        assert tx.instructed_amount == Amount(Decimal("1000.00"), "EUR")
        assert tx.creditor_account.iban == "GB29NWBK60161331926819"
        assert tx.remittance_info.unstructured == ("kawase-yui on-ramp", "ref 42")

    def test_namespace_is_official_urn(self) -> None:
        msg = CustomerCreditTransferInitiation(
            group_header=_group_header(pacs=False),
            payments=(
                PaymentInstruction(
                    payment_info_id="PMT-0001",
                    requested_execution_date="2026-06-08",
                    debtor=Party("Alice"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=(_alice_to_bob_tx(interbank=False),),
                ),
            ),
        )
        xml = build_pain001(msg)
        root = ET.fromstring(xml)
        assert root.tag == f"{{{urn_for(DEFAULT_VERSIONS['pain.001'])}}}Document"

    def test_missing_amount_raises(self) -> None:
        bad_tx = CreditTransferTransaction(end_to_end_id="E2E", instructed_amount=None)
        msg = CustomerCreditTransferInitiation(
            group_header=_group_header(pacs=False),
            payments=(
                PaymentInstruction(
                    payment_info_id="P",
                    requested_execution_date="2026-06-08",
                    debtor=Party("A"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=(bad_tx,),
                ),
            ),
        )
        with pytest.raises(Iso20022CodecError):
            build_pain001(msg)


class TestPacs008:
    def test_roundtrip(self) -> None:
        msg = FIToFICustomerCreditTransfer(
            group_header=_group_header(pacs=True),
            transactions=(_alice_to_bob_tx(interbank=True),),
        )
        xml = build_pacs008(msg)
        back = parse_pacs008(xml)
        tx = back.transactions[0]
        assert back.group_header.settlement_method == "CLRG"
        assert tx.tx_id == "TX-0001"
        assert tx.uetr == "dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"
        assert tx.interbank_amount == Amount(Decimal("1000.00"), "EUR")
        assert tx.interbank_settlement_date == "2026-06-08"
        assert tx.charge_bearer == "SLEV"
        assert tx.debtor_agent.bicfi == "DEUTDEFF"
        assert tx.creditor_agent.bicfi == "NWBKGB2L"

    def test_jpy_amount_formats_without_fraction(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E2E-JPY",
            interbank_amount=Amount(Decimal("500000"), "JPY"),
        )
        msg = FIToFICustomerCreditTransfer(
            group_header=_group_header(pacs=True), transactions=(tx,)
        )
        xml = build_pacs008(msg)
        assert ">500000<" in xml
        back = parse_pacs008(xml)
        assert back.transactions[0].interbank_amount.value == Decimal("500000")

    def test_missing_interbank_amount_raises(self) -> None:
        tx = CreditTransferTransaction(end_to_end_id="E2E", interbank_amount=None)
        msg = FIToFICustomerCreditTransfer(
            group_header=_group_header(pacs=True), transactions=(tx,)
        )
        with pytest.raises(Iso20022CodecError):
            build_pacs008(msg)

    def test_wrong_namespace_parse_raises(self) -> None:
        msg = FIToFICustomerCreditTransfer(
            group_header=_group_header(pacs=True),
            transactions=(_alice_to_bob_tx(interbank=True),),
        )
        xml = build_pacs008(msg, version="pacs.008.001.08")
        with pytest.raises(Iso20022CodecError):
            parse_pacs008(xml, version="pacs.008.001.10")


class TestPacs002:
    def test_roundtrip_accepted(self) -> None:
        msg = FIToFIPaymentStatusReport(
            group_header=GroupHeader(
                message_id="STS-0001",
                creation_datetime="2026-06-08T09:31:00Z",
                number_of_txs=0,
            ),
            original_message_id="MSG-2026-0608-0001",
            original_message_name_id="pacs.008.001.08",
            statuses=(
                TransactionStatus(
                    status_id="STSID-1",
                    original_end_to_end_id="E2E-0001",
                    original_uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
                    transaction_status="ACSC",
                ),
            ),
        )
        xml = build_pacs002(msg)
        back = parse_pacs002(xml)
        assert back.original_message_name_id == "pacs.008.001.08"
        assert back.statuses[0].transaction_status == "ACSC"
        assert back.statuses[0].original_end_to_end_id == "E2E-0001"

    def test_roundtrip_rejected_with_reason(self) -> None:
        msg = FIToFIPaymentStatusReport(
            group_header=GroupHeader(
                message_id="STS-0002",
                creation_datetime="2026-06-08T09:32:00Z",
                number_of_txs=0,
            ),
            original_message_id="MSG-2026-0608-0001",
            original_message_name_id="pacs.008.001.08",
            statuses=(
                TransactionStatus(
                    status_id="STSID-2",
                    original_end_to_end_id="E2E-0001",
                    transaction_status="RJCT",
                    status_reason_code="AC04",
                    additional_info=("account closed",),
                ),
            ),
        )
        xml = build_pacs002(msg)
        back = parse_pacs002(xml)
        sts = back.statuses[0]
        assert sts.transaction_status == "RJCT"
        assert sts.status_reason_code == "AC04"
        assert sts.additional_info == ("account closed",)


def test_parse_garbage_raises() -> None:
    with pytest.raises(Iso20022CodecError):
        parse_pacs008("<not-xml")
