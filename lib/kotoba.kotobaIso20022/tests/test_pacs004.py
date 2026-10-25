"""pacs.004 PaymentReturn — round-trip + reversal reconciliation."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    DEFAULT_VERSIONS,
    Iso20022CodecError,
    build_pacs004,
    parse_pacs004,
    to_datoms,
    urn_for,
)
from kotoba_iso20022.datoms import NS
from kotoba_iso20022.model import (
    Amount,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    PaymentReturn,
    PaymentReturnTransaction,
)

GOOD_UETR = "dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"


def _return() -> PaymentReturn:
    tx = PaymentReturnTransaction(
        returned_interbank_amount=Amount(Decimal("1000.00"), "EUR"),
        return_id="RTR-1",
        original_end_to_end_id="E2E-0001",
        original_tx_id="TX-0001",
        original_uetr=GOOD_UETR,
        original_interbank_amount=Amount(Decimal("1000.00"), "EUR"),
        interbank_settlement_date="2026-06-10",
        return_reason_code="AC04",  # account closed
        additional_info=("beneficiary account closed",),
    )
    return PaymentReturn(
        group_header=GroupHeader("RTN-1", "2026-06-10T09:00:00Z", 1, settlement_method="CLRG"),
        transactions=(tx,),
        original_message_id="MSG-2026-0608-0001",
        original_message_name_id="pacs.008.001.08",
    )


class TestRoundTrip:
    def test_roundtrip(self) -> None:
        back = parse_pacs004(build_pacs004(_return()))
        assert back.original_message_name_id == "pacs.008.001.08"
        tx = back.transactions[0]
        assert tx.return_id == "RTR-1"
        assert tx.original_uetr == GOOD_UETR
        assert tx.original_end_to_end_id == "E2E-0001"
        assert tx.returned_interbank_amount == Amount(Decimal("1000.00"), "EUR")
        assert tx.original_interbank_amount == Amount(Decimal("1000.00"), "EUR")
        assert tx.return_reason_code == "AC04"
        assert tx.additional_info == ("beneficiary account closed",)
        assert tx.interbank_settlement_date == "2026-06-10"

    def test_official_namespace(self) -> None:
        root = ET.fromstring(build_pacs004(_return()))
        assert root.tag == f"{{{urn_for(DEFAULT_VERSIONS['pacs.004'])}}}Document"

    def test_minimal_return(self) -> None:
        msg = PaymentReturn(
            group_header=GroupHeader("R", "t", 1, settlement_method="CLRG"),
            transactions=(
                PaymentReturnTransaction(
                    returned_interbank_amount=Amount(Decimal("5.00"), "USD"),
                    original_end_to_end_id="E2E-X",
                ),
            ),
        )
        back = parse_pacs004(build_pacs004(msg))
        assert back.transactions[0].returned_interbank_amount.value == Decimal("5.00")
        assert back.original_message_id is None

    def test_missing_returned_amount_raises(self) -> None:
        body = (
            "<PmtRtr><GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm><NbOfTxs>1</NbOfTxs>"
            "<SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf></GrpHdr>"
            "<TxInf><OrgnlEndToEndId>E</OrgnlEndToEndId></TxInf></PmtRtr>"
        )
        ns = urn_for(DEFAULT_VERSIONS["pacs.004"])
        with pytest.raises(Iso20022CodecError, match="RtrdIntrBkSttlmAmt"):
            parse_pacs004(f"<Document xmlns='{ns}'>{body}</Document>")


class TestReversalReconciliation:
    def test_return_lands_on_original_transfer_entity(self) -> None:
        # original transfer ingress
        pacs008 = FIToFICustomerCreditTransfer(
            group_header=GroupHeader("M", "2026-06-08T09:30:00Z", 1, settlement_method="CLRG"),
            transactions=(
                CreditTransferTransaction(
                    end_to_end_id="E2E-0001", uetr=GOOD_UETR,
                    interbank_amount=Amount(Decimal("1000.00"), "EUR"),
                ),
            ),
        )
        entity = f"{NS}/tx:{GOOD_UETR}"
        assert any(d.entity == entity for d in to_datoms(pacs008))

        # the return lands on the SAME entity, asserting RTND + reason
        rd = to_datoms(_return())
        facts = {(d.attribute, d.value) for d in rd if d.entity == entity}
        assert (f"{NS}.tx/status", "RTND") in facts
        assert (f"{NS}.tx/returnReason", "AC04") in facts
        assert (f"{NS}.tx/returnedAmount", "1000.00") in facts
        assert (f"{NS}.tx/returnedCurrency", "EUR") in facts

    def test_definition_fact(self) -> None:
        facts = {(d.attribute, d.value) for d in to_datoms(_return())}
        assert (f"{NS}.msg/definition", "pacs.004") in facts

    def test_return_without_original_refs_emits_no_tx_facts(self) -> None:
        msg = PaymentReturn(
            group_header=GroupHeader("R", "t", 1, settlement_method="CLRG"),
            transactions=(
                PaymentReturnTransaction(
                    returned_interbank_amount=Amount(Decimal("1.00"), "EUR"),
                ),  # no original_uetr/tx_id/end_to_end_id
            ),
        )
        datoms = to_datoms(msg)
        # only the message-level facts; no per-tx entity facts
        assert all(not d.entity.startswith(f"{NS}/tx:") for d in datoms)
        assert any(d.attribute == f"{NS}.msg/definition" and d.value == "pacs.004" for d in datoms)
