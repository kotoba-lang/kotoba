# Changelog — kotoba_iso20022

All notable changes to the cleanroom ISO 20022 codec. Pre-1.0; the public
surface in `kotoba_iso20022/__init__.py` is the compatibility contract.

## [0.1.0] — unreleased

Cleanroom ISO 20022 payment-message codec for the kawase-yui interop wire,
built purely from the open published standard (no proprietary SWIFT SDK).

### Messages
- **pain.001** CustomerCreditTransferInitiation — build + parse
- **pain.002** CustomerPaymentStatusReport — build + parse
- **pacs.008** FIToFICustomerCreditTransfer — build + parse
- **pacs.002** FIToFIPaymentStatusReport — build + parse
- **pacs.004** PaymentReturn — build + parse (reversal reconciliation)
- **camt.053** BankToCustomerStatement — build + parse
- **camt.054** BankToCustomerDebitCreditNotification — build + parse
- **head.001** Business Application Header + CBPR+ `<Envelope>` (BAH
  `MsgDefIdr` ↔ Document match enforced)

### Validation
- ISO 13616 IBAN (ISO 7064 MOD 97-10), ISO 9362 BIC, ISO 4217 currency,
  ISO 20022 `ActiveCurrencyAndAmount` constraints, CBPR+ UETR (UUIDv4)

### CBPR+ conformance
- `conformance.py` — 11 Usage-Guideline rules (CBPR-001…011): NbOfTxs,
  UETR mandatory + UUIDv4, settlement amount, ChrgBr ∈ {DEBT,CRED,SHAR},
  agent BICFI required + no-Name-with-BICFI, CtrlSum, party names, BAH
  MsgDefIdr + `swift.cbprplus.*` BizSvc

### kotoba / kawase integration
- `datoms.py` — message → append-only EAVT facts; content-addressed entity
  (UETR→TxId→EndToEndId); camt entries reconcile onto the ingress entity
- `bridge.py` + `com.etzhayyim.iso20022.ingressAttestation` Lexicon —
  one record per transaction/entry; `linkedDepositCid` reconciles against
  `com.etzhayyim.kawase.depositAttestation`; party names omitted by default
  (kawase-yui G10 PII discipline)

### Helpers
- `helpers.py` — `new_uetr()`, `control_sum_of()`,
  `pacs008_group_header()` / `pain001_group_header()` (auto NbOfTxs +
  CtrlSum so a hand-built message satisfies CBPR-001/008)

### Quality
- Dependency-free (stdlib only), Python ≥ 3.11
- 231 tests, 97% branch / 99% line coverage
- Passes `mypy --strict` clean (all 9 modules)
- Full SWIFT IBAN-registry country-length set (ISO 13616); breadth
  round-trip + cross-currency (incl. 0- and 3-fraction-digit) tests
- Property-based serialization-idempotence fuzz (seeded, 750+ generated
  messages: build(parse(build(m)))==build(m)) + golden wire-bytes regression lock
- CI gate `.github/workflows/kotoba-iso20022-ci.yml`: ruff lint + pytest
  (Python 3.11–3.13) + `mypy --strict` + `coverage --fail-under=90` +
  Lexicon validation, on push/PR/nightly
- ruff-clean (E/F/W/B/UP/SIM/I/C4/PIE/RET); PEP 604 unions throughout
- Charter-clean: format library only — no network, no chain, no money
  movement, no Travel-Rule KYC
