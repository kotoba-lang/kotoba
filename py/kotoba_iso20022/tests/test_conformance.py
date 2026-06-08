"""Tests for the CBPR+ Usage-Guideline conformance checker."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    CbprConformanceError,
    assert_cbpr_pacs008,
    check_cbpr_bah,
    check_cbpr_pacs008,
    validate_uetr,
)
from kotoba_iso20022.model import (
    Agent,
    Amount,
    BusinessApplicationHeader,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    GroupHeader,
    Party,
)
from kotoba_iso20022.validate import InvalidUetr, is_uetr

GOOD_UETR = "dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e"


def _good_tx(**over) -> CreditTransferTransaction:
    base = {
        "end_to_end_id": "E2E-1",
        "uetr": GOOD_UETR,
        "interbank_amount": Amount(Decimal("1000.00"), "EUR"),
        "charge_bearer": "SHAR",
        "debtor": Party("Alice Cohen"),
        "debtor_agent": Agent(bicfi="DEUTDEFF"),
        "creditor": Party("Bob Levi"),
        "creditor_agent": Agent(bicfi="NWBKGB2L"),
    }
    base.update(over)
    return CreditTransferTransaction(**base)


def _msg(tx: CreditTransferTransaction, *, nb: int = 1, ctrl=None) -> FIToFICustomerCreditTransfer:
    return FIToFICustomerCreditTransfer(
        group_header=GroupHeader("M", "2026-06-08T09:30:00Z", nb, control_sum=ctrl,
                                 settlement_method="CLRG"),
        transactions=(tx,),
    )


class TestUetr:
    def test_valid(self) -> None:
        assert is_uetr(GOOD_UETR)
        assert validate_uetr(GOOD_UETR) == GOOD_UETR

    @pytest.mark.parametrize("bad", [
        "DCED6A36-9E4B-4E2A-8B9F-2F3A4B5C6D7E",  # uppercase
        "dced6a36-9e4b-1e2a-8b9f-2f3a4b5c6d7e",  # version nibble != 4
        "dced6a36-9e4b-4e2a-7b9f-2f3a4b5c6d7e",  # variant nibble bad
        "not-a-uuid",
    ])
    def test_invalid(self, bad: str) -> None:
        assert not is_uetr(bad)
        with pytest.raises(InvalidUetr):
            validate_uetr(bad)


class TestPacs008Conformance:
    def test_clean_message_has_no_issues(self) -> None:
        assert check_cbpr_pacs008(_msg(_good_tx(), ctrl=Decimal("1000.00"))) == []

    def test_missing_uetr(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(uetr=None)))
        assert any(i.rule_id == "CBPR-002" for i in issues)

    def test_bad_uetr_format(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(uetr="not-a-uuid")))
        assert any(i.rule_id == "CBPR-003" for i in issues)

    def test_slev_charge_bearer_rejected(self) -> None:
        # SLEV is SEPA, not CBPR+
        issues = check_cbpr_pacs008(_msg(_good_tx(charge_bearer="SLEV")))
        assert any(i.rule_id == "CBPR-005" for i in issues)

    def test_missing_creditor_agent_bic(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(creditor_agent=None)))
        assert any(i.rule_id == "CBPR-006" and "CdtrAgt" in i.location for i in issues)

    def test_agent_name_with_bic_rejected(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(debtor_agent=Agent(bicfi="DEUTDEFF", name="DB"))))
        assert any(i.rule_id == "CBPR-007" for i in issues)

    def test_nboftxs_mismatch(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(), nb=5))
        assert any(i.rule_id == "CBPR-001" for i in issues)

    def test_control_sum_mismatch(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(), ctrl=Decimal("999.99")))
        assert any(i.rule_id == "CBPR-008" for i in issues)

    def test_missing_creditor_name(self) -> None:
        issues = check_cbpr_pacs008(_msg(_good_tx(creditor=Party(""))))
        assert any(i.rule_id == "CBPR-009" for i in issues)

    def test_assert_raises_on_error(self) -> None:
        with pytest.raises(CbprConformanceError):
            assert_cbpr_pacs008(_msg(_good_tx(uetr=None)))

    def test_assert_passes_clean(self) -> None:
        assert_cbpr_pacs008(_msg(_good_tx(), ctrl=Decimal("1000.00")))  # no raise


class TestBahConformance:
    def test_clean(self) -> None:
        bah = BusinessApplicationHeader(
            from_bic="DEUTDEFF", to_bic="NWBKGB2L", business_message_id="B",
            message_definition="pacs.008.001.08", creation_datetime="2026-06-08T09:30:00Z",
            business_service="swift.cbprplus.02",
        )
        assert check_cbpr_bah(bah, "pacs.008.001.08") == []

    def test_msgdef_mismatch_and_bizsvc_warning(self) -> None:
        bah = BusinessApplicationHeader(
            from_bic="DEUTDEFF", to_bic="NWBKGB2L", business_message_id="B",
            message_definition="pain.001.001.09", creation_datetime="2026-06-08T09:30:00Z",
            business_service=None,
        )
        issues = check_cbpr_bah(bah, "pacs.008.001.08")
        assert any(i.rule_id == "CBPR-010" for i in issues)
        assert any(i.rule_id == "CBPR-011" and i.severity == "warning" for i in issues)
