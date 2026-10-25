"""kotoba_iso20022 — cleanroom ISO 20022 payment-message codec.

A dependency-free, charter-clean reimplementation of the three ISO 20022
message definitions the kawase-yui (為替結) cross-border actor needs at its
interop/ingress boundary, built purely from the *open published* standard
(no proprietary SWIFT SDK) — the same cleanroom posture warifu applied to
ISO 8583.

Why this exists: kawase-yui settles adherent-to-adherent over Base L2
stablecoins, but a member on/off-ramps through the real banking system,
which speaks ISO 20022 (the format SWIFT itself migrated to via CBPR+).
This module is the *traditional-finance ingress/interop wire* — it
translates between ISO 20022 XML and kotoba EAVT Datoms so a real bank
transfer becomes auditable, append-only kotoba history.

Boundaries (CRITICAL): this is a *format library* only. It does not open a
network connection, does not touch a chain, does not move money, does not
perform Travel-Rule / FATF passport KYC (the Adherent SBT remains the KYC
per kawase-yui G10). It is datafication of an open standard.

Public surface::

    from kotoba_iso20022 import (
        build_pacs008, parse_pacs008,
        build_pain001, parse_pain001,
        build_pacs002, parse_pacs002,
        to_datoms,
        validate_iban, validate_bic, validate_currency, validate_amount,
    )

Message definitions (version-parameterised; CBPR+/SEPA defaults):

- pain.001 — CustomerCreditTransferInitiation
- pacs.008 — FIToFICustomerCreditTransfer
- pacs.002 — FIToFIPaymentStatusReport
"""

from __future__ import annotations

from .bah import (
    build_bah,
    build_business_message,
    parse_bah,
    parse_business_message,
)
from .bridge import LEXICON_VERSION, RECORD_TYPE, ingress_attestations
from .codec import (
    DEFAULT_VERSIONS,
    Iso20022CodecError,
    build_camt053,
    build_camt054,
    build_pacs002,
    build_pacs004,
    build_pacs008,
    build_pain001,
    build_pain002,
    parse_camt053,
    parse_camt054,
    parse_pacs002,
    parse_pacs004,
    parse_pacs008,
    parse_pain001,
    parse_pain002,
    urn_for,
)
from .conformance import (
    CbprConformanceError,
    ConformanceIssue,
    assert_cbpr_pacs008,
    check_cbpr_bah,
    check_cbpr_pacs008,
)
from .datoms import NS, Datom, to_datoms, tx_entity_of
from .helpers import (
    control_sum_of,
    new_uetr,
    pacs008_group_header,
    pain001_group_header,
)
from .validate import (
    InvalidAmount,
    InvalidBic,
    InvalidCurrency,
    InvalidIban,
    InvalidUetr,
    validate_amount,
    validate_bic,
    validate_currency,
    validate_iban,
    validate_uetr,
)

__all__ = (
    # codec
    "build_pain001",
    "parse_pain001",
    "build_pacs008",
    "parse_pacs008",
    "build_pacs002",
    "parse_pacs002",
    "build_camt053",
    "parse_camt053",
    "build_camt054",
    "parse_camt054",
    "build_pain002",
    "parse_pain002",
    "build_pacs004",
    "parse_pacs004",
    # business application header (head.001) + CBPR+ envelope
    "build_bah",
    "parse_bah",
    "build_business_message",
    "parse_business_message",
    "urn_for",
    "DEFAULT_VERSIONS",
    "Iso20022CodecError",
    # datoms
    "to_datoms",
    "tx_entity_of",
    "Datom",
    "NS",
    # kawase-yui bridge (ingressAttestation Lexicon records)
    "ingress_attestations",
    "RECORD_TYPE",
    "LEXICON_VERSION",
    # construction helpers
    "new_uetr",
    "control_sum_of",
    "pacs008_group_header",
    "pain001_group_header",
    # validators
    "validate_iban",
    "validate_bic",
    "validate_currency",
    "validate_amount",
    "validate_uetr",
    "InvalidIban",
    "InvalidBic",
    "InvalidCurrency",
    "InvalidAmount",
    "InvalidUetr",
    # CBPR+ conformance
    "check_cbpr_pacs008",
    "check_cbpr_bah",
    "assert_cbpr_pacs008",
    "ConformanceIssue",
    "CbprConformanceError",
)

__version__ = "0.1.0"
