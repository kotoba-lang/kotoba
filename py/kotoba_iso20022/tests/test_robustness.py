"""Breadth/robustness tests: full IBAN registry, cross-currency round-trips.

These exercise the codec/validators across the *range* of valid inputs,
not just one happy path — the maturity complement to the edge-case suite.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from kotoba_iso20022 import build_pacs008, pacs008_group_header, parse_pacs008
from kotoba_iso20022.model import (
    Agent,
    Amount,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
    Party,
)
from kotoba_iso20022.validate import (
    IBAN_LENGTHS,
    iban_check_digits,
    validate_amount,
    validate_iban,
)

# --------------------------------------------------------------------------
# Full ISO 13616 registry: a valid IBAN can be constructed + validated for
# every listed participating country.
# --------------------------------------------------------------------------

_PARTICIPATING = [c for c, n in IBAN_LENGTHS.items() if n > 0]


@pytest.mark.parametrize("country", _PARTICIPATING)
def test_constructed_iban_validates(country: str) -> None:
    length = IBAN_LENGTHS[country]
    # numeric BBAN of the right width (digits are valid BBAN chars everywhere)
    bban = ("1234567890" * 4)[: length - 4]
    check = iban_check_digits(country, bban)
    iban = country + check + bban
    assert validate_iban(iban) == iban
    assert len(iban) == length


def test_registry_is_substantial() -> None:
    # guard against an accidental truncation of the registry
    assert len(_PARTICIPATING) >= 75


def test_unlisted_country_soft_passes_structure() -> None:
    # a structurally-valid IBAN for a country not in the registry is accepted
    # on structure + checksum (length check skipped), never hard-rejected
    bban = "ABCD1234567890123456"
    check = iban_check_digits("ZZ", bban)
    assert validate_iban("ZZ" + check + bban)


# --------------------------------------------------------------------------
# Cross-currency round-trips with correct ISO 4217 minor-unit formatting.
# --------------------------------------------------------------------------

_CURRENCY_CASES = [
    ("USD", "1000.00"),
    ("EUR", "0.01"),
    ("GBP", "999999.99"),
    ("CHF", "12.50"),
    ("JPY", "500000"),      # 0 fraction digits
    ("KRW", "1000000"),     # 0 fraction digits
    ("BHD", "1.234"),       # 3 fraction digits
    ("KWD", "0.500"),       # 3 fraction digits
]


@pytest.mark.parametrize("ccy,amount", _CURRENCY_CASES)
def test_pacs008_amount_roundtrip(ccy: str, amount: str) -> None:
    tx = CreditTransferTransaction(
        end_to_end_id="E2E",
        interbank_amount=Amount(Decimal(amount), ccy),
        debtor=Party("A"), debtor_agent=Agent(bicfi="DEUTDEFF"),
        creditor=Party("B"), creditor_agent=Agent(bicfi="NWBKGB2L"),
    )
    msg = FIToFICustomerCreditTransfer(
        group_header=pacs008_group_header("M", "2026-06-08T09:30:00Z", (tx,)),
        transactions=(tx,),
    )
    back = parse_pacs008(build_pacs008(msg))
    rt = back.transactions[0].interbank_amount
    assert rt.currency == ccy
    assert rt.value == Decimal(amount)


@pytest.mark.parametrize("ccy,amount", _CURRENCY_CASES)
def test_amounts_validate(ccy: str, amount: str) -> None:
    assert validate_amount(amount, ccy) == Decimal(amount)


def test_max_total_digits_boundary() -> None:
    # exactly 18 significant digits is allowed; 19 is rejected
    assert validate_amount("123456789012345.67", "USD")  # 17 digits, ok
    from kotoba_iso20022.validate import InvalidAmount
    with pytest.raises(InvalidAmount):
        validate_amount("12345678901234567.89", "USD")  # 19 digits


def test_many_transactions_in_one_message() -> None:
    txs = tuple(
        CreditTransferTransaction(
            end_to_end_id=f"E2E-{i}",
            interbank_amount=Amount(Decimal("1.00"), "EUR"),
            debtor=Party("A"), debtor_agent=Agent(bicfi="DEUTDEFF"),
            creditor=Party(f"C{i}"), creditor_agent=Agent(bicfi="NWBKGB2L"),
        )
        for i in range(25)
    )
    msg = FIToFICustomerCreditTransfer(
        group_header=pacs008_group_header("M", "2026-06-08T09:30:00Z", txs),
        transactions=txs,
    )
    back = parse_pacs008(build_pacs008(msg))
    assert len(back.transactions) == 25
    assert back.group_header.control_sum == Decimal("25.00")
    assert {t.end_to_end_id for t in back.transactions} == {f"E2E-{i}" for i in range(25)}
