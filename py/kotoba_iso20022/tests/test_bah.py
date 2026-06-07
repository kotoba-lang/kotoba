"""Tests for head.001 BAH + CBPR+ business-message envelope + pain.002."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    Iso20022CodecError,
    build_bah,
    build_business_message,
    build_pacs008,
    build_pain002,
    parse_bah,
    parse_business_message,
    parse_pacs008,
    parse_pain002,
    urn_for,
)
from kotoba_iso20022.bah import DEFAULT_BAH_VERSION
from kotoba_iso20022.model import (
    Amount,
    BusinessApplicationHeader,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    OriginalPaymentStatus,
    TransactionStatus,
)


def _bah(msgdef: str = "pacs.008.001.08") -> BusinessApplicationHeader:
    return BusinessApplicationHeader(
        from_bic="DEUTDEFF",
        to_bic="NWBKGB2L",
        business_message_id="BMID-2026-0608-1",
        message_definition=msgdef,
        creation_datetime="2026-06-08T09:30:00Z",
        business_service="swift.cbprplus.02",
    )


def _pacs008_xml() -> str:
    tx = CreditTransferTransaction(
        end_to_end_id="E2E-0001", interbank_amount=Amount(Decimal("1000.00"), "EUR")
    )
    msg = FIToFICustomerCreditTransfer(
        group_header=GroupHeader("M", "2026-06-08T09:30:00Z", 1, settlement_method="CLRG"),
        transactions=(tx,),
    )
    return build_pacs008(msg)


class TestBah:
    def test_roundtrip(self) -> None:
        back = parse_bah(build_bah(_bah()))
        assert back.from_bic == "DEUTDEFF"
        assert back.to_bic == "NWBKGB2L"
        assert back.message_definition == "pacs.008.001.08"
        assert back.business_service == "swift.cbprplus.02"

    def test_official_namespace(self) -> None:
        root = ET.fromstring(build_bah(_bah()))
        assert root.tag == f"{{{urn_for(DEFAULT_BAH_VERSION)}}}AppHdr"

    def test_invalid_bic_rejected(self) -> None:
        from kotoba_iso20022.validate import InvalidBic
        with pytest.raises(InvalidBic):
            build_bah(_bah().__class__(
                from_bic="BAD", to_bic="NWBKGB2L", business_message_id="x",
                message_definition="pacs.008.001.08", creation_datetime="2026-06-08T09:30:00Z",
            ))


class TestBusinessMessageEnvelope:
    def test_roundtrip_pairs_header_and_document(self) -> None:
        env = build_business_message(_bah(), _pacs008_xml())
        header, doc_xml = parse_business_message(env)
        assert header.business_message_id == "BMID-2026-0608-1"
        # the inner document still parses as a real pacs.008
        msg = parse_pacs008(doc_xml)
        assert msg.transactions[0].end_to_end_id == "E2E-0001"

    def test_cbpr_msgdef_mismatch_rejected_on_build(self) -> None:
        # BAH says pain.001 but the document is pacs.008 → CBPR+ violation
        with pytest.raises(Iso20022CodecError):
            build_business_message(_bah(msgdef="pain.001.001.09"), _pacs008_xml())

    def test_cbpr_msgdef_mismatch_rejected_on_parse(self) -> None:
        env = build_business_message(
            _bah(msgdef="pain.001.001.09"), _pacs008_xml(), enforce_msgdef_match=False
        )
        with pytest.raises(Iso20022CodecError):
            parse_business_message(env)

    def test_envelope_has_apphdr_and_document_siblings(self) -> None:
        env = build_business_message(_bah(), _pacs008_xml())
        root = ET.fromstring(env)
        assert root.tag == "Envelope"
        children = list(root)
        assert children[0].tag.endswith("}AppHdr")
        assert children[1].tag.endswith("}Document")


class TestPain002:
    def test_roundtrip(self) -> None:
        msg = parse_pain002(
            build_pain002(
                _pain002_message()
            )
        )
        assert msg.original_message_name_id == "pain.001.001.09"
        pstat = msg.payment_statuses[0]
        assert pstat.original_payment_info_id == "PMT-0001"
        assert pstat.statuses[0].transaction_status == "RJCT"
        assert pstat.statuses[0].status_reason_code == "AC04"


def _pain002_message():
    from kotoba_iso20022.model import CustomerPaymentStatusReport

    return CustomerPaymentStatusReport(
        group_header=GroupHeader("STS-1", "2026-06-08T10:00:00Z", 0),
        original_message_id="MSG-2026-0608-0001",
        original_message_name_id="pain.001.001.09",
        payment_statuses=(
            OriginalPaymentStatus(
                original_payment_info_id="PMT-0001",
                statuses=(
                    TransactionStatus(
                        status_id="S1",
                        original_end_to_end_id="E2E-0001",
                        transaction_status="RJCT",
                        status_reason_code="AC04",
                        additional_info=("account closed",),
                    ),
                ),
            ),
        ),
    )
