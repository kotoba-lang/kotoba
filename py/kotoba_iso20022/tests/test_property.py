"""Property-based round-trip idempotence + golden-output regression lock.

A correct codec is a *stable fixed point*: ``build(parse(build(m))) ==
build(m)``. These tests generate many structurally-varied valid messages
from a fixed seed (deterministic, dependency-free) and assert that property,
catching serialization bugs that hand-written examples miss. A golden test
additionally pins the exact wire bytes so an accidental format change is
caught as a regression.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from kotoba_iso20022 import (
    build_camt054,
    build_pacs008,
    build_pain001,
    pacs008_group_header,
    pain001_group_header,
    parse_camt054,
    parse_pacs008,
    parse_pain001,
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
    RemittanceInfo,
    StatementEntry,
)
from kotoba_iso20022.validate import iban_check_digits

_CCYS = [("EUR", 2), ("USD", 2), ("JPY", 0), ("GBP", 2)]
_BICS = ["DEUTDEFF", "NWBKGB2L", "BOFAUS3N", "BNPAFRPP", "CHASUS33", "DEUTDEFF500"]
_NAMES = ["Alice Cohen", "Bob Levi", "Acme GmbH", "Société Générale Client", "李雷"]


def _iban(rng: random.Random) -> str:
    country, length = rng.choice([("DE", 22), ("GB", 22), ("FR", 27), ("NL", 18)])
    bban = "".join(rng.choice("0123456789") for _ in range(length - 4))
    return country + iban_check_digits(country, bban) + bban


def _uetr(rng: random.Random) -> str:
    h = "0123456789abcdef"
    def p(n: int) -> str:
        return "".join(rng.choice(h) for _ in range(n))
    return f"{p(8)}-{p(4)}-4{p(3)}-{rng.choice('89ab')}{p(3)}-{p(12)}"


def _amount(rng: random.Random) -> Amount:
    ccy, dp = rng.choice(_CCYS)
    units = rng.randint(1, 10_000_000)
    value = Decimal(units) / (10 ** dp) if dp else Decimal(units)
    return Amount(value.quantize(Decimal(1).scaleb(-dp)) if dp else value, ccy)


def _party(rng: random.Random) -> Party:
    return Party(rng.choice(_NAMES))


def _gen_pacs008(rng: random.Random) -> FIToFICustomerCreditTransfer:
    n = rng.randint(1, 4)
    txs = []
    for i in range(n):
        tx = CreditTransferTransaction(
            end_to_end_id=f"E2E-{rng.randint(0, 1_000_000)}",
            instruction_id=f"INSTR-{i}" if rng.random() < 0.5 else None,
            tx_id=f"TX-{i}" if rng.random() < 0.5 else None,
            uetr=_uetr(rng),
            interbank_amount=_amount(rng),
            interbank_settlement_date="2026-06-08" if rng.random() < 0.7 else None,
            charge_bearer=rng.choice(["DEBT", "CRED", "SHAR"]) if rng.random() < 0.7 else None,
            debtor=_party(rng),
            debtor_account=Account(iban=_iban(rng)) if rng.random() < 0.6 else None,
            debtor_agent=Agent(bicfi=rng.choice(_BICS)),
            creditor_agent=Agent(bicfi=rng.choice(_BICS)),
            creditor=_party(rng),
            creditor_account=Account(iban=_iban(rng)) if rng.random() < 0.6 else None,
            remittance_info=RemittanceInfo(tuple(
                f"line {k}" for k in range(rng.randint(1, 3))
            )) if rng.random() < 0.5 else None,
        )
        txs.append(tx)
    return FIToFICustomerCreditTransfer(
        group_header=pacs008_group_header(f"MSG-{rng.randint(0, 10**6)}",
                                          "2026-06-08T09:30:00Z", tuple(txs)),
        transactions=tuple(txs),
    )


def _gen_pain001(rng: random.Random) -> CustomerCreditTransferInitiation:
    n = rng.randint(1, 4)
    txs = tuple(
        CreditTransferTransaction(
            end_to_end_id=f"E2E-{rng.randint(0, 10**6)}",
            uetr=_uetr(rng) if rng.random() < 0.5 else None,
            instructed_amount=_amount(rng),
            creditor=_party(rng),
            creditor_account=Account(iban=_iban(rng)) if rng.random() < 0.6 else None,
            remittance_info=RemittanceInfo(("ref",)) if rng.random() < 0.4 else None,
        )
        for _ in range(n)
    )
    return CustomerCreditTransferInitiation(
        group_header=pain001_group_header(f"MSG-{rng.randint(0, 10**6)}",
                                          "2026-06-08T09:30:00Z", txs,
                                          initiating_party=_party(rng)),
        payments=(
            PaymentInstruction(
                payment_info_id=f"P-{rng.randint(0, 10**6)}",
                requested_execution_date="2026-06-08",
                debtor=_party(rng),
                debtor_account=Account(iban=_iban(rng)),
                debtor_agent=Agent(bicfi=rng.choice(_BICS)),
                transactions=txs,
            ),
        ),
    )


def _gen_camt054(rng: random.Random) -> BankToCustomerDebitCreditNotification:
    entries = tuple(
        StatementEntry(
            amount=_amount(rng),
            credit_debit=rng.choice(["CRDT", "DBIT"]),
            status=rng.choice(["BOOK", "PDNG", "INFO"]),
            booking_date="2026-06-08" if rng.random() < 0.6 else None,
            value_date="2026-06-09" if rng.random() < 0.6 else None,
            account_servicer_reference=f"SVCR-{rng.randint(0, 10**6)}" if rng.random() < 0.5 else None,
            end_to_end_id=f"E2E-{rng.randint(0, 10**6)}" if rng.random() < 0.7 else None,
            bank_transaction_code="PMNT" if rng.random() < 0.3 else None,
        )
        for _ in range(rng.randint(1, 3))
    )
    return BankToCustomerDebitCreditNotification(
        group_header=GroupHeader(f"C-{rng.randint(0, 10**6)}", "2026-06-08T23:00:00Z", 0),
        notifications=(
            AccountNotification(f"N-{rng.randint(0, 10**6)}", "2026-06-08T23:05:00Z",
                                Account(iban=_iban(rng)), entries),
        ),
    )


_GENERATORS = [
    (_gen_pacs008, build_pacs008, parse_pacs008),
    (_gen_pain001, build_pain001, parse_pain001),
    (_gen_camt054, build_camt054, parse_camt054),
]


@pytest.mark.parametrize("gen,build,parse", _GENERATORS)
def test_serialization_is_idempotent(gen, build, parse) -> None:
    rng = random.Random(20260608)
    for _ in range(150):
        msg = gen(rng)
        xml1 = build(msg)
        xml2 = build(parse(xml1))
        assert xml1 == xml2, "codec is not a stable round-trip fixed point"


@pytest.mark.parametrize("gen,build,parse", _GENERATORS)
def test_parse_preserves_structure(gen, build, parse) -> None:
    rng = random.Random(42)
    for _ in range(100):
        msg = gen(rng)
        back = parse(build(msg))
        # rebuild matches — structural equality via the wire form
        assert build(back) == build(msg)


# --------------------------------------------------------------------------
# golden output — pins the exact wire bytes (regression lock)
# --------------------------------------------------------------------------

_GOLDEN_PACS008 = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">\n'
    "  <FIToFICstmrCdtTrf>\n"
    "    <GrpHdr>\n"
    "      <MsgId>MSG-GOLD</MsgId>\n"
    "      <CreDtTm>2026-06-08T09:30:00Z</CreDtTm>\n"
    "      <NbOfTxs>1</NbOfTxs>\n"
    "      <CtrlSum>1234.56</CtrlSum>\n"
    "      <SttlmInf>\n"
    "        <SttlmMtd>CLRG</SttlmMtd>\n"
    "      </SttlmInf>\n"
    "    </GrpHdr>\n"
    "    <CdtTrfTxInf>\n"
    "      <PmtId>\n"
    "        <EndToEndId>E2E-GOLD</EndToEndId>\n"
    "        <UETR>dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e</UETR>\n"
    "      </PmtId>\n"
    '      <IntrBkSttlmAmt Ccy="EUR">1234.56</IntrBkSttlmAmt>\n'
    "      <IntrBkSttlmDt>2026-06-08</IntrBkSttlmDt>\n"
    "      <ChrgBr>SHAR</ChrgBr>\n"
    "      <Dbtr>\n"
    "        <Nm>Alice</Nm>\n"
    "      </Dbtr>\n"
    "      <DbtrAcct>\n"
    "        <Id>\n"
    "          <IBAN>DE89370400440532013000</IBAN>\n"
    "        </Id>\n"
    "      </DbtrAcct>\n"
    "      <DbtrAgt>\n"
    "        <FinInstnId>\n"
    "          <BICFI>DEUTDEFF</BICFI>\n"
    "        </FinInstnId>\n"
    "      </DbtrAgt>\n"
    "      <CdtrAgt>\n"
    "        <FinInstnId>\n"
    "          <BICFI>NWBKGB2L</BICFI>\n"
    "        </FinInstnId>\n"
    "      </CdtrAgt>\n"
    "      <Cdtr>\n"
    "        <Nm>Bob</Nm>\n"
    "      </Cdtr>\n"
    "      <CdtrAcct>\n"
    "        <Id>\n"
    "          <IBAN>GB29NWBK60161331926819</IBAN>\n"
    "        </Id>\n"
    "      </CdtrAcct>\n"
    "    </CdtTrfTxInf>\n"
    "  </FIToFICstmrCdtTrf>\n"
    "</Document>"
)


def test_golden_pacs008_exact_bytes() -> None:
    tx = CreditTransferTransaction(
        end_to_end_id="E2E-GOLD", uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
        interbank_amount=Amount(Decimal("1234.56"), "EUR"),
        interbank_settlement_date="2026-06-08", charge_bearer="SHAR",
        debtor=Party("Alice"), debtor_account=Account(iban="DE89370400440532013000"),
        debtor_agent=Agent(bicfi="DEUTDEFF"), creditor_agent=Agent(bicfi="NWBKGB2L"),
        creditor=Party("Bob"), creditor_account=Account(iban="GB29NWBK60161331926819"),
    )
    gh = GroupHeader("MSG-GOLD", "2026-06-08T09:30:00Z", 1,
                     control_sum=Decimal("1234.56"), settlement_method="CLRG")
    out = build_pacs008(FIToFICustomerCreditTransfer(group_header=gh, transactions=(tx,)))
    assert out == _GOLDEN_PACS008
