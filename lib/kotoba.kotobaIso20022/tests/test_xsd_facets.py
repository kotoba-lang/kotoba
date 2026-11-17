"""Regression tests for AWAI-3229: values the published XSD rejects are refused.

The AWAI-3153 conformance run (lib/kotoba.swift/conformance/README.md, findings
P1-P6) found that the codec emitted documents the ISO 20022 XSDs reject. These
tests pin the fixes: the structure the XSD requires, and a refusal before
emitting for every value facet the codec checks.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    Iso20022CodecError,
    build_camt054,
    build_pacs008,
    build_pain001,
    urn_for,
)
from kotoba_iso20022.model import (
    Account,
    AccountNotification,
    Agent,
    Amount,
    BankToCustomerDebitCreditNotification,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    Party,
    PaymentInstruction,
    StatementEntry,
)
from kotoba_iso20022.validate import InvalidAmount

_UETR = "eb6305c4-3e7a-4b29-9a1f-8d2ce5a71b30"


def _pacs_tx(**over: object) -> CreditTransferTransaction:
    base = CreditTransferTransaction(
        end_to_end_id="E2E-1", uetr=_UETR,
        interbank_amount=Amount(Decimal("10.00"), "EUR"), charge_bearer="SHAR",
        debtor=Party("A"), debtor_agent=Agent(bicfi="DEUTDEFF"),
        creditor=Party("B"), creditor_agent=Agent(bicfi="NWBKGB2L"),
    )
    return replace(base, **over)  # type: ignore[arg-type]


def _pacs(tx: CreditTransferTransaction, created: str = "2026-06-08T09:30:00Z") -> str:
    return build_pacs008(FIToFICustomerCreditTransfer(
        group_header=GroupHeader("M", created, 1, settlement_method="CLRG"), transactions=(tx,),
    ))


def _pain(date: str = "2026-06-09", initiating_party: Party | None = None) -> str:
    tx = CreditTransferTransaction(end_to_end_id="E2E-1",
                                   instructed_amount=Amount(Decimal("1.00"), "EUR"))
    return build_pain001(CustomerCreditTransferInitiation(
        group_header=GroupHeader("M", "2026-06-08T09:30:00Z", 1, initiating_party=initiating_party),
        payments=(PaymentInstruction(
            payment_info_id="P", requested_execution_date=date, debtor=Party("A"),
            debtor_account=Account(iban="DE89370400440532013000"),
            debtor_agent=Agent(bicfi="DEUTDEFF"), transactions=(tx,),
        ),),
    ))


def _local(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


class TestStructure:
    def test_pain001_reqd_exctn_dt_holds_a_dt_child(self) -> None:  # P1
        ns = urn_for("pain.001.001.09")
        root = ET.fromstring(_pain())
        rd = root.find(f".//{{{ns}}}ReqdExctnDt")
        assert rd is not None
        assert [_local(c) for c in rd] == ["Dt"]
        assert (rd.text or "").strip() == ""

    def test_pain001_initgpty_is_always_present(self) -> None:
        ns = urn_for("pain.001.001.09")
        assert ET.fromstring(_pain()).find(f".//{{{ns}}}GrpHdr/{{{ns}}}InitgPty") is not None

    @pytest.mark.parametrize("missing", ["charge_bearer", "debtor", "debtor_agent",
                                         "creditor_agent", "creditor"])
    def test_pacs008_mandatory_transaction_elements(self, missing: str) -> None:  # P2
        with pytest.raises(Iso20022CodecError, match="requires"):
            _pacs(_pacs_tx(**{missing: None}))

    def test_camt054_entry_status_and_bank_transaction_code(self) -> None:  # P3, P4
        ns = urn_for("camt.054.001.08")
        entry = StatementEntry(amount=Amount(Decimal("1.00"), "EUR"), credit_debit="CRDT",
                               status="BOOK", end_to_end_id="E")
        xml = build_camt054(BankToCustomerDebitCreditNotification(
            group_header=GroupHeader("N", "2026-06-08T09:30:00Z", 0),
            notifications=(AccountNotification("N1", "2026-06-08T09:30:00Z",
                                               Account(iban="DE89370400440532013000"), (entry,)),),
        ))
        ntry = ET.fromstring(xml).find(f".//{{{ns}}}Ntry")
        assert ntry is not None
        assert [_local(c) for c in ntry] == ["Amt", "CdtDbtInd", "Sts", "BkTxCd", "NtryDtls"]
        sts = ntry.find(f"{{{ns}}}Sts/{{{ns}}}Cd")
        assert sts is not None and sts.text == "BOOK"


class TestValueFacets:  # P6
    @pytest.mark.parametrize("created", ["t", "2026-06-08 09:30:00", "2026-02-30T00:00:00Z",
                                         "2026-06-08T24:00:00Z", "2026-06-08T09:30:00+15:00"])
    def test_bad_creation_datetime(self, created: str) -> None:
        with pytest.raises(Iso20022CodecError, match="ISODateTime"):
            _pacs(_pacs_tx(), created=created)

    @pytest.mark.parametrize("date", ["2026-6-9", "2026-02-29", "20260609"])
    def test_bad_requested_execution_date(self, date: str) -> None:
        with pytest.raises(Iso20022CodecError, match="ISODate"):
            _pain(date=date)

    def test_leap_day_is_accepted(self) -> None:
        assert "<Dt>2028-02-29</Dt>" in _pain(date="2028-02-29")

    @pytest.mark.parametrize("uetr", [_UETR.upper(), "eb6305c4-3e7a-1b29-9a1f-8d2ce5a71b30", "x"])
    def test_bad_uetr(self, uetr: str) -> None:
        with pytest.raises(Iso20022CodecError, match="UUIDv4"):
            _pacs(_pacs_tx(uetr=uetr))

    def test_identifier_longer_than_35(self) -> None:
        with pytest.raises(Iso20022CodecError, match="Max35Text"):
            _pacs(_pacs_tx(end_to_end_id="E" * 36))

    def test_empty_name(self) -> None:
        with pytest.raises(Iso20022CodecError, match="Max140Text"):
            _pacs(_pacs_tx(creditor=Party("")))

    def test_amount_fraction_digits(self) -> None:
        # validate_amount refuses it first; the facet check is the backstop.
        with pytest.raises((Iso20022CodecError, InvalidAmount)):
            _pacs(_pacs_tx(interbank_amount=Amount(Decimal("1.000001"), "EUR")))

    def test_valid_document_passes_unchanged(self) -> None:
        xml = _pacs(_pacs_tx())
        assert f"<UETR>{_UETR}</UETR>" in xml
        assert "<ChrgBr>SHAR</ChrgBr>" in xml
