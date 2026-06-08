"""CBPR+ Usage-Guideline conformance checks (the rulebook over the grammar).

The codec in :mod:`kotoba_iso20022.codec` implements the *base ISO 20022*
message grammar. SWIFT's **CBPR+** programme layers a Usage Guideline of
additional constraints on top of that grammar — a base-schema-valid
``pacs.008`` can still be a non-conformant CBPR+ message. This module is the
cleanroom implementation of those published rules, so a kawase corridor can
check an inbound/outbound message before it ever reaches the wire.

Rules implemented (each carries a stable ``rule_id``), from the public
CBPR+ Usage Guidelines for ``pacs.008.001.08`` and the BAH:

- ``CBPR-001`` GrpHdr/NbOfTxs must equal the actual CdtTrfTxInf count.
- ``CBPR-002`` UETR is mandatory on every transaction.
- ``CBPR-003`` UETR must be a lowercase UUIDv4.
- ``CBPR-004`` IntrBkSttlmAmt mandatory, with a valid ISO 4217 amount.
- ``CBPR-005`` ChrgBr ∈ {DEBT, CRED, SHAR} (SLEV is SEPA, not CBPR+).
- ``CBPR-006`` DbtrAgt and CdtrAgt each require a valid BICFI.
- ``CBPR-007`` if an Agent BICFI is present, its Name is not allowed.
- ``CBPR-008`` CtrlSum, if present, must equal the sum of settlement amounts.
- ``CBPR-009`` Debtor and Creditor names are mandatory.
- ``CBPR-010`` BAH MsgDefIdr must match the message definition.
- ``CBPR-011`` BAH BizSvc should be a ``swift.cbprplus.*`` service (warning).

This is a *non-adjudicating* deterministic checker: it reports findings, it
does not move money, sign, or transact (kawase G2/G13 stay with the gated
ingress cell). No proprietary SWIFT validator is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from .model import (
    Agent,
    BusinessApplicationHeader,
    CreditTransferTransaction,
    FIToFICustomerCreditTransfer,
)
from .validate import (
    Iso20022ValidationError,
    is_uetr,
    validate_amount,
    validate_bic,
)

__all__ = (
    "Severity",
    "ConformanceIssue",
    "CbprConformanceError",
    "CBPR_CHARGE_BEARERS",
    "check_cbpr_pacs008",
    "check_cbpr_bah",
    "assert_cbpr_pacs008",
)

Severity = Literal["error", "warning"]

# CBPR+ permits only these charge-bearer codes (SLEV is SEPA-only).
CBPR_CHARGE_BEARERS: frozenset[str] = frozenset({"DEBT", "CRED", "SHAR"})


@dataclass(frozen=True)
class ConformanceIssue:
    """One CBPR+ finding. ``location`` points at the offending element."""

    rule_id: str
    severity: Severity
    location: str
    message: str


class CbprConformanceError(ValueError):
    """Raised by :func:`assert_cbpr_pacs008` when error-level issues exist."""

    def __init__(self, issues: list[ConformanceIssue]) -> None:
        self.issues = issues
        super().__init__(
            f"{len(issues)} CBPR+ error(s): "
            + "; ".join(f"{i.rule_id}@{i.location}: {i.message}" for i in issues)
        )


def _agent_issues(agent: Agent | None, where: str) -> list[ConformanceIssue]:
    out: list[ConformanceIssue] = []
    if agent is None or not agent.bicfi:
        out.append(ConformanceIssue("CBPR-006", "error", where, "Agent BICFI required"))
        return out
    try:
        validate_bic(agent.bicfi)
    except Iso20022ValidationError as exc:
        out.append(ConformanceIssue("CBPR-006", "error", where, str(exc)))
    if agent.name:
        out.append(
            ConformanceIssue(
                "CBPR-007", "error", where, "Agent Name not allowed when BICFI present"
            )
        )
    return out


def _tx_issues(tx: CreditTransferTransaction, idx: int) -> list[ConformanceIssue]:
    loc = f"CdtTrfTxInf[{idx}]"
    out: list[ConformanceIssue] = []

    if not tx.uetr:
        out.append(ConformanceIssue("CBPR-002", "error", f"{loc}/PmtId", "UETR is mandatory"))
    elif not is_uetr(tx.uetr):
        out.append(
            ConformanceIssue("CBPR-003", "error", f"{loc}/PmtId/UETR", "UETR must be UUIDv4")
        )

    if tx.interbank_amount is None:
        out.append(ConformanceIssue("CBPR-004", "error", loc, "IntrBkSttlmAmt required"))
    else:
        try:
            validate_amount(tx.interbank_amount.value, tx.interbank_amount.currency)
        except Iso20022ValidationError as exc:
            out.append(ConformanceIssue("CBPR-004", "error", f"{loc}/IntrBkSttlmAmt", str(exc)))

    if tx.charge_bearer is not None and tx.charge_bearer not in CBPR_CHARGE_BEARERS:
        out.append(
            ConformanceIssue(
                "CBPR-005", "error", f"{loc}/ChrgBr",
                f"ChrgBr {tx.charge_bearer!r} not in CBPR+ {sorted(CBPR_CHARGE_BEARERS)}",
            )
        )

    out += _agent_issues(tx.debtor_agent, f"{loc}/DbtrAgt")
    out += _agent_issues(tx.creditor_agent, f"{loc}/CdtrAgt")

    if tx.debtor is None or not tx.debtor.name:
        out.append(ConformanceIssue("CBPR-009", "error", f"{loc}/Dbtr", "Debtor name required"))
    if tx.creditor is None or not tx.creditor.name:
        out.append(ConformanceIssue("CBPR-009", "error", f"{loc}/Cdtr", "Creditor name required"))

    return out


def check_cbpr_pacs008(msg: FIToFICustomerCreditTransfer) -> list[ConformanceIssue]:
    """Return all CBPR+ Usage-Guideline findings for a pacs.008 message."""
    out: list[ConformanceIssue] = []

    actual = len(msg.transactions)
    if msg.group_header.number_of_txs != actual:
        out.append(
            ConformanceIssue(
                "CBPR-001", "error", "GrpHdr/NbOfTxs",
                f"NbOfTxs={msg.group_header.number_of_txs} != {actual} transactions",
            )
        )

    for idx, tx in enumerate(msg.transactions):
        out += _tx_issues(tx, idx)

    if msg.group_header.control_sum is not None:
        total = sum(
            (tx.interbank_amount.value for tx in msg.transactions if tx.interbank_amount),
            Decimal("0"),
        )
        if total != msg.group_header.control_sum:
            out.append(
                ConformanceIssue(
                    "CBPR-008", "error", "GrpHdr/CtrlSum",
                    f"CtrlSum={msg.group_header.control_sum} != sum {total}",
                )
            )

    return out


def check_cbpr_bah(
    bah: BusinessApplicationHeader, msg_definition: str | None = None
) -> list[ConformanceIssue]:
    """Return CBPR+ findings for a Business Application Header."""
    out: list[ConformanceIssue] = []
    for bic, where in ((bah.from_bic, "AppHdr/Fr"), (bah.to_bic, "AppHdr/To")):
        try:
            validate_bic(bic)
        except Iso20022ValidationError as exc:
            out.append(ConformanceIssue("CBPR-006", "error", where, str(exc)))
    if msg_definition is not None and bah.message_definition != msg_definition:
        out.append(
            ConformanceIssue(
                "CBPR-010", "error", "AppHdr/MsgDefIdr",
                f"MsgDefIdr {bah.message_definition!r} != {msg_definition!r}",
            )
        )
    if not (bah.business_service or "").startswith("swift.cbprplus."):
        out.append(
            ConformanceIssue(
                "CBPR-011", "warning", "AppHdr/BizSvc",
                "BizSvc should be a swift.cbprplus.* service for CBPR+",
            )
        )
    return out


def assert_cbpr_pacs008(msg: FIToFICustomerCreditTransfer) -> None:
    """Raise :class:`CbprConformanceError` if any error-level issue exists."""
    errors = [i for i in check_cbpr_pacs008(msg) if i.severity == "error"]
    if errors:
        raise CbprConformanceError(errors)
