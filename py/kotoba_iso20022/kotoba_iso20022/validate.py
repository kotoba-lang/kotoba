"""Cleanroom validators for the open identifier standards ISO 20022 reuses.

Every routine here is implemented purely from the *published* algorithm in
the relevant open ISO standard — no proprietary SWIFT SDK, no vendor
reference code (Charter Rider §2(c)/§2(e); the same cleanroom discipline
warifu applied to ISO 8583 in ``50-infra/warifu-gateway``).

Standards implemented:

- **IBAN** — ISO 13616 (check digits = ISO 7064 MOD 97-10).
- **BIC**  — ISO 9362 (8- or 11-character business identifier code).
- **Currency** — ISO 4217 alphabetic code shape + active-code membership.
- **Amount** — ISO 20022 ``ActiveCurrencyAndAmount`` lexical constraints
  (total digits ≤ 18, fraction digits ≤ 5, non-negative).

These are *facts of an open standard*, not copyrightable expression, so a
clean reimplementation is charter-clean.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

__all__ = (
    "InvalidIban",
    "InvalidBic",
    "InvalidCurrency",
    "InvalidAmount",
    "InvalidUetr",
    "validate_iban",
    "validate_bic",
    "validate_currency",
    "validate_amount",
    "validate_uetr",
    "is_uetr",
    "iban_check_digits",
    "ISO4217_ACTIVE",
)


class Iso20022ValidationError(ValueError):
    """Base class for every validator failure in this module."""


class InvalidIban(Iso20022ValidationError):
    """IBAN fails ISO 13616 structure or ISO 7064 MOD 97-10 check."""


class InvalidBic(Iso20022ValidationError):
    """BIC fails ISO 9362 structure."""


class InvalidCurrency(Iso20022ValidationError):
    """Currency code fails ISO 4217 shape or active-membership check."""


class InvalidAmount(Iso20022ValidationError):
    """Amount violates ISO 20022 ActiveCurrencyAndAmount constraints."""


class InvalidUetr(Iso20022ValidationError):
    """UETR is not a lowercase UUIDv4 (CBPR+ requirement)."""


# --------------------------------------------------------------------------
# ISO 13616 — IBAN
# --------------------------------------------------------------------------

# ISO 13616 fixed national IBAN lengths, from the official SWIFT IBAN
# Registry. An unknown country code is structure-checked but length-skipped
# (a soft pass) so the codec never hard-rejects a valid-but-unlisted country.
# `0` marks a country that does not participate in IBAN (e.g. JP/US).
IBAN_LENGTHS: dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18,
    "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24,
    "ME": 22, "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22,
    "SA": 24, "SC": 31, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "ST": 25,
    "SV": 28, "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24,
    "XK": 20,
    "JP": 0, "US": 0,  # do not participate in IBAN
}

_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")


def _iban_mod97(rearranged: str) -> int:
    """ISO 7064 MOD 97-10 over the letter-expanded IBAN string.

    Letters A..Z expand to 10..35; the integer is reduced mod 97 in
    chunks to avoid building an arbitrarily large int.
    """
    total = 0
    for ch in rearranged:
        if ch.isdigit():
            total = (total * 10 + (ord(ch) - 48)) % 97
        else:  # 'A'..'Z' -> 10..35, two decimal digits
            total = (total * 100 + (ord(ch) - 55)) % 97
    return total


def normalize_iban(iban: str) -> str:
    """Strip spaces and uppercase — the canonical electronic IBAN form."""
    return re.sub(r"\s+", "", iban).upper()


def iban_check_digits(country: str, bban: str) -> str:
    """Compute the ISO 13616 two-digit check for ``country`` + ``bban``.

    Useful for constructing test vectors and for emitting outbound IBANs.
    """
    country = country.upper()
    bban = bban.upper()
    rearranged = bban + country + "00"
    remainder = _iban_mod97(rearranged)
    check = 98 - remainder
    return f"{check:02d}"


def validate_iban(iban: str) -> str:
    """Validate ``iban`` and return its normalized electronic form.

    Raises :class:`InvalidIban` on any structural or checksum failure.
    """
    norm = normalize_iban(iban)
    if not _IBAN_RE.match(norm):
        raise InvalidIban(f"IBAN structure invalid (ISO 13616): {iban!r}")
    country = norm[:2]
    expected = IBAN_LENGTHS.get(country)
    if expected == 0:
        raise InvalidIban(f"country {country} does not participate in IBAN")
    if expected is not None and len(norm) != expected:
        raise InvalidIban(
            f"IBAN length {len(norm)} != {expected} for {country} (ISO 13616)"
        )
    rearranged = norm[4:] + norm[:4]
    if _iban_mod97(rearranged) != 1:
        raise InvalidIban(f"IBAN MOD 97-10 check failed (ISO 7064): {iban!r}")
    return norm


# --------------------------------------------------------------------------
# ISO 9362 — BIC
# --------------------------------------------------------------------------

# 4 alpha institution + 2 alpha ISO-3166 country + 2 alnum location
# (+ optional 3 alnum branch). A location ending in '0' is a test BIC;
# '1' is a passive participant; '2' a reverse-billing connection.
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def validate_bic(bic: str) -> str:
    """Validate an ISO 9362 BIC (BICFI), returning its uppercase form."""
    norm = bic.strip().upper()
    if len(norm) not in (8, 11):
        raise InvalidBic(f"BIC must be 8 or 11 chars (ISO 9362): {bic!r}")
    if not _BIC_RE.match(norm):
        raise InvalidBic(f"BIC structure invalid (ISO 9362): {bic!r}")
    return norm


# --------------------------------------------------------------------------
# ISO 4217 — currency
# --------------------------------------------------------------------------

# Active ISO 4217 alphabetic codes. Scoped to the kawase-yui settlement
# corridor (USD/EUR/JPY/GBP/CHF/KRW) plus common reach currencies; the
# shape check below is the structural gate, this set the membership gate.
ISO4217_ACTIVE: frozenset[str] = frozenset(
    {
        "USD", "EUR", "JPY", "GBP", "CHF", "KRW", "CAD", "AUD", "NZD",
        "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "SGD", "HKD", "CNY",
        "INR", "BRL", "MXN", "ZAR", "AED", "SAR", "TRY", "THB", "IDR",
        "PHP", "MYR", "TWD", "ILS",
    }
)

_CCY_RE = re.compile(r"^[A-Z]{3}$")


def validate_currency(ccy: str, *, require_active: bool = True) -> str:
    """Validate an ISO 4217 alphabetic currency code."""
    norm = ccy.strip().upper()
    if not _CCY_RE.match(norm):
        raise InvalidCurrency(f"currency must be 3 letters (ISO 4217): {ccy!r}")
    if require_active and norm not in ISO4217_ACTIVE:
        raise InvalidCurrency(f"currency {norm} not in active ISO 4217 set")
    return norm


# --------------------------------------------------------------------------
# ISO 20022 — ActiveCurrencyAndAmount lexical constraints
# --------------------------------------------------------------------------

# ISO 20022 currency-amount fraction digits per ISO 4217 minor unit. Default
# 2; the exceptions are the codec's amount-formatting authority.
CCY_FRACTION_DIGITS: dict[str, int] = {
    "JPY": 0, "KRW": 0, "CLP": 0, "ISK": 0, "HUF": 2,
    "BHD": 3, "KWD": 3, "OMR": 3, "TND": 3,
}

_MAX_TOTAL_DIGITS = 18
_MAX_FRACTION_DIGITS = 5


def validate_amount(value: Decimal | str, ccy: str) -> Decimal:
    """Validate an ISO 20022 ``ActiveCurrencyAndAmount`` value for ``ccy``.

    Enforces: non-negative, total significant digits ≤ 18, fraction digits
    ≤ 5 and ≤ the ISO 4217 minor-unit digits for the currency.
    """
    norm_ccy = validate_currency(ccy, require_active=False)
    try:
        dec = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidAmount(f"amount not a decimal: {value!r}") from exc
    if dec.is_nan() or dec.is_infinite():
        raise InvalidAmount(f"amount not finite: {value!r}")
    if dec < 0:
        raise InvalidAmount(f"amount must be non-negative: {value!r}")
    sign, digits, exponent = dec.as_tuple()
    # exponent is a special str ('n'/'N'/'F') only for NaN/Infinity, both
    # already rejected above; narrow to int for the arithmetic below.
    assert isinstance(exponent, int)
    frac = -exponent if exponent < 0 else 0
    if frac > _MAX_FRACTION_DIGITS:
        raise InvalidAmount(
            f"fraction digits {frac} > {_MAX_FRACTION_DIGITS} (ISO 20022)"
        )
    allowed_frac = CCY_FRACTION_DIGITS.get(norm_ccy, 2)
    if frac > allowed_frac:
        raise InvalidAmount(
            f"{norm_ccy} permits {allowed_frac} fraction digits, got {frac}"
        )
    if len(digits) > _MAX_TOTAL_DIGITS:
        raise InvalidAmount(
            f"total digits {len(digits)} > {_MAX_TOTAL_DIGITS} (ISO 20022)"
        )
    return dec


# --------------------------------------------------------------------------
# UETR — Unique End-to-End Transaction Reference (CBPR+ requires UUIDv4)
# --------------------------------------------------------------------------

# UUID version 4, lowercase: 8-4-4-4-12 hex with version nibble '4' and
# variant nibble in {8,9,a,b}. CBPR+ mandates the UETR be a UUIDv4 and it
# must remain unchanged across the entire payment chain.
_UETR_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_uetr(uetr: str) -> bool:
    """Return whether ``uetr`` is a lowercase UUIDv4 (CBPR+ UETR)."""
    return bool(_UETR_RE.match(uetr))


def validate_uetr(uetr: str) -> str:
    """Validate a CBPR+ UETR (lowercase UUIDv4), returning it unchanged."""
    if not is_uetr(uetr):
        raise InvalidUetr(f"UETR must be a lowercase UUIDv4 (CBPR+): {uetr!r}")
    return uetr
