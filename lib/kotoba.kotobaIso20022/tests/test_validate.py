"""Tests for the cleanroom open-standard validators."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kotoba_iso20022.validate import (
    InvalidAmount,
    InvalidBic,
    InvalidCurrency,
    InvalidIban,
    iban_check_digits,
    validate_amount,
    validate_bic,
    validate_currency,
    validate_iban,
)


class TestIban:
    # Published ISO 13616 example IBANs (registry test vectors).
    VALID = [
        "DE89 3704 0044 0532 0130 00",
        "GB29 NWBK 6016 1331 9268 19",
        "FR14 2004 1010 0505 0001 3M02 606",
        "CH93 0076 2011 6238 5295 7",
        "BE68 5390 0754 7034",
    ]

    @pytest.mark.parametrize("iban", VALID)
    def test_valid(self, iban: str) -> None:
        out = validate_iban(iban)
        assert " " not in out and out == out.upper()

    def test_bad_checksum(self) -> None:
        # flip a digit in the German example
        with pytest.raises(InvalidIban):
            validate_iban("DE90 3704 0044 0532 0130 00")

    def test_wrong_length(self) -> None:
        with pytest.raises(InvalidIban):
            validate_iban("DE89 3704 0044 0532 0130")

    def test_bad_structure(self) -> None:
        with pytest.raises(InvalidIban):
            validate_iban("XX")

    def test_jp_has_no_iban(self) -> None:
        with pytest.raises(InvalidIban):
            validate_iban("JP00 0000 0000 0000 0000 00")

    def test_check_digits_roundtrip(self) -> None:
        # DE BBAN from the canonical example
        cd = iban_check_digits("DE", "370400440532013000")
        assert cd == "89"
        assert validate_iban("DE" + cd + "370400440532013000")


class TestBic:
    @pytest.mark.parametrize("bic", ["DEUTDEFF", "DEUTDEFF500", "NWBKGB2L", "BOFAUS3N"])
    def test_valid(self, bic: str) -> None:
        assert validate_bic(bic) == bic.upper()

    @pytest.mark.parametrize("bic", ["DEUT", "DEUTDEFF5", "1234DEFF", "deutde"])
    def test_invalid(self, bic: str) -> None:
        with pytest.raises(InvalidBic):
            validate_bic(bic)


class TestCurrency:
    def test_valid_active(self) -> None:
        assert validate_currency("usd") == "USD"

    def test_shape_only(self) -> None:
        assert validate_currency("XYZ", require_active=False) == "XYZ"

    def test_inactive_rejected(self) -> None:
        with pytest.raises(InvalidCurrency):
            validate_currency("XYZ")

    def test_bad_shape(self) -> None:
        with pytest.raises(InvalidCurrency):
            validate_currency("US")


class TestAmount:
    def test_eur_two_dp(self) -> None:
        assert validate_amount("100.00", "EUR") == Decimal("100.00")

    def test_jpy_zero_dp(self) -> None:
        assert validate_amount("1000", "JPY") == Decimal("1000")

    def test_jpy_rejects_fraction(self) -> None:
        with pytest.raises(InvalidAmount):
            validate_amount("1000.50", "JPY")

    def test_too_many_fraction_digits(self) -> None:
        with pytest.raises(InvalidAmount):
            validate_amount("1.000000", "USD")

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidAmount):
            validate_amount("-1.00", "USD")

    def test_total_digits_cap(self) -> None:
        with pytest.raises(InvalidAmount):
            validate_amount("1234567890123456789", "USD")
