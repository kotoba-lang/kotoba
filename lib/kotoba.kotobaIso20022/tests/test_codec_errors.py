"""Malformed-input error paths + optional-element build branches for codec."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    Iso20022CodecError,
    build_camt053,
    build_pacs002,
    build_pain002,
    parse_camt053,
    parse_camt054,
    parse_pacs002,
    parse_pacs008,
    parse_pain001,
    parse_pain002,
)
from kotoba_iso20022.model import (
    Account,
    AccountStatement,
    Amount,
    BankToCustomerStatement,
    CashBalance,
    CustomerPaymentStatusReport,
    FIToFIPaymentStatusReport,
    GroupHeader,
    OriginalPaymentStatus,
    StatementEntry,
    TransactionStatus,
)


def _doc(msgdef: str, body: str) -> str:
    ns = f"urn:iso:std:iso:20022:tech:xsd:{msgdef}"
    return f"<?xml version='1.0'?><Document xmlns='{ns}'>{body}</Document>"


# --------------------------------------------------------------------------
# parse error paths
# --------------------------------------------------------------------------


def test_missing_group_header() -> None:
    xml = _doc("pacs.008.001.08", "<FIToFICstmrCdtTrf></FIToFICstmrCdtTrf>")
    with pytest.raises(Iso20022CodecError, match="GrpHdr"):
        parse_pacs008(xml)


def test_amount_missing_ccy_attribute() -> None:
    body = (
        "<FIToFICstmrCdtTrf>"
        "<GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm><NbOfTxs>1</NbOfTxs>"
        "<SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf></GrpHdr>"
        "<CdtTrfTxInf><PmtId><EndToEndId>E</EndToEndId></PmtId>"
        "<IntrBkSttlmAmt>10.00</IntrBkSttlmAmt></CdtTrfTxInf>"
        "</FIToFICstmrCdtTrf>"
    )
    with pytest.raises(Iso20022CodecError, match="Ccy"):
        parse_pacs008(_doc("pacs.008.001.08", body))


def test_pain001_pmtinf_missing_debtor() -> None:
    body = (
        "<CstmrCdtTrfInitn>"
        "<GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm><NbOfTxs>1</NbOfTxs></GrpHdr>"
        "<PmtInf><PmtInfId>P</PmtInfId><ReqdExctnDt>2026-06-08</ReqdExctnDt></PmtInf>"
        "</CstmrCdtTrfInitn>"
    )
    with pytest.raises(Iso20022CodecError, match="Dbtr"):
        parse_pain001(_doc("pain.001.001.09", body))


def test_camt053_stmt_missing_acct() -> None:
    body = (
        "<BkToCstmrStmt><GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm></GrpHdr>"
        "<Stmt><Id>S</Id><CreDtTm>t</CreDtTm></Stmt></BkToCstmrStmt>"
    )
    with pytest.raises(Iso20022CodecError, match="Acct"):
        parse_camt053(_doc("camt.053.001.08", body))


def test_camt053_balance_missing_amt() -> None:
    body = (
        "<BkToCstmrStmt><GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm></GrpHdr>"
        "<Stmt><Id>S</Id><CreDtTm>t</CreDtTm>"
        "<Acct><Id><IBAN>DE89370400440532013000</IBAN></Id></Acct>"
        "<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>"
        "<CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-06-08</Dt></Dt></Bal>"
        "</Stmt></BkToCstmrStmt>"
    )
    with pytest.raises(Iso20022CodecError, match="Bal missing Amt"):
        parse_camt053(_doc("camt.053.001.08", body))


def test_camt053_entry_missing_amt() -> None:
    body = (
        "<BkToCstmrStmt><GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm></GrpHdr>"
        "<Stmt><Id>S</Id><CreDtTm>t</CreDtTm>"
        "<Acct><Id><IBAN>DE89370400440532013000</IBAN></Id></Acct>"
        "<Ntry><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts></Ntry>"
        "</Stmt></BkToCstmrStmt>"
    )
    with pytest.raises(Iso20022CodecError, match="Ntry missing Amt"):
        parse_camt053(_doc("camt.053.001.08", body))


def test_camt054_ntfctn_missing_acct() -> None:
    body = (
        "<BkToCstmrDbtCdtNtfctn><GrpHdr><MsgId>M</MsgId><CreDtTm>t</CreDtTm></GrpHdr>"
        "<Ntfctn><Id>N</Id><CreDtTm>t</CreDtTm></Ntfctn></BkToCstmrDbtCdtNtfctn>"
    )
    with pytest.raises(Iso20022CodecError, match="Acct"):
        parse_camt054(_doc("camt.054.001.08", body))


# --------------------------------------------------------------------------
# optional-element build branches (OrgnlTxId, BkTxCd)
# --------------------------------------------------------------------------


def test_pacs002_with_original_tx_id() -> None:
    msg = FIToFIPaymentStatusReport(
        group_header=GroupHeader("STS", "t", 0),
        original_message_id="M", original_message_name_id="pacs.008.001.08",
        statuses=(TransactionStatus(status_id="S", original_tx_id="TX-9",
                                    transaction_status="ACSC"),),
    )
    back = parse_pacs002(build_pacs002(msg))
    assert back.statuses[0].original_tx_id == "TX-9"


def test_pain002_with_original_tx_id() -> None:
    msg = CustomerPaymentStatusReport(
        group_header=GroupHeader("STS", "t", 0),
        original_message_id="M", original_message_name_id="pain.001.001.09",
        payment_statuses=(
            OriginalPaymentStatus(
                original_payment_info_id="P",
                statuses=(TransactionStatus(status_id="S", original_tx_id="TX-7",
                                            transaction_status="ACSP"),),
            ),
        ),
    )
    back = parse_pain002(build_pain002(msg))
    assert back.payment_statuses[0].statuses[0].original_tx_id == "TX-7"


def test_camt053_entry_with_bank_transaction_code() -> None:
    entry = StatementEntry(
        amount=Amount(Decimal("1.00"), "EUR"), credit_debit="CRDT", status="BOOK",
        end_to_end_id="E", bank_transaction_code="PMNT",
    )
    msg = BankToCustomerStatement(
        group_header=GroupHeader("CS", "t", 0),
        statements=(AccountStatement("S", "t", Account(iban="DE89370400440532013000"),
                                     (CashBalance("OPBD", Amount(Decimal("0"), "EUR"),
                                                  "CRDT", "2026-06-08"),), (entry,)),),
    )
    xml = build_camt053(msg)
    assert "<BkTxCd>" in xml
    back = parse_camt053(xml)
    assert back.statements[0].entries[0].bank_transaction_code == "PMNT"
