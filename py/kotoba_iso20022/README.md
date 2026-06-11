# kotoba_iso20022 — cleanroom ISO 20022 payment-message codec

A dependency-free, charter-clean reimplementation of the three ISO 20022
message definitions the **kawase-yui (為替結)** cross-border actor
(ADR-2605282200) needs at its **interop / ingress boundary** — built purely
from the *open published* ISO 20022 standard, with **no proprietary SWIFT
SDK** and no vendor schema files at runtime.

This is the traditional-finance analogue of the CLAUDE.md substrate rule
*"AT-Protocol MST = ingress/interop wire"*: here the wire is the global
ISO 20022 banking network (the format **SWIFT itself migrated to** via the
CBPR+ programme), and this module translates between that wire and the
canonical **kotoba EAVT Datom log**.

## Why this exists

kawase-yui settles adherent-to-adherent over **Base L2 stablecoins**
(USDC/EURC/…), never fiat. But an adherent *on/off-ramps* through the real
banking system, which speaks ISO 20022. When a real bank credit transfer
touches a kawase corridor, it must become **auditable, append-only kotoba
history** (Wellbecoming `as-of`, no mutation). This codec is the format
layer that makes that ingress possible without taking on a proprietary
vendor dependency.

## Scope (what this is — and is NOT)

| | |
|---|---|
| **Is** | a pure XML **codec** + open-standard validators + kotoba Datom mapping |
| **Is** | cleanroom — implemented from the public ISO 20022 element grammar only |
| **Is NOT** | a network client — it opens no socket, calls no bank, joins no SWIFT |
| **Is NOT** | a money-movement path — no chain, no transfer, no custody |
| **Is NOT** | a Travel-Rule / FATF passport-KYC engine — the **Adherent SBT remains the KYC** (kawase-yui G10) |
| **Is NOT** | a chargeback/reversal path — ingress Datoms are assertion-only, never retracted (kawase-yui G11 mirror) |
| **Is NOT** | a commercial-MSB integration — no Wise/WU/MoneyGram/etc. (kawase-yui G7) |

## Cleanroom provenance

Every wire detail comes from the **open published standard**, not vendor code:

- **Message structure** — `GrpHdr` / `PmtInf` / `CdtTrfTxInf` / `PmtId` /
  `IntrBkSttlmAmt` / `OrgnlGrpInfAndSts` … from the ISO 20022 message
  components.
- **Namespace** — the official URN scheme
  `urn:iso:std:iso:20022:tech:xsd:<msgdef>` (e.g.
  `urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08`), emitted as the
  canonical default-namespace `<Document xmlns="…">` form.
- **Embedded identifiers** — validated by independent reimplementations of
  the *open* identifier standards: **ISO 13616** IBAN (check digits via
  **ISO 7064 MOD 97-10**, the full SWIFT IBAN-registry country-length set),
  **ISO 9362** BIC, **ISO 4217** currency, and the ISO 20022
  `ActiveCurrencyAndAmount` lexical constraints.

This is the same cleanroom posture warifu applied to ISO 8583 in
`50-infra/warifu-gateway/` — facts of an open standard are not
copyrightable expression, so a clean reimplementation is charter-clean
(Charter Rider §2(c) vendor data-sovereignty + §2(e) anti-gatekeeping).

## Supported message definitions

Version-parameterised; defaults follow widely-deployed CBPR+/SEPA versions.

| Def | Name | Default version | Direction |
|---|---|---|---|
| **pain.001** | CustomerCreditTransferInitiation | `pain.001.001.09` | ingress (a party instructs a transfer) |
| **pacs.008** | FIToFICustomerCreditTransfer | `pacs.008.001.08` | inter-bank leg (the SWIFT/CBPR+ carrier) |
| **pacs.002** | FIToFIPaymentStatusReport | `pacs.002.001.10` | acceptance / rejection / pending ack |
| **pacs.004** | PaymentReturn | `pacs.004.001.09` | reversal (a settled transfer sent back) |
| **camt.053** | BankToCustomerStatement | `camt.053.001.08` | reconciliation (end-of-day account statement) |
| **camt.054** | BankToCustomerDebitCreditNotification | `camt.054.001.08` | reconciliation (debit/credit notification) |
| **pain.002** | CustomerPaymentStatusReport | `pain.002.001.10` | pain-side ack of a pain.001 |
| **head.001** | BusinessApplicationHeader (BAH) | `head.001.001.02` | **mandatory CBPR+ wrapper** around every message |

Pass `version=` to any `build_*` / `parse_*` to target a different release.

### CBPR+ Business Application Header (head.001)

A bare `Document` is **not** a valid CBPR+ message on the SWIFT network — it
must be wrapped in a Business Application Header. This module builds the BAH
and pairs it with its `Document` in an `<Envelope>`, enforcing the CBPR+
rule that the header's `MsgDefIdr` must match the wrapped message:

```python
from kotoba_iso20022 import build_business_message, parse_business_message
from kotoba_iso20022.model import BusinessApplicationHeader

bah = BusinessApplicationHeader(
    from_bic="DEUTDEFF", to_bic="NWBKGB2L",
    business_message_id="BMID-2026-0608-1",
    message_definition="pacs.008.001.08",   # MUST match the document
    creation_datetime="2026-06-08T09:30:00Z",
    business_service="swift.cbprplus.02",
)
envelope = build_business_message(bah, pacs008_xml)   # <Envelope><AppHdr/><Document/></Envelope>
header, document_xml = parse_business_message(envelope)  # raises on MsgDefIdr mismatch
```

### CBPR+ Usage-Guideline conformance (the rulebook over the grammar)

The codec implements the *base ISO 20022* grammar; SWIFT **CBPR+** layers a
Usage Guideline of extra constraints on top. `conformance.py` is the
cleanroom implementation of those rules — a base-valid `pacs.008` can still
be a non-conformant CBPR+ message, and this catches it before the wire:

```python
from kotoba_iso20022 import check_cbpr_pacs008, assert_cbpr_pacs008
issues = check_cbpr_pacs008(msg)   # list[ConformanceIssue(rule_id, severity, location, message)]
assert_cbpr_pacs008(msg)           # raises CbprConformanceError on any error-level issue
```

| Rule | Constraint |
|---|---|
| `CBPR-001` | `GrpHdr/NbOfTxs` equals the actual `CdtTrfTxInf` count |
| `CBPR-002/003` | UETR mandatory and a lowercase **UUIDv4** |
| `CBPR-004` | `IntrBkSttlmAmt` present with a valid ISO 4217 amount |
| `CBPR-005` | `ChrgBr` ∈ {DEBT, CRED, SHAR} (SLEV is SEPA, not CBPR+) |
| `CBPR-006/007` | `DbtrAgt`/`CdtrAgt` need a valid BICFI; Name not allowed alongside BICFI |
| `CBPR-008` | `CtrlSum`, if present, equals the sum of settlement amounts |
| `CBPR-009` | Debtor and Creditor names mandatory |
| `CBPR-010/011` | BAH `MsgDefIdr` matches; `BizSvc` is a `swift.cbprplus.*` service |

Non-adjudicating and deterministic — it reports findings, it does not move
money, sign, or transact (kawase G2/G13 stay with the gated ingress cell).

### Reconciliation (camt → ingress loop-close)

A `camt.053`/`camt.054` entry that carries an `EndToEndId` maps to the
**same** content-addressed transaction entity as the original
`pain.001`/`pacs.008` ingress, so an inbound bank statement/notification
*reconciles against* the earlier message instead of creating a parallel
record — the off-ramp closing the loop in the kotoba Datom log:

```python
from kotoba_iso20022 import parse_camt054, to_datoms
report = parse_camt054(camt054_xml)
datoms = to_datoms(report)   # entry facts land on com.etzhayyim.iso20022/tx:<EndToEndId>
```

## Usage

```python
from decimal import Decimal
from kotoba_iso20022 import build_pacs008, parse_pacs008, to_datoms
from kotoba_iso20022.model import *

tx = CreditTransferTransaction(
    end_to_end_id="E2E-0001",
    tx_id="TX-0001",
    uetr="dced6a36-9e4b-4e2a-8b9f-2f3a4b5c6d7e",
    interbank_amount=Amount(Decimal("1000.00"), "EUR"),
    interbank_settlement_date="2026-06-08",
    charge_bearer="SLEV",
    debtor=Party("Alice Cohen"),
    debtor_account=Account(iban="DE89370400440532013000"),
    debtor_agent=Agent(bicfi="DEUTDEFF"),
    creditor_agent=Agent(bicfi="NWBKGB2L"),
    creditor=Party("Bob Levi"),
    creditor_account=Account(iban="GB29NWBK60161331926819"),
)
gh = GroupHeader(message_id="MSG-1", creation_datetime="2026-06-08T09:30:00Z",
                 number_of_txs=1, settlement_method="CLRG")
msg = FIToFICustomerCreditTransfer(group_header=gh, transactions=(tx,))

xml = build_pacs008(msg)        # → canonical ISO 20022 <Document xmlns="urn:…">
back = parse_pacs008(xml)       # → round-trips back to the dataclass
datoms = to_datoms(back)        # → append-only kotoba EAVT facts (ingress wire)
```

The Datom entity handle is **content-addressed on the message's own
immutable identifiers** (UETR → TxId → EndToEndId), so re-ingesting the
same message is idempotent and a later `pacs.002` status lands on the
*same* transaction entity.

### kawase-yui bridge (ingressAttestation Lexicon records)

`bridge.py` shapes the same value-events into
`com.etzhayyim.iso20022.ingressAttestation` AT-Protocol records (Lexicon at
`00-contracts/lexicons/com/etzhayyim/iso20022/`) so a kawase corridor can
attest an external bank transfer and, where it corresponds to an on-chain
on-ramp, reconcile it against a `com.etzhayyim.kawase.depositAttestation`
via `linkedDepositCid`:

```python
from kotoba_iso20022 import ingress_attestations
records = ingress_attestations(
    msg,
    ingested_at="2026-06-08T23:00:00Z",
    cbpr_conformant=True,            # carry the CBPR+ verdict onto the record
    linked_deposit_cid="bafy…",      # reconcile vs a kawase depositAttestation
)
# one record per pacs.008/pain.001 transaction or camt.053/054 entry
```

**PII discipline (kawase-yui G10)**: party names are 要配慮 PII and are
**omitted by default**; `include_party_names=True` is opt-in for a
consent-bound / encrypted path. Only institution BICs (ISO 9362) are
first-class. Status-only messages (pacs.002 / pain.002) are rejected — their
status is carried by `to_datoms`, not the value-event record.

## Layout

```
kotoba_iso20022/
├── validate.py   # ISO 13616 IBAN / ISO 9362 BIC / ISO 4217 ccy / amount
├── model.py      # frozen-dataclass domain model (GrpHdr / CdtTrfTxInf / …)
├── codec.py        # build + parse XML for pain.001/002 / pacs.008/002 / camt.053/054
├── bah.py          # head.001 BAH + CBPR+ business-message envelope (MsgDefIdr match)
├── conformance.py  # CBPR+ Usage-Guideline rule checks over the parsed model
├── datoms.py       # message → kotoba EAVT Datom ingress + reconciliation mapping
├── bridge.py       # message → com.etzhayyim.iso20022.ingressAttestation records
├── helpers.py      # new_uetr() + auto NbOfTxs/CtrlSum group-header builders
└── __init__.py     # public surface
tests/              # 231 tests · 97% branch / 99% line · mypy --strict + ruff clean
```

## Construction helpers

`helpers.py` removes the two most common ways a hand-built message fails
CBPR+ conformance — a miscounted `NbOfTxs` and a mismatched `CtrlSum`:

```python
from kotoba_iso20022 import new_uetr, pacs008_group_header
tx = CreditTransferTransaction(end_to_end_id="E", uetr=new_uetr(), ...)
gh = pacs008_group_header("MSG-1", "2026-06-08T09:30:00Z", (tx,))  # NbOfTxs+CtrlSum derived
```

## Tests

```bash
cd 40-engine/kotoba_iso20022
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python3 -m pytest tests/ -q
# → 207 passed

# with coverage (pip install coverage):
PYTHONPATH=. coverage run -m pytest tests/ -q && coverage report
# → 95% branch / 98% line

# static typing (pip install mypy): the package passes --strict clean
PYTHONPATH=. mypy kotoba_iso20022 --strict
# → Success: no issues found
```

CI enforces all of the above on every PR via
`.github/workflows/kotoba-iso20022-ci.yml` (ruff lint + pytest on Python
3.11–3.13 + `mypy --strict` + `coverage --fail-under=90` + Lexicon validation).

IBAN test vectors are the published ISO 13616 registry examples (DE/GB/FR/
CH/BE); BIC vectors are real ISO 9362 codes. See `CHANGELOG.md` for the
full surface.

## Charter & substrate alignment

- **G2 / G13** — output is kotoba EAVT Datoms (content-addressed); this
  module *maps* but does not transact (the gated kawase ingress cell does).
- **G10** — no Travel-Rule KYC; Adherent SBT is the KYC.
- **G11** — ingress Datoms are assertion-only (`op=True`), never retracted.
- **No-server-key** — pure function; no signing, no key material.
- **Inference-free** — deterministic codec; no Murakumo/LLM call (no G12
  surface).

## Roadmap

- ✅ `camt.053` / `camt.054` (statement + debit/credit notification) for the
  off-ramp reconciliation direction — **shipped**, entries reconcile against
  the ingress tx entity via `EndToEndId`.
- A gated `kawase` ingress cell that calls `to_datoms` and transacts under
  G2/G13 (Council-ratified, post-RFP).
- ✅ Lexicon mapping `com.etzhayyim.iso20022.ingressAttestation` ↔
  `com.etzhayyim.kawase.depositAttestation` for corridor reconciliation —
  **shipped** (`bridge.py` + Lexicon).
- A gated `kawase` ingress cell that calls `ingress_attestations` +
  `to_datoms` and transacts under G2/G13 (Council-ratified, post-RFP).
- ISO 20022 XSD conformance harness (optional dev-time check against the
  official schema files; runtime stays schema-file-free).
- ✅ `pain.002` customer payment-status report — **shipped**.
- ✅ `head.001` Business Application Header + CBPR+ envelope — **shipped**.

## Related

- `90-docs/adr/2605282200-kawase-yui-multi-stable-adherent-remittance-mutual-aid.md` — consuming actor
- `40-engine/kotoba_kawase/` — kawase-yui Python facade (sibling)
- `50-infra/warifu-gateway/iso8583-map.md` — sibling cleanroom (card-side ISO 8583)
- `90-docs/adr/2605262130` + `2605312345` — kotoba Datom first-class state
- `/CHARTER-RIDER.md` — §2(c) + §2(e) cleanroom basis
