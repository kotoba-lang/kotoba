"""Edge-case + error-path coverage across all modules."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    Iso20022CodecError,
    build_pacs008,
    build_pain001,
    control_sum_of,
    ingress_attestations,
    new_uetr,
    pacs008_group_header,
    pain001_group_header,
    parse_pacs008,
    parse_pain001,
    to_datoms,
)
from kotoba_iso20022.bah import (
    build_business_message,
    parse_bah,
    parse_business_message,
)
from kotoba_iso20022.conformance import check_cbpr_bah, check_cbpr_pacs008
from kotoba_iso20022.datoms import NS
from kotoba_iso20022.model import (
    Account,
    AccountStatement,
    Agent,
    Amount,
    BankToCustomerStatement,
    BusinessApplicationHeader,
    CashBalance,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    Party,
    PaymentInstruction,
    PostalAddress,
    StatementEntry,
)
from kotoba_iso20022.validate import is_uetr

# --------------------------------------------------------------------------
# model __post_init__ validation
# --------------------------------------------------------------------------


class TestModelValidation:
    def test_account_requires_an_id(self) -> None:
        with pytest.raises(ValueError):
            Account()

    def test_agent_requires_bic_or_member_id(self) -> None:
        with pytest.raises(ValueError):
            Agent()

    def test_account_other_id_ok(self) -> None:
        assert Account(other_id="123").other_id == "123"

    def test_agent_clearing_member_ok(self) -> None:
        assert Agent(clearing_member_id="USABA021000021").clearing_member_id


# --------------------------------------------------------------------------
# codec optional branches (other_id account, clearing member, postal address)
# --------------------------------------------------------------------------


class TestCodecOptionalBranches:
    def test_pacs008_with_other_id_and_clearing_member_and_address(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E2E",
            interbank_amount=Amount(Decimal("10.00"), "USD"),
            debtor=Party("Acme", postal_address=PostalAddress("US", ("1 Main St",)),
                         identifier="LEI123"),
            debtor_account=Account(other_id="ACCT-1", currency="USD"),
            debtor_agent=Agent(clearing_member_id="021000021"),
            creditor_agent=Agent(bicfi="NWBKGB2L", name="NatWest"),
            creditor=Party("Bob"),
            creditor_account=Account(other_id="C-1"),
        )
        msg = FIToFICustomerCreditTransfer(
            group_header=pacs008_group_header("M", "2026-06-08T09:30:00Z", (tx,)),
            transactions=(tx,),
        )
        back = parse_pacs008(build_pacs008(msg))
        rtx = back.transactions[0]
        assert rtx.debtor.postal_address.country == "US"
        assert rtx.debtor.identifier == "LEI123"
        assert rtx.debtor_account.other_id == "ACCT-1"
        assert rtx.debtor_agent.clearing_member_id == "021000021"
        assert rtx.creditor_agent.name == "NatWest"

    def test_pain001_multiple_transactions_roundtrip(self) -> None:
        txs = tuple(
            CreditTransferTransaction(
                end_to_end_id=f"E2E-{i}",
                instructed_amount=Amount(Decimal("10.00"), "EUR"),
                creditor=Party(f"C{i}"),
                creditor_account=Account(iban="GB29NWBK60161331926819"),
            )
            for i in range(3)
        )
        msg = CustomerCreditTransferInitiation(
            group_header=pain001_group_header("M", "2026-06-08T09:30:00Z", txs,
                                              initiating_party=Party("Org")),
            payments=(
                PaymentInstruction(
                    payment_info_id="P", requested_execution_date="2026-06-08",
                    debtor=Party("Alice"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=txs,
                ),
            ),
        )
        back = parse_pain001(build_pain001(msg))
        assert len(back.payments[0].transactions) == 3
        assert back.group_header.control_sum == Decimal("30.00")


# --------------------------------------------------------------------------
# datoms: pain.001 + camt.053 paths
# --------------------------------------------------------------------------


class TestDatomsPaths:
    def test_pain001_datoms(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E2E-P", instructed_amount=Amount(Decimal("5.00"), "EUR")
        )
        msg = CustomerCreditTransferInitiation(
            group_header=GroupHeader("MP", "2026-06-08T09:30:00Z", 1),
            payments=(
                PaymentInstruction(
                    payment_info_id="P", requested_execution_date="2026-06-08",
                    debtor=Party("Alice"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=(tx,),
                ),
            ),
        )
        facts = {(d.attribute, d.value) for d in to_datoms(msg)}
        assert (f"{NS}.msg/definition", "pain.001") in facts
        assert (f"{NS}.tx/amount", "5.00") in facts

    def test_camt053_datoms(self) -> None:
        entry = StatementEntry(
            amount=Amount(Decimal("7.00"), "EUR"), credit_debit="DBIT", status="BOOK",
            account_servicer_reference="SVCR-9", value_date="2026-06-09",
        )
        msg = BankToCustomerStatement(
            group_header=GroupHeader("CS", "2026-06-08T23:00:00Z", 0),
            statements=(
                AccountStatement("S", "2026-06-08T23:00:00Z",
                                 Account(iban="DE89370400440532013000"),
                                 (CashBalance("OPBD", Amount(Decimal("0"), "EUR"), "CRDT",
                                              "2026-06-08"),),
                                 (entry,)),
            ),
        )
        facts = {(d.attribute, d.value) for d in to_datoms(msg)}
        assert (f"{NS}.msg/definition", "camt.053") in facts
        assert (f"{NS}.entry/reportedBy", "camt.053") in facts
        assert (f"{NS}.entry/creditDebit", "DBIT") in facts


# --------------------------------------------------------------------------
# bridge: pain.001 path + entry without ref skipped
# --------------------------------------------------------------------------


class TestBridgeEdges:
    def test_pain001_bridge(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E2E-P", uetr=new_uetr(),
            instructed_amount=Amount(Decimal("5.00"), "EUR"),
        )
        msg = CustomerCreditTransferInitiation(
            group_header=GroupHeader("MP", "2026-06-08T09:30:00Z", 1),
            payments=(
                PaymentInstruction(
                    payment_info_id="P", requested_execution_date="2026-06-08",
                    debtor=Party("Alice"),
                    debtor_account=Account(iban="DE89370400440532013000"),
                    debtor_agent=Agent(bicfi="DEUTDEFF"),
                    transactions=(tx,),
                ),
            ),
        )
        recs = ingress_attestations(msg, ingested_at="2026-06-08T23:00:00Z")
        assert recs[0]["reportedBy"] == "pain.001"
        assert recs[0]["amount"] == "5.00"

    def test_entry_without_ref_is_skipped(self) -> None:
        from kotoba_iso20022.model import AccountNotification, BankToCustomerDebitCreditNotification
        entry = StatementEntry(amount=Amount(Decimal("1"), "EUR"), credit_debit="CRDT",
                               status="BOOK")  # no end_to_end_id, no acct_svcr_ref
        msg = BankToCustomerDebitCreditNotification(
            group_header=GroupHeader("C", "2026-06-08T23:00:00Z", 0),
            notifications=(AccountNotification("N", "2026-06-08T23:00:00Z",
                                               Account(iban="DE89370400440532013000"), (entry,)),),
        )
        assert ingress_attestations(msg, ingested_at="2026-06-08T23:00:00Z") == []


# --------------------------------------------------------------------------
# bah error paths
# --------------------------------------------------------------------------


def _bah() -> BusinessApplicationHeader:
    return BusinessApplicationHeader(
        from_bic="DEUTDEFF", to_bic="NWBKGB2L", business_message_id="B",
        message_definition="pacs.008.001.08", creation_datetime="2026-06-08T09:30:00Z",
    )


class TestBahErrors:
    def test_parse_bad_xml(self) -> None:
        with pytest.raises(Iso20022CodecError):
            parse_bah("<nope")

    def test_parse_wrong_root(self) -> None:
        with pytest.raises(Iso20022CodecError):
            parse_bah("<Document xmlns='urn:iso:std:iso:20022:tech:xsd:head.001.001.02'/>")

    def test_parse_missing_bic(self) -> None:
        ns = "urn:iso:std:iso:20022:tech:xsd:head.001.001.02"
        xml = f"<AppHdr xmlns='{ns}'><BizMsgIdr>B</BizMsgIdr></AppHdr>"
        with pytest.raises(Iso20022CodecError):
            parse_bah(xml)

    def test_envelope_payload_not_document(self) -> None:
        with pytest.raises(Iso20022CodecError):
            build_business_message(_bah(), "<NotDocument/>")

    def test_envelope_non_iso_namespace(self) -> None:
        with pytest.raises(Iso20022CodecError):
            build_business_message(_bah(), "<Document xmlns='http://example.com'/>")

    def test_parse_envelope_missing_parts(self) -> None:
        with pytest.raises(Iso20022CodecError):
            parse_business_message("<Envelope/>")

    def test_parse_envelope_bad_xml(self) -> None:
        with pytest.raises(Iso20022CodecError):
            parse_business_message("<Envelope")


# --------------------------------------------------------------------------
# conformance: invalid (not just missing) agent BIC + bah BIC
# --------------------------------------------------------------------------


class TestConformanceInvalidBic:
    def test_invalid_agent_bic(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E", uetr=new_uetr(),
            interbank_amount=Amount(Decimal("1.00"), "EUR"),
            charge_bearer="SHAR",
            debtor=Party("A"), debtor_agent=Agent(bicfi="BADBIC!!"),
            creditor=Party("B"), creditor_agent=Agent(bicfi="NWBKGB2L"),
        )
        msg = FIToFICustomerCreditTransfer(
            group_header=pacs008_group_header("M", "2026-06-08T09:30:00Z", (tx,)),
            transactions=(tx,),
        )
        assert any(i.rule_id == "CBPR-006" for i in check_cbpr_pacs008(msg))

    def test_bah_invalid_bic(self) -> None:
        bah = BusinessApplicationHeader(
            from_bic="BAD", to_bic="NWBKGB2L", business_message_id="B",
            message_definition="pacs.008.001.08", creation_datetime="2026-06-08T09:30:00Z",
            business_service="swift.cbprplus.02",
        )
        assert any(i.rule_id == "CBPR-006" for i in check_cbpr_bah(bah))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


class TestAmountValidationEdges:
    def test_non_decimal_string(self) -> None:
        from kotoba_iso20022 import validate_amount
        from kotoba_iso20022.validate import InvalidAmount
        with pytest.raises(InvalidAmount):
            validate_amount("not-a-number", "USD")

    def test_nan(self) -> None:
        from kotoba_iso20022 import validate_amount
        from kotoba_iso20022.validate import InvalidAmount
        with pytest.raises(InvalidAmount):
            validate_amount(Decimal("NaN"), "USD")

    def test_infinity(self) -> None:
        from kotoba_iso20022 import validate_amount
        from kotoba_iso20022.validate import InvalidAmount
        with pytest.raises(InvalidAmount):
            validate_amount(Decimal("Infinity"), "USD")


class TestCamt053Bridge:
    def test_statement_entries_bridged(self) -> None:
        entry = StatementEntry(
            amount=Amount(Decimal("9.00"), "EUR"), credit_debit="CRDT", status="BOOK",
            end_to_end_id="E2E-S",
        )
        msg = BankToCustomerStatement(
            group_header=GroupHeader("CS", "2026-06-08T23:00:00Z", 0),
            statements=(
                AccountStatement("S", "2026-06-08T23:00:00Z",
                                 Account(iban="DE89370400440532013000"), (), (entry,)),
            ),
        )
        recs = ingress_attestations(msg, ingested_at="2026-06-08T23:10:00Z")
        assert recs[0]["reportedBy"] == "camt.053"
        assert recs[0]["amount"] == "9.00"


class TestConformanceMissingFields:
    def test_missing_amount_and_debtor(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E", uetr=new_uetr(),
            interbank_amount=None,            # CBPR-004
            creditor=Party("B"), creditor_agent=Agent(bicfi="NWBKGB2L"),
            debtor=None, debtor_agent=None,   # CBPR-006 + CBPR-009
        )
        msg = FIToFICustomerCreditTransfer(
            group_header=GroupHeader("M", "2026-06-08T09:30:00Z", 1, settlement_method="CLRG"),
            transactions=(tx,),
        )
        ids = {i.rule_id for i in check_cbpr_pacs008(msg)}
        assert {"CBPR-004", "CBPR-006", "CBPR-009"} <= ids


class TestHelpers:
    def test_new_uetr_is_valid(self) -> None:
        assert is_uetr(new_uetr())

    def test_new_uetr_unique(self) -> None:
        assert new_uetr() != new_uetr()

    def test_control_sum(self) -> None:
        txs = (
            CreditTransferTransaction(end_to_end_id="1", interbank_amount=Amount(Decimal("1.50"), "EUR")),
            CreditTransferTransaction(end_to_end_id="2", instructed_amount=Amount(Decimal("2.50"), "EUR")),
            CreditTransferTransaction(end_to_end_id="3"),  # no amount → 0
        )
        assert control_sum_of(txs) == Decimal("4.00")

    def test_generated_pacs008_header_is_cbpr_clean(self) -> None:
        tx = CreditTransferTransaction(
            end_to_end_id="E", uetr=new_uetr(),
            interbank_amount=Amount(Decimal("1000.00"), "EUR"), charge_bearer="SHAR",
            debtor=Party("A"), debtor_agent=Agent(bicfi="DEUTDEFF"),
            creditor=Party("B"), creditor_agent=Agent(bicfi="NWBKGB2L"),
        )
        msg = FIToFICustomerCreditTransfer(
            group_header=pacs008_group_header("M", "2026-06-08T09:30:00Z", (tx,)),
            transactions=(tx,),
        )
        # NbOfTxs + CtrlSum derived → no CBPR-001/008 findings
        ids = {i.rule_id for i in check_cbpr_pacs008(msg)}
        assert "CBPR-001" not in ids and "CBPR-008" not in ids
