# ISO 20022 XSD conformance — evidence of 2026-11-18

Tracking: [AWAI-3153](https://linear.app/kotobalabs/issue/AWAI-3153), under
[AWAI-3149](https://linear.app/kotobalabs/issue/AWAI-3149). Level names (L1/L2/L3)
are those of network-awai-apex ADR 0042 D2.

This directory checks the XML that `kotoba.swift` and `kotoba.kotobaIso20022`
emit against the public ISO 20022 XSDs (level **L1, syntax**). It records what
was found. **Nothing was fixed in this change**; each mismatch below is a
separate follow-up.

**Result: neither library emits schema-valid documents for the messages it
claims, except `head.001.001.02` (Python). No ISO 20022 message from these
libraries may be described as L1-conformant yet.**

## How to run

From the repository root:

```bash
lib/kotoba.swift/conformance/check.sh
```

| File | Role |
|---|---|
| `xsd-pins.edn` | The eight XSDs: source URL and SHA-256. The XSDs are downloaded at run time and not stored here |
| `samples.cljk` | Builds one pain.001.001.09 and one pacs.008.001.08 with `kotoba.swift.iso20022` |
| `dump_plugin.py` | pytest plugin: records every document the Python codec builds while its own test suite runs |
| `summarize.py` | Validates every recorded document with `xmllint --schema` and groups the errors |
| `results-20261118.json` | The summary of the run below |

This is a local evidence run, not a CI gate. The monorepo CI runs the native
qualification jobs only and does not run library tests; adding a job for this
check is a separate decision (see "Not covered").

## Run of 2026-11-18

| Item | Value |
|---|---|
| Repository revision | `109d0ccbdda2b6c62494b57952013bee6c12d4c3` |
| XSD source | iso20022.org message archive, retrieved 2026-11-18, digests in `xsd-pins.edn` |
| Validator | `xmllint` (libxml 2.9.13, macOS system) |
| `kotoba.swift` runner | `kbb --backend sci`, explicit classpath from `lib/` |
| Python runner | Python 3.14.6, pytest 9.0.3; the suite reported 233 passed |
| Documents checked | 785 (2 from `kotoba.swift`, 783 from the Python suite) |
| Summary digest | `results-20261118.json` sha256 `19406d51c495d96ac77607f7f150ddb81b4cd4cbec1b5b98ca0d120453db677d` |

| Message | Documents | XSD-valid |
|---|---|---|
| pain.001.001.09 | 254 (1 kotoba.swift) | 0 |
| pacs.008.001.08 | 265 (1 kotoba.swift) | 103 (all Python) |
| pacs.002.001.10 | 3 | 2 |
| pacs.004.001.09 | 2 | 1 |
| pain.002.001.10 | 2 | 1 |
| camt.053.001.08 | 3 | 0 |
| camt.054.001.08 | 252 | 0 |
| head.001.001.02 | 2 | 2 |
| Envelope (AppHdr + Document) | 2 | not checked: no public XSD pinned |

The Python suite includes property tests that build documents from
deliberately odd inputs (for example a `CreDtTm` of `"t"`). A handful of the
errors in `results-20261118.json` come from those inputs and say only that the
codec does not reject them (P6). The findings below are the ones that occur
with ordinary inputs.

## Findings — `kotoba.swift` (`lib/kotoba.swift/src/kotoba/swift/iso20022.cljk`)

Both documents parse back to the same tree (`parse-xml` round-trip holds),
and `validate-iso20022` accepts them, yet both fail the XSD.

| # | Message | Mismatch | Effect |
|---|---|---|---|
| K1 | both | `xml->str` emits every leaf value on its own indented line (`<MsgId>\n        MSG-2\n      </MsgId>`). XSD simple types do not allow that whitespace | Every value fails its type: dates, counts, codes, UETR, BIC, IBAN. `parse-xml` trims text, so the round-trip test cannot see it |
| K2 | pain.001.001.09 | `PmtInf/ReqdExctnDt` holds the date as text. In .09 it is `DateAndDateTime2Choice` and needs a `Dt` or `DtTm` child | Every pain.001 fails |
| K3 | pacs.008.001.08 | In `CdtTrfTxInf`, `DbtrAgt` is emitted before `Dbtr`/`DbtrAcct`. The XSD sequence is `Dbtr`, `DbtrAcct`, `DbtrAgt`, then `CdtrAgt` | Every pacs.008 fails |
| K4 | both | `validate-iso20022` reports `valid? true` for documents the XSD rejects | The library's own check cannot be used as a conformance claim |

With whitespace removed and K2 and K3 corrected by hand, both sample
documents validated against their XSDs. No other mismatch was found for the
element subset these builders emit.

## Findings — `kotoba.kotobaIso20022` (Python)

| # | Message | Mismatch | Documents affected |
|---|---|---|---|
| P1 | pain.001.001.09 | `ReqdExctnDt` holds the date as text instead of a `Dt`/`DtTm` child (same as K2) | all 253 |
| P2 | pacs.008.001.08 | `ChrgBr` is mandatory in every `CdtTrfTxInf`, but the codec omits it whenever the model's charge bearer is unset. Multi-transaction messages fail when any later transaction lacks it | nearly all of the 161 invalid out of 264 (a few also carry odd test inputs) |
| P3 | camt.053/054.001.08 | `Ntry/Sts` is emitted as text; in .08 it is `EntryStatus1Choice` and needs a `Cd` child | camt.054: all 252; camt.053: 2 of 3 |
| P4 | camt.053/054.001.08 | `Ntry/BkTxCd` is mandatory and must come before `NtryDtls`; it is often missing. When present, `Domn` lacks the mandatory `Fmly`. In camt.053, `Stmt/Bal` (mandatory) is missing before `Ntry` | many; see `results-20261118.json` |
| P5 | pain.002.001.10 | `TxInfAndSts/OrgnlTxId` is emitted, but pain.002 has no such element (it exists in pacs.002) | 1 of 2 |
| P6 | all | The codec does not validate `ISODateTime`, `NbOfTxs`, code values, UETR, BIC or IBAN before emitting them | test inputs only |

`head.001.001.02` validated. `pacs.002.001.10` and `pacs.004.001.09` validated
for every ordinary input.

The CBPR+ rules in `conformance.py` (CBPR-001 to CBPR-011) are level L2. They
were not checked here: their source documents are subject to ADR 0042 O3.

## MT103 ↔ pacs.008.001.08 mapping (`kotoba.swift`)

The library has no conversion function between MT and MX. This table compares
what `mt103` and `pacs008-doc` can each carry, so that a later converter knows
where data would be lost.

| MT103 field (modeled) | pacs.008.001.08 element | `pacs008-doc` |
|---|---|---|
| 20 sender's reference | `PmtId/InstrId` | carried (optional) |
| 23B bank operation code | `PmtTpInf` (no 1:1 element) | not modeled |
| 32A value date | `IntrBkSttlmDt` | **not modeled** |
| 32A currency, amount | `IntrBkSttlmAmt` | carried |
| 33B instructed amount | `InstdAmt` | not modeled |
| 50K ordering customer: account | `DbtrAcct/Id` | IBAN only (`Othr` not modeled) |
| 50K ordering customer: name and address | `Dbtr/Nm`, `Dbtr/PstlAdr` | name only, address lost |
| 52A ordering institution | `DbtrAgt/FinInstnId/BICFI` | carried |
| 57A account with institution | `CdtrAgt/FinInstnId/BICFI` | carried |
| 59 beneficiary: account | `CdtrAcct/Id` | IBAN only |
| 59 beneficiary: name and address | `Cdtr/Nm`, `Cdtr/PstlAdr` | name only, address lost |
| 70 remittance information | `RmtInf/Ustrd` | **not modeled** |
| 71A details of charges (OUR/BEN/SHA) | `ChrgBr` (DEBT/CRED/SHAR) | carried; the code mapping is not written down |
| 72 sender to receiver information | `InstrForCdtrAgt`, `InstrForNxtAgt` | not modeled |
| block 3 field 121 (UETR) | `PmtId/UETR` | carried by pacs.008; `mt103` emits an empty block 3, so UETR is lost on the MT side |
| block 1/2 sender and receiver BIC | `InstgAgt`, `InstdAgt` | not modeled (optional in the base XSD) |

## Not covered

- L2 (usage guidelines such as CBPR+) and L3 (acceptance by a bank). L2
  waits on ADR 0042 O3; L3 on O5.
- SWIFT MT syntax. There is no public machine-readable MT schema; MT field
  checks wait on O3.
- The `Envelope` documents built by `build_business_message`, which wrap
  `AppHdr` and `Document`. No public XSD for the wrapper is pinned.
- Messages the libraries do not build (pacs.009, camt.053 variants beyond the
  test suite, securities messages; the latter are AWAI-3154).
- CI. The monorepo CI runs native qualification jobs only. Running this
  check in CI would need a separate oracle job (Python and xmllint); whether
  to add one is an owner decision.
