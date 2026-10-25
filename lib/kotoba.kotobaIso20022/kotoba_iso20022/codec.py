"""Cleanroom ISO 20022 XML codec — build and parse, round-trip stable.

Implemented purely from the published ISO 20022 message-component
structure (``GrpHdr`` / ``PmtInf`` / ``CdtTrfTxInf`` / ``PmtId`` …) and the
official namespace scheme::

    urn:iso:std:iso:20022:tech:xsd:<msgdef>

e.g. ``urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08``. No proprietary
SWIFT SDK or vendor schema file is used or required at runtime — only the
public element grammar of the open standard (same cleanroom posture as
warifu's ISO 8583 map). Validation of embedded identifiers (IBAN/BIC/
currency/amount) is delegated to :mod:`kotoba_iso20022.validate`.

Supported message definitions (version-parameterised; CBPR+/SEPA defaults):

- pain.001 — CustomerCreditTransferInitiation (default ``pain.001.001.09``)
- pacs.008 — FIToFICustomerCreditTransfer    (default ``pacs.008.001.08``)
- pacs.002 — FIToFIPaymentStatusReport       (default ``pacs.002.001.10``)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from .model import (
    Account,
    AccountNotification,
    AccountStatement,
    Agent,
    Amount,
    BankToCustomerDebitCreditNotification,
    BankToCustomerStatement,
    CashBalance,
    CreditTransferTransaction,
    CustomerCreditTransferInitiation,
    CustomerPaymentStatusReport,
    FIToFICustomerCreditTransfer,
    FIToFIPaymentStatusReport,
    GroupHeader,
    OriginalPaymentStatus,
    Party,
    PaymentInstruction,
    PaymentReturn,
    PaymentReturnTransaction,
    PostalAddress,
    RemittanceInfo,
    StatementEntry,
    TransactionStatus,
)
from .validate import (
    CCY_FRACTION_DIGITS,
    validate_amount,
    validate_bic,
    validate_currency,
    validate_iban,
)

__all__ = (
    "Iso20022CodecError",
    "DEFAULT_VERSIONS",
    "urn_for",
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
)

DEFAULT_VERSIONS: dict[str, str] = {
    "pain.001": "pain.001.001.09",
    "pain.002": "pain.002.001.10",
    "pacs.008": "pacs.008.001.08",
    "pacs.002": "pacs.002.001.10",
    "pacs.004": "pacs.004.001.09",
    "camt.053": "camt.053.001.08",
    "camt.054": "camt.054.001.08",
}

_URN_PREFIX = "urn:iso:std:iso:20022:tech:xsd:"


class Iso20022CodecError(ValueError):
    """Raised on malformed input during build or parse."""


def urn_for(msgdef: str) -> str:
    """Return the official ISO 20022 namespace URN for a message def id."""
    return _URN_PREFIX + msgdef


# --------------------------------------------------------------------------
# small XML helpers (namespace-qualified element construction / lookup)
# --------------------------------------------------------------------------


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _sub(parent: ET.Element, ns: str, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, _q(ns, tag))
    if text is not None:
        el.text = text
    return el


def _find(parent: ET.Element, ns: str, path: str) -> ET.Element | None:
    return parent.find("/".join(_q(ns, t) for t in path.split("/")))


def _findall(parent: ET.Element, ns: str, tag: str) -> list[ET.Element]:
    return parent.findall(_q(ns, tag))


def _text(parent: ET.Element | None, ns: str, path: str) -> str | None:
    if parent is None:
        return None
    el = _find(parent, ns, path)
    return el.text if el is not None else None


def _fmt_amount(amt: Amount) -> str:
    ccy = validate_currency(amt.currency, require_active=False)
    dec = validate_amount(amt.value, ccy)
    digits = CCY_FRACTION_DIGITS.get(ccy, 2)
    return f"{dec:.{digits}f}" if digits else str(int(dec))


def _root(ns: str, container_tag: str) -> tuple[ET.Element, ET.Element]:
    """Build ``<Document xmlns=ns><container_tag>`` and return both."""
    # Register the message namespace as the default (no prefix) so the
    # serialized form is the canonical ISO 20022 ``<Document xmlns="urn:…">``
    # that SWIFT/CBPR+ validators expect, not a ``ns0:`` prefix.
    ET.register_namespace("", ns)
    doc = ET.Element(_q(ns, "Document"))
    container = ET.SubElement(doc, _q(ns, container_tag))
    return doc, container


def _serialize(doc: ET.Element) -> str:
    ET.indent(doc, space="  ")
    return ET.tostring(doc, encoding="unicode", xml_declaration=True)


# --------------------------------------------------------------------------
# shared component builders
# --------------------------------------------------------------------------


def _build_group_header(parent: ET.Element, ns: str, gh: GroupHeader, *, is_pacs: bool) -> None:
    grp = _sub(parent, ns, "GrpHdr")
    _sub(grp, ns, "MsgId", gh.message_id)
    _sub(grp, ns, "CreDtTm", gh.creation_datetime)
    _sub(grp, ns, "NbOfTxs", str(gh.number_of_txs))
    if gh.control_sum is not None:
        _sub(grp, ns, "CtrlSum", str(gh.control_sum))
    if is_pacs:
        sttlm = _sub(grp, ns, "SttlmInf")
        _sub(sttlm, ns, "SttlmMtd", gh.settlement_method or "CLRG")
    elif gh.initiating_party is not None:
        _build_party(grp, ns, "InitgPty", gh.initiating_party)


def _build_party(parent: ET.Element, ns: str, tag: str, party: Party) -> None:
    el = _sub(parent, ns, tag)
    _sub(el, ns, "Nm", party.name)
    if party.postal_address is not None:
        adr = _sub(el, ns, "PstlAdr")
        if party.postal_address.country:
            _sub(adr, ns, "Ctry", party.postal_address.country)
        for line in party.postal_address.address_lines:
            _sub(adr, ns, "AdrLine", line)
    if party.identifier is not None:
        idn = _sub(el, ns, "Id")
        org = _sub(idn, ns, "OrgId")
        oth = _sub(org, ns, "Othr")
        _sub(oth, ns, "Id", party.identifier)


def _build_account(parent: ET.Element, ns: str, tag: str, acct: Account) -> None:
    el = _sub(parent, ns, tag)
    idn = _sub(el, ns, "Id")
    if acct.iban:
        _sub(idn, ns, "IBAN", validate_iban(acct.iban))
    else:
        oth = _sub(idn, ns, "Othr")
        _sub(oth, ns, "Id", acct.other_id or "")
    if acct.currency:
        _sub(el, ns, "Ccy", validate_currency(acct.currency, require_active=False))


def _build_agent(parent: ET.Element, ns: str, tag: str, agent: Agent) -> None:
    el = _sub(parent, ns, tag)
    fin = _sub(el, ns, "FinInstnId")
    if agent.bicfi:
        _sub(fin, ns, "BICFI", validate_bic(agent.bicfi))
    if agent.name:
        _sub(fin, ns, "Nm", agent.name)
    if agent.clearing_member_id:
        clr = _sub(fin, ns, "ClrSysMmbId")
        _sub(clr, ns, "MmbId", agent.clearing_member_id)


def _build_remittance(parent: ET.Element, ns: str, rmt: RemittanceInfo) -> None:
    el = _sub(parent, ns, "RmtInf")
    for line in rmt.unstructured:
        _sub(el, ns, "Ustrd", line)


# --------------------------------------------------------------------------
# shared component parsers
# --------------------------------------------------------------------------


def _parse_amount(el: ET.Element | None) -> Amount | None:
    if el is None or el.text is None:
        return None
    ccy = el.get("Ccy")
    if not ccy:
        raise Iso20022CodecError("amount element missing Ccy attribute")
    return Amount(value=Decimal(el.text), currency=validate_currency(ccy, require_active=False))


def _parse_party(el: ET.Element | None, ns: str) -> Party | None:
    if el is None:
        return None
    name = _text(el, ns, "Nm") or ""
    country = _text(el, ns, "PstlAdr/Ctry")
    adr_el = _find(el, ns, "PstlAdr")
    lines = tuple(
        ln.text
        for ln in (_findall(adr_el, ns, "AdrLine") if adr_el is not None else [])
        if ln.text
    )
    postal = PostalAddress(country=country, address_lines=lines) if (country or lines) else None
    identifier = _text(el, ns, "Id/OrgId/Othr/Id")
    return Party(name=name, postal_address=postal, identifier=identifier)


def _parse_account(el: ET.Element | None, ns: str) -> Account | None:
    if el is None:
        return None
    iban = _text(el, ns, "Id/IBAN")
    other = _text(el, ns, "Id/Othr/Id")
    ccy = _text(el, ns, "Ccy")
    return Account(iban=iban, other_id=other, currency=ccy)


def _parse_agent(el: ET.Element | None, ns: str) -> Agent | None:
    if el is None:
        return None
    return Agent(
        bicfi=_text(el, ns, "FinInstnId/BICFI"),
        name=_text(el, ns, "FinInstnId/Nm"),
        clearing_member_id=_text(el, ns, "FinInstnId/ClrSysMmbId/MmbId"),
    )


def _addtl_info(rsn: ET.Element | None, ns: str) -> tuple[str, ...]:
    """Collect ``AddtlInf`` text lines under a status/return reason element."""
    if rsn is None:
        return ()
    return tuple(a.text for a in _findall(rsn, ns, "AddtlInf") if a.text)


def _parse_remittance(el: ET.Element | None, ns: str) -> RemittanceInfo | None:
    if el is None:
        return None
    return RemittanceInfo(
        unstructured=tuple(u.text for u in _findall(el, ns, "Ustrd") if u.text)
    )


def _parse_group_header(parent: ET.Element, ns: str) -> GroupHeader:
    grp = _find(parent, ns, "GrpHdr")
    if grp is None:
        raise Iso20022CodecError("missing GrpHdr")
    ctrl = _text(grp, ns, "CtrlSum")
    sttlm = _text(grp, ns, "SttlmInf/SttlmMtd")
    return GroupHeader(
        message_id=_text(grp, ns, "MsgId") or "",
        creation_datetime=_text(grp, ns, "CreDtTm") or "",
        number_of_txs=int(_text(grp, ns, "NbOfTxs") or "0"),
        control_sum=Decimal(ctrl) if ctrl else None,
        initiating_party=_parse_party(_find(grp, ns, "InitgPty"), ns),
        settlement_method=sttlm,  # type: ignore[arg-type]
    )


def _root_or_raise(xml: str, ns: str, container_tag: str) -> ET.Element:
    try:
        doc = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise Iso20022CodecError(f"not well-formed XML: {exc}") from exc
    container = doc.find(_q(ns, container_tag))
    if container is None:
        raise Iso20022CodecError(f"missing {container_tag} (wrong namespace/version?)")
    return container


# --------------------------------------------------------------------------
# pain.001 — CustomerCreditTransferInitiation
# --------------------------------------------------------------------------


def build_pain001(msg: CustomerCreditTransferInitiation, version: str | None = None) -> str:
    msgdef = version or DEFAULT_VERSIONS["pain.001"]
    ns = urn_for(msgdef)
    doc, root = _root(ns, "CstmrCdtTrfInitn")
    _build_group_header(root, ns, msg.group_header, is_pacs=False)
    for pmt in msg.payments:
        pinf = _sub(root, ns, "PmtInf")
        _sub(pinf, ns, "PmtInfId", pmt.payment_info_id)
        _sub(pinf, ns, "PmtMtd", pmt.payment_method)
        _sub(pinf, ns, "ReqdExctnDt", pmt.requested_execution_date)
        _build_party(pinf, ns, "Dbtr", pmt.debtor)
        _build_account(pinf, ns, "DbtrAcct", pmt.debtor_account)
        _build_agent(pinf, ns, "DbtrAgt", pmt.debtor_agent)
        for tx in pmt.transactions:
            cdt = _sub(pinf, ns, "CdtTrfTxInf")
            pid = _sub(cdt, ns, "PmtId")
            if tx.instruction_id:
                _sub(pid, ns, "InstrId", tx.instruction_id)
            _sub(pid, ns, "EndToEndId", tx.end_to_end_id)
            if tx.uetr:
                _sub(pid, ns, "UETR", tx.uetr)
            if tx.instructed_amount is None:
                raise Iso20022CodecError("pain.001 CdtTrfTxInf requires InstdAmt")
            amt = _sub(cdt, ns, "Amt")
            instd = _sub(amt, ns, "InstdAmt", _fmt_amount(tx.instructed_amount))
            instd.set("Ccy", validate_currency(tx.instructed_amount.currency, require_active=False))
            if tx.creditor_agent:
                _build_agent(cdt, ns, "CdtrAgt", tx.creditor_agent)
            if tx.creditor:
                _build_party(cdt, ns, "Cdtr", tx.creditor)
            if tx.creditor_account:
                _build_account(cdt, ns, "CdtrAcct", tx.creditor_account)
            if tx.remittance_info:
                _build_remittance(cdt, ns, tx.remittance_info)
    return _serialize(doc)


def parse_pain001(xml: str, version: str | None = None) -> CustomerCreditTransferInitiation:
    ns = urn_for(version or DEFAULT_VERSIONS["pain.001"])
    root = _root_or_raise(xml, ns, "CstmrCdtTrfInitn")
    gh = _parse_group_header(root, ns)
    payments = []
    for pinf in _findall(root, ns, "PmtInf"):
        txs = []
        for cdt in _findall(pinf, ns, "CdtTrfTxInf"):
            pid = _find(cdt, ns, "PmtId")
            txs.append(
                CreditTransferTransaction(
                    end_to_end_id=_text(pid, ns, "EndToEndId") or "",
                    instruction_id=_text(pid, ns, "InstrId"),
                    uetr=_text(pid, ns, "UETR"),
                    instructed_amount=_parse_amount(_find(cdt, ns, "Amt/InstdAmt")),
                    creditor_agent=_parse_agent(_find(cdt, ns, "CdtrAgt"), ns),
                    creditor=_parse_party(_find(cdt, ns, "Cdtr"), ns),
                    creditor_account=_parse_account(_find(cdt, ns, "CdtrAcct"), ns),
                    remittance_info=_parse_remittance(_find(cdt, ns, "RmtInf"), ns),
                )
            )
        debtor = _parse_party(_find(pinf, ns, "Dbtr"), ns)
        debtor_acct = _parse_account(_find(pinf, ns, "DbtrAcct"), ns)
        debtor_agt = _parse_agent(_find(pinf, ns, "DbtrAgt"), ns)
        if debtor is None or debtor_acct is None or debtor_agt is None:
            raise Iso20022CodecError("pain.001 PmtInf missing Dbtr/DbtrAcct/DbtrAgt")
        payments.append(
            PaymentInstruction(
                payment_info_id=_text(pinf, ns, "PmtInfId") or "",
                requested_execution_date=_text(pinf, ns, "ReqdExctnDt") or "",
                debtor=debtor,
                debtor_account=debtor_acct,
                debtor_agent=debtor_agt,
                transactions=tuple(txs),
            )
        )
    return CustomerCreditTransferInitiation(group_header=gh, payments=tuple(payments))


# --------------------------------------------------------------------------
# pacs.008 — FIToFICustomerCreditTransfer
# --------------------------------------------------------------------------


def build_pacs008(msg: FIToFICustomerCreditTransfer, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.008"])
    doc, root = _root(ns, "FIToFICstmrCdtTrf")
    _build_group_header(root, ns, msg.group_header, is_pacs=True)
    for tx in msg.transactions:
        cdt = _sub(root, ns, "CdtTrfTxInf")
        pid = _sub(cdt, ns, "PmtId")
        if tx.instruction_id:
            _sub(pid, ns, "InstrId", tx.instruction_id)
        _sub(pid, ns, "EndToEndId", tx.end_to_end_id)
        if tx.tx_id:
            _sub(pid, ns, "TxId", tx.tx_id)
        if tx.uetr:
            _sub(pid, ns, "UETR", tx.uetr)
        if tx.interbank_amount is None:
            raise Iso20022CodecError("pacs.008 CdtTrfTxInf requires IntrBkSttlmAmt")
        amt = _sub(cdt, ns, "IntrBkSttlmAmt", _fmt_amount(tx.interbank_amount))
        amt.set("Ccy", validate_currency(tx.interbank_amount.currency, require_active=False))
        if tx.interbank_settlement_date:
            _sub(cdt, ns, "IntrBkSttlmDt", tx.interbank_settlement_date)
        if tx.charge_bearer:
            _sub(cdt, ns, "ChrgBr", tx.charge_bearer)
        if tx.debtor:
            _build_party(cdt, ns, "Dbtr", tx.debtor)
        if tx.debtor_account:
            _build_account(cdt, ns, "DbtrAcct", tx.debtor_account)
        if tx.debtor_agent:
            _build_agent(cdt, ns, "DbtrAgt", tx.debtor_agent)
        if tx.creditor_agent:
            _build_agent(cdt, ns, "CdtrAgt", tx.creditor_agent)
        if tx.creditor:
            _build_party(cdt, ns, "Cdtr", tx.creditor)
        if tx.creditor_account:
            _build_account(cdt, ns, "CdtrAcct", tx.creditor_account)
        if tx.remittance_info:
            _build_remittance(cdt, ns, tx.remittance_info)
    return _serialize(doc)


def parse_pacs008(xml: str, version: str | None = None) -> FIToFICustomerCreditTransfer:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.008"])
    root = _root_or_raise(xml, ns, "FIToFICstmrCdtTrf")
    gh = _parse_group_header(root, ns)
    txs = []
    for cdt in _findall(root, ns, "CdtTrfTxInf"):
        pid = _find(cdt, ns, "PmtId")
        txs.append(
            CreditTransferTransaction(
                end_to_end_id=_text(pid, ns, "EndToEndId") or "",
                instruction_id=_text(pid, ns, "InstrId"),
                tx_id=_text(pid, ns, "TxId"),
                uetr=_text(pid, ns, "UETR"),
                interbank_amount=_parse_amount(_find(cdt, ns, "IntrBkSttlmAmt")),
                interbank_settlement_date=_text(cdt, ns, "IntrBkSttlmDt"),
                charge_bearer=_text(cdt, ns, "ChrgBr"),  # type: ignore[arg-type]
                debtor=_parse_party(_find(cdt, ns, "Dbtr"), ns),
                debtor_account=_parse_account(_find(cdt, ns, "DbtrAcct"), ns),
                debtor_agent=_parse_agent(_find(cdt, ns, "DbtrAgt"), ns),
                creditor_agent=_parse_agent(_find(cdt, ns, "CdtrAgt"), ns),
                creditor=_parse_party(_find(cdt, ns, "Cdtr"), ns),
                creditor_account=_parse_account(_find(cdt, ns, "CdtrAcct"), ns),
                remittance_info=_parse_remittance(_find(cdt, ns, "RmtInf"), ns),
            )
        )
    return FIToFICustomerCreditTransfer(group_header=gh, transactions=tuple(txs))


# --------------------------------------------------------------------------
# pacs.002 — FIToFIPaymentStatusReport
# --------------------------------------------------------------------------


def build_pacs002(msg: FIToFIPaymentStatusReport, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.002"])
    doc, root = _root(ns, "FIToFIPmtStsRpt")
    grp = _sub(root, ns, "GrpHdr")
    _sub(grp, ns, "MsgId", msg.group_header.message_id)
    _sub(grp, ns, "CreDtTm", msg.group_header.creation_datetime)
    orig = _sub(root, ns, "OrgnlGrpInfAndSts")
    _sub(orig, ns, "OrgnlMsgId", msg.original_message_id)
    _sub(orig, ns, "OrgnlMsgNmId", msg.original_message_name_id)
    for sts in msg.statuses:
        ts = _sub(root, ns, "TxInfAndSts")
        _sub(ts, ns, "StsId", sts.status_id)
        if sts.original_end_to_end_id:
            _sub(ts, ns, "OrgnlEndToEndId", sts.original_end_to_end_id)
        if sts.original_tx_id:
            _sub(ts, ns, "OrgnlTxId", sts.original_tx_id)
        if sts.original_uetr:
            _sub(ts, ns, "OrgnlUETR", sts.original_uetr)
        _sub(ts, ns, "TxSts", sts.transaction_status)
        if sts.status_reason_code or sts.additional_info:
            rsn = _sub(ts, ns, "StsRsnInf")
            if sts.status_reason_code:
                rcd = _sub(rsn, ns, "Rsn")
                _sub(rcd, ns, "Cd", sts.status_reason_code)
            for info in sts.additional_info:
                _sub(rsn, ns, "AddtlInf", info)
    return _serialize(doc)


def parse_pacs002(xml: str, version: str | None = None) -> FIToFIPaymentStatusReport:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.002"])
    root = _root_or_raise(xml, ns, "FIToFIPmtStsRpt")
    grp = _find(root, ns, "GrpHdr")
    gh = GroupHeader(
        message_id=_text(grp, ns, "MsgId") or "",
        creation_datetime=_text(grp, ns, "CreDtTm") or "",
        number_of_txs=0,
    )
    statuses = []
    for ts in _findall(root, ns, "TxInfAndSts"):
        rsn = _find(ts, ns, "StsRsnInf")
        statuses.append(
            TransactionStatus(
                status_id=_text(ts, ns, "StsId") or "",
                original_end_to_end_id=_text(ts, ns, "OrgnlEndToEndId"),
                original_tx_id=_text(ts, ns, "OrgnlTxId"),
                original_uetr=_text(ts, ns, "OrgnlUETR"),
                transaction_status=_text(ts, ns, "TxSts") or "ACSP",  # type: ignore[arg-type]
                status_reason_code=_text(ts, ns, "StsRsnInf/Rsn/Cd"),
                additional_info=_addtl_info(rsn, ns),
            )
        )
    return FIToFIPaymentStatusReport(
        group_header=gh,
        original_message_id=_text(root, ns, "OrgnlGrpInfAndSts/OrgnlMsgId") or "",
        original_message_name_id=_text(root, ns, "OrgnlGrpInfAndSts/OrgnlMsgNmId") or "",
        statuses=tuple(statuses),
    )


# --------------------------------------------------------------------------
# camt.053 / camt.054 — shared Bal + Ntry component build/parse
# --------------------------------------------------------------------------


def _build_amt(parent: ET.Element, ns: str, tag: str, amt: Amount) -> None:
    el = _sub(parent, ns, tag, _fmt_amount(amt))
    el.set("Ccy", validate_currency(amt.currency, require_active=False))


def _build_balance(parent: ET.Element, ns: str, bal: CashBalance) -> None:
    el = _sub(parent, ns, "Bal")
    tp = _sub(el, ns, "Tp")
    cdor = _sub(tp, ns, "CdOrPrtry")
    _sub(cdor, ns, "Cd", bal.balance_type)
    _build_amt(el, ns, "Amt", bal.amount)
    _sub(el, ns, "CdtDbtInd", bal.credit_debit)
    dt = _sub(el, ns, "Dt")
    _sub(dt, ns, "Dt", bal.date)


def _build_entry(parent: ET.Element, ns: str, entry: StatementEntry) -> None:
    el = _sub(parent, ns, "Ntry")
    _build_amt(el, ns, "Amt", entry.amount)
    _sub(el, ns, "CdtDbtInd", entry.credit_debit)
    _sub(el, ns, "Sts", entry.status)
    if entry.booking_date:
        bd = _sub(el, ns, "BookgDt")
        _sub(bd, ns, "Dt", entry.booking_date)
    if entry.value_date:
        vd = _sub(el, ns, "ValDt")
        _sub(vd, ns, "Dt", entry.value_date)
    if entry.account_servicer_reference:
        _sub(el, ns, "AcctSvcrRef", entry.account_servicer_reference)
    if entry.bank_transaction_code:
        btc = _sub(el, ns, "BkTxCd")
        domn = _sub(btc, ns, "Domn")
        _sub(domn, ns, "Cd", entry.bank_transaction_code)
    if entry.end_to_end_id or entry.remittance_info:
        dtls = _sub(el, ns, "NtryDtls")
        txd = _sub(dtls, ns, "TxDtls")
        if entry.end_to_end_id:
            refs = _sub(txd, ns, "Refs")
            _sub(refs, ns, "EndToEndId", entry.end_to_end_id)
        if entry.remittance_info:
            _build_remittance(txd, ns, entry.remittance_info)


def _parse_balance(el: ET.Element, ns: str) -> CashBalance:
    amt = _parse_amount(_find(el, ns, "Amt"))
    if amt is None:
        raise Iso20022CodecError("Bal missing Amt")
    return CashBalance(
        balance_type=_text(el, ns, "Tp/CdOrPrtry/Cd") or "OPBD",  # type: ignore[arg-type]
        amount=amt,
        credit_debit=_text(el, ns, "CdtDbtInd") or "CRDT",  # type: ignore[arg-type]
        date=_text(el, ns, "Dt/Dt") or "",
    )


def _parse_entry(el: ET.Element, ns: str) -> StatementEntry:
    amt = _parse_amount(_find(el, ns, "Amt"))
    if amt is None:
        raise Iso20022CodecError("Ntry missing Amt")
    txd = _find(el, ns, "NtryDtls/TxDtls")
    return StatementEntry(
        amount=amt,
        credit_debit=_text(el, ns, "CdtDbtInd") or "CRDT",  # type: ignore[arg-type]
        status=_text(el, ns, "Sts") or "BOOK",  # type: ignore[arg-type]
        booking_date=_text(el, ns, "BookgDt/Dt"),
        value_date=_text(el, ns, "ValDt/Dt"),
        account_servicer_reference=_text(el, ns, "AcctSvcrRef"),
        bank_transaction_code=_text(el, ns, "BkTxCd/Domn/Cd"),
        end_to_end_id=_text(txd, ns, "Refs/EndToEndId") if txd is not None else None,
        remittance_info=(
            _parse_remittance(_find(txd, ns, "RmtInf"), ns) if txd is not None else None
        ),
    )


def _grphdr_min(parent: ET.Element, ns: str, gh: GroupHeader) -> None:
    grp = _sub(parent, ns, "GrpHdr")
    _sub(grp, ns, "MsgId", gh.message_id)
    _sub(grp, ns, "CreDtTm", gh.creation_datetime)


# --------------------------------------------------------------------------
# camt.053 — BankToCustomerStatement
# --------------------------------------------------------------------------


def build_camt053(msg: BankToCustomerStatement, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["camt.053"])
    doc, root = _root(ns, "BkToCstmrStmt")
    _grphdr_min(root, ns, msg.group_header)
    for stmt in msg.statements:
        s = _sub(root, ns, "Stmt")
        _sub(s, ns, "Id", stmt.statement_id)
        _sub(s, ns, "CreDtTm", stmt.creation_datetime)
        _build_account(s, ns, "Acct", stmt.account)
        for bal in stmt.balances:
            _build_balance(s, ns, bal)
        for entry in stmt.entries:
            _build_entry(s, ns, entry)
    return _serialize(doc)


def parse_camt053(xml: str, version: str | None = None) -> BankToCustomerStatement:
    ns = urn_for(version or DEFAULT_VERSIONS["camt.053"])
    root = _root_or_raise(xml, ns, "BkToCstmrStmt")
    gh = GroupHeader(
        message_id=_text(root, ns, "GrpHdr/MsgId") or "",
        creation_datetime=_text(root, ns, "GrpHdr/CreDtTm") or "",
        number_of_txs=0,
    )
    statements = []
    for s in _findall(root, ns, "Stmt"):
        acct = _parse_account(_find(s, ns, "Acct"), ns)
        if acct is None:
            raise Iso20022CodecError("camt.053 Stmt missing Acct")
        statements.append(
            AccountStatement(
                statement_id=_text(s, ns, "Id") or "",
                creation_datetime=_text(s, ns, "CreDtTm") or "",
                account=acct,
                balances=tuple(_parse_balance(b, ns) for b in _findall(s, ns, "Bal")),
                entries=tuple(_parse_entry(e, ns) for e in _findall(s, ns, "Ntry")),
            )
        )
    return BankToCustomerStatement(group_header=gh, statements=tuple(statements))


# --------------------------------------------------------------------------
# camt.054 — BankToCustomerDebitCreditNotification
# --------------------------------------------------------------------------


def build_camt054(msg: BankToCustomerDebitCreditNotification, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["camt.054"])
    doc, root = _root(ns, "BkToCstmrDbtCdtNtfctn")
    _grphdr_min(root, ns, msg.group_header)
    for ntf in msg.notifications:
        n = _sub(root, ns, "Ntfctn")
        _sub(n, ns, "Id", ntf.notification_id)
        _sub(n, ns, "CreDtTm", ntf.creation_datetime)
        _build_account(n, ns, "Acct", ntf.account)
        for entry in ntf.entries:
            _build_entry(n, ns, entry)
    return _serialize(doc)


def parse_camt054(xml: str, version: str | None = None) -> BankToCustomerDebitCreditNotification:
    ns = urn_for(version or DEFAULT_VERSIONS["camt.054"])
    root = _root_or_raise(xml, ns, "BkToCstmrDbtCdtNtfctn")
    gh = GroupHeader(
        message_id=_text(root, ns, "GrpHdr/MsgId") or "",
        creation_datetime=_text(root, ns, "GrpHdr/CreDtTm") or "",
        number_of_txs=0,
    )
    notifications = []
    for n in _findall(root, ns, "Ntfctn"):
        acct = _parse_account(_find(n, ns, "Acct"), ns)
        if acct is None:
            raise Iso20022CodecError("camt.054 Ntfctn missing Acct")
        notifications.append(
            AccountNotification(
                notification_id=_text(n, ns, "Id") or "",
                creation_datetime=_text(n, ns, "CreDtTm") or "",
                account=acct,
                entries=tuple(_parse_entry(e, ns) for e in _findall(n, ns, "Ntry")),
            )
        )
    return BankToCustomerDebitCreditNotification(
        group_header=gh, notifications=tuple(notifications)
    )


# --------------------------------------------------------------------------
# pain.002 — CustomerPaymentStatusReport (pain-side ack of pain.001)
# --------------------------------------------------------------------------


def _build_tx_status(parent: ET.Element, ns: str, sts: TransactionStatus) -> None:
    ts = _sub(parent, ns, "TxInfAndSts")
    _sub(ts, ns, "StsId", sts.status_id)
    if sts.original_end_to_end_id:
        _sub(ts, ns, "OrgnlEndToEndId", sts.original_end_to_end_id)
    if sts.original_tx_id:
        _sub(ts, ns, "OrgnlTxId", sts.original_tx_id)
    _sub(ts, ns, "TxSts", sts.transaction_status)
    if sts.status_reason_code or sts.additional_info:
        rsn = _sub(ts, ns, "StsRsnInf")
        if sts.status_reason_code:
            _sub(_sub(rsn, ns, "Rsn"), ns, "Cd", sts.status_reason_code)
        for info in sts.additional_info:
            _sub(rsn, ns, "AddtlInf", info)


def _parse_tx_status(ts: ET.Element, ns: str) -> TransactionStatus:
    rsn = _find(ts, ns, "StsRsnInf")
    return TransactionStatus(
        status_id=_text(ts, ns, "StsId") or "",
        original_end_to_end_id=_text(ts, ns, "OrgnlEndToEndId"),
        original_tx_id=_text(ts, ns, "OrgnlTxId"),
        transaction_status=_text(ts, ns, "TxSts") or "ACSP",  # type: ignore[arg-type]
        status_reason_code=_text(ts, ns, "StsRsnInf/Rsn/Cd"),
        additional_info=tuple(
            a.text for a in (_findall(rsn, ns, "AddtlInf") if rsn is not None else []) if a.text
        ),
    )


def build_pain002(msg: CustomerPaymentStatusReport, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["pain.002"])
    doc, root = _root(ns, "CstmrPmtStsRpt")
    _grphdr_min(root, ns, msg.group_header)
    orig = _sub(root, ns, "OrgnlGrpInfAndSts")
    _sub(orig, ns, "OrgnlMsgId", msg.original_message_id)
    _sub(orig, ns, "OrgnlMsgNmId", msg.original_message_name_id)
    for pmt in msg.payment_statuses:
        pinf = _sub(root, ns, "OrgnlPmtInfAndSts")
        _sub(pinf, ns, "OrgnlPmtInfId", pmt.original_payment_info_id)
        for sts in pmt.statuses:
            _build_tx_status(pinf, ns, sts)
    return _serialize(doc)


def parse_pain002(xml: str, version: str | None = None) -> CustomerPaymentStatusReport:
    ns = urn_for(version or DEFAULT_VERSIONS["pain.002"])
    root = _root_or_raise(xml, ns, "CstmrPmtStsRpt")
    gh = GroupHeader(
        message_id=_text(root, ns, "GrpHdr/MsgId") or "",
        creation_datetime=_text(root, ns, "GrpHdr/CreDtTm") or "",
        number_of_txs=0,
    )
    payment_statuses = []
    for pinf in _findall(root, ns, "OrgnlPmtInfAndSts"):
        payment_statuses.append(
            OriginalPaymentStatus(
                original_payment_info_id=_text(pinf, ns, "OrgnlPmtInfId") or "",
                statuses=tuple(
                    _parse_tx_status(ts, ns) for ts in _findall(pinf, ns, "TxInfAndSts")
                ),
            )
        )
    return CustomerPaymentStatusReport(
        group_header=gh,
        original_message_id=_text(root, ns, "OrgnlGrpInfAndSts/OrgnlMsgId") or "",
        original_message_name_id=_text(root, ns, "OrgnlGrpInfAndSts/OrgnlMsgNmId") or "",
        payment_statuses=tuple(payment_statuses),
    )


# --------------------------------------------------------------------------
# pacs.004 — PaymentReturn (reversal of a settled transfer)
# --------------------------------------------------------------------------


def build_pacs004(msg: PaymentReturn, version: str | None = None) -> str:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.004"])
    doc, root = _root(ns, "PmtRtr")
    _build_group_header(root, ns, msg.group_header, is_pacs=True)
    for tx in msg.transactions:
        txinf = _sub(root, ns, "TxInf")
        if tx.return_id:
            _sub(txinf, ns, "RtrId", tx.return_id)
        if msg.original_message_id or msg.original_message_name_id:
            ogi = _sub(txinf, ns, "OrgnlGrpInf")
            if msg.original_message_id:
                _sub(ogi, ns, "OrgnlMsgId", msg.original_message_id)
            if msg.original_message_name_id:
                _sub(ogi, ns, "OrgnlMsgNmId", msg.original_message_name_id)
        if tx.original_end_to_end_id:
            _sub(txinf, ns, "OrgnlEndToEndId", tx.original_end_to_end_id)
        if tx.original_tx_id:
            _sub(txinf, ns, "OrgnlTxId", tx.original_tx_id)
        if tx.original_uetr:
            _sub(txinf, ns, "OrgnlUETR", tx.original_uetr)
        if tx.original_interbank_amount is not None:
            _build_amt(txinf, ns, "OrgnlIntrBkSttlmAmt", tx.original_interbank_amount)
        _build_amt(txinf, ns, "RtrdIntrBkSttlmAmt", tx.returned_interbank_amount)
        if tx.interbank_settlement_date:
            _sub(txinf, ns, "IntrBkSttlmDt", tx.interbank_settlement_date)
        if tx.return_reason_code or tx.additional_info:
            rsn = _sub(txinf, ns, "RtrRsnInf")
            if tx.return_reason_code:
                _sub(_sub(rsn, ns, "Rsn"), ns, "Cd", tx.return_reason_code)
            for info in tx.additional_info:
                _sub(rsn, ns, "AddtlInf", info)
    return _serialize(doc)


def parse_pacs004(xml: str, version: str | None = None) -> PaymentReturn:
    ns = urn_for(version or DEFAULT_VERSIONS["pacs.004"])
    root = _root_or_raise(xml, ns, "PmtRtr")
    gh = _parse_group_header(root, ns)
    orig_msg_id: str | None = None
    orig_msg_nm: str | None = None
    txs = []
    for txinf in _findall(root, ns, "TxInf"):
        if orig_msg_id is None:
            orig_msg_id = _text(txinf, ns, "OrgnlGrpInf/OrgnlMsgId")
            orig_msg_nm = _text(txinf, ns, "OrgnlGrpInf/OrgnlMsgNmId")
        rtrd = _parse_amount(_find(txinf, ns, "RtrdIntrBkSttlmAmt"))
        if rtrd is None:
            raise Iso20022CodecError("pacs.004 TxInf missing RtrdIntrBkSttlmAmt")
        rsn = _find(txinf, ns, "RtrRsnInf")
        txs.append(
            PaymentReturnTransaction(
                returned_interbank_amount=rtrd,
                return_id=_text(txinf, ns, "RtrId"),
                original_end_to_end_id=_text(txinf, ns, "OrgnlEndToEndId"),
                original_tx_id=_text(txinf, ns, "OrgnlTxId"),
                original_uetr=_text(txinf, ns, "OrgnlUETR"),
                original_interbank_amount=_parse_amount(_find(txinf, ns, "OrgnlIntrBkSttlmAmt")),
                interbank_settlement_date=_text(txinf, ns, "IntrBkSttlmDt"),
                return_reason_code=_text(txinf, ns, "RtrRsnInf/Rsn/Cd"),
                additional_info=_addtl_info(rsn, ns),
            )
        )
    return PaymentReturn(
        group_header=gh,
        transactions=tuple(txs),
        original_message_id=orig_msg_id,
        original_message_name_id=orig_msg_nm,
    )
