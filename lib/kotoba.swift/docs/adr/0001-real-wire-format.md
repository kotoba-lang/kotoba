# ADR-0001 — Upgrade from placeholder EDN to real SWIFT MT / ISO 20022 wire format

- Status: Accepted
- Date: 2026-07-14
- Context tags: swift, iso20022, banking, wire-format, cloud-itonami-isic-6493

## Context

The prior version of `kotoba-swift` modeled SWIFT MT messages and ISO 20022
envelopes as plain EDN records, explicitly documented as a deliberate
simplification: "SWIFT MT on the wire uses `{1:...}{4:...}` brace blocks and
ISO 20022 is XML; here both are EDN." That was a reasonable placeholder for
an early capability library, but it means nothing built against it could be
handed to a licensed financial institution and plugged into a real banking
backend without a rewrite — the wire shape simply wasn't real.

`cloud-itonami-isic-6493` (a factoring-business governed actor) and its
planned deployment need genuinely standards-accurate banking-message
capability, even though no live SWIFTNet/bank connection is attached from
this codebase (that requires a licensed financial institution, out of scope
here — see the library's "Why" section). The instruction from the owner was
explicit: implement code that is **genuinely identical to the real
specification**, not a simplified approximation, so a licensed operator
could plug this in downstream with minimal translation work.

## Decision

Replace the EDN placeholder with:

1. **Real SWIFT MT wire-format generation and lossless parsing** for
   **MT103** (Single Customer Credit Transfer) and **MT202** (General
   Financial Institution Transfer) — the actual
   `{1:...}{2:...}{3:...}{4:...}{5:...}` brace-block structure, real field
   tags (`:20:`, `:23B:`, `:32A:`, `:50K:`, `:59:`, `:70:`, `:71A:`, etc.),
   round-tripping generate → parse → structurally-equal-to-input.
2. **Real ISO 20022 XML generation and lossless parsing** for
   **pain.001.001.09** (CustomerCreditTransferInitiation) and
   **pacs.008.001.08** (FIToFICustomerCreditTransfer) — the real element
   hierarchy (`GrpHdr`/`PmtInf`/`CdtTrfTxInf`/`Dbtr`/`CdtrAgt`/etc.) and the
   real XML namespace URIs, emitted as actual well-formed XML strings via
   [`kotoba-lang/xml`](https://github.com/kotoba-lang/xml) (a dependency-free
   Hiccup→XML emitter already in this fleet, matching the
   `kotoba-lang/html`+`kotoba-lang/css` dependency pattern this library
   already used for its operator console), and parsed back by a minimal
   recursive-descent parser scoped to this library's own generated
   documents.
3. Keep BIC (ISO 9362) validation/parsing unchanged — it was already
   correct.
4. Keep the "no network, no I/O" purity. This is message
   CONSTRUCTION/PARSING, not a network client.
5. Split the growing surface into `kotoba.swift` (BIC + MT wire format) and
   a new `kotoba.swift.iso20022` (ISO 20022 XML) namespace, mirroring the
   existing `kotoba.swift.export`/`kotoba.swift.ui` sub-namespace
   convention rather than growing one file unboundedly.

## Verified against

Every field tag, format constraint, and element name below was checked
against a public source before being encoded — none were reconstructed from
memory. Full field lists were captured via `WebFetch` against the actual
detail pages, not re-typed from a summary.

**SWIFT MT block structure:**
- Block 1 (Basic Header) exact character layout (AppID(1) + ServiceID(2) +
  LT-address(12) + Session(4) + Sequence(6)) and a worked example
  `{1:F01CITIFRPPAXXX0070970817}` — paymentsdomain.com ("SWIFT MTs – Blocks
  1 Through 5").
- Block 2 (Application Header, Input) exact layout and worked example
  `{2:I103NDEANOKKBXXXU3003}` — Prowide Software's SWIFT MT developer guide
  (`dev.prowidesoftware.com/latest/getting-started/swift/swift-mt/`).
- Block 3/5 sub-block shape (`{3:{108:...}}`, `{5:{CHK:...}}`) and the
  block-4 `-}` termination sequence — a full raw MT103 example string ending
  `... :71A:SHA -}` from swiftmt103.com ("MT103 Format").
- Block-1/2/3 general five-block overview cross-checked against
  paiementor.com ("SWIFT MT Message Structure Blocks 1 to 5") and
  swiftfinguru.com.

**MT103 field list (tag, name, mandatory/optional, format):** full table —
20, 13C, 23B, 23E, 26T, 32A, 33B, 36, 50a, 51A, 52a, 53a, 54a, 55a, 56a, 57a,
59a, 70, 71A, 71F, 71G, 72, 77B — captured from iotafinance.com's SWIFT
ISO15022 MT103 detail view. Only the subset documented in `kotoba.swift`'s
`mt103` docstring is implemented.

**MT202 field list:** full table — 20, 21, 13C, 32A, 52a, 53a, 54a, 56a,
57a, 58a, 72 — captured from iotafinance.com's SWIFT ISO15022 MT202 detail
view. Only the subset documented in `kotoba.swift`'s `mt202` docstring is
implemented.

**Field-format rules:**
- Field 32A's `6!n3!a15d` composite format and the rule that "a decimal
  comma is mandatory and is included in the maximum length" (why
  `format-mt-amount` always emits the comma even at 0 decimals) —
  paiementor/iotafinance field-32A descriptions surfaced during the MT202
  field search.
- Field 20/21 reference-shape usage rule (must not start/end with `/`, must
  not contain `//`, error code T26) — knowledge.xmldation.com's Field 20
  reference page.
- Field 23B valid codes CRED/CRTS/SPAY/SPRI/SSTD (CRTS flagged as not for
  live FIN use) — SWIFT Standards MT Category 1 field-23B references
  (pinas.synology.me mirror of the SWIFT Standards manual,
  xmldation.com knowledgebase).
- Field 71A valid codes OUR/SHA/BEN and their real-world meaning —
  sepaforcorporates.com / paymentbrief.com / flywire.com's OUR/SHA/BEN
  explainers (cross-checked across multiple independent sources for the
  same three-code enumeration).

**ISO 20022:**
- pain.001.001.09 namespace `urn:iso:std:iso:20022:tech:xsd:pain.001.001.09`
  and element hierarchy (`GrpHdr`: MsgId/CreDtTm/NbOfTxs/CtrlSum/InitgPty;
  `PmtInf`: PmtInfId/PmtMtd/NbOfTxs/CtrlSum/ReqdExctnDt/Dbtr/DbtrAcct/
  DbtrAgt/ChrgBr; `CdtTrfTxInf`: PmtId(EndToEndId/InstrId/UETR)/Amt(InstdAmt
  Ccy)/CdtrAgt/Cdtr/CdtrAcct/RmtInf) — docs.lhv.com's pain.001.001.09 format
  guide (LHV Connect documentation), cross-checked against
  developer.huntington.com's pain001 docs and pain001.com.
- pacs.008.001.08 namespace `urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08`
  and a full worked XML example (`FIToFICstmrCdtTrf`/`GrpHdr`/`SttlmInf`/
  `CdtTrfTxInf` with `IntrBkSttlmAmt`, `UETR`, per-transaction `Dbtr`/
  `DbtrAgt`/`CdtrAgt`/`Cdtr`) — ohmyfin.ai's pacs.008 explainer, which is
  the direct source for pacs.008 carrying debtor/creditor **per
  transaction** rather than in a shared block (unlike pain.001's PmtInf).
- `ChargeBearerType1Code` external code list (DEBT/CRED/SHAR/SLEV) —
  knowledge.xmldation.com's ChrgBr reference and mx-message.com's
  pain.001.001.11 ChrgBr field page (cross-checked, same four-code
  enumeration).
- `SttlmMtd` (SettlementMethod1Code): only the value `INDA` was
  independently confirmed (present in the ohmyfin.ai worked example);
  the full code-list enumeration was **not** independently verified, so
  `kotoba.swift.iso20022` validates it only by shape (`4!a`), not against a
  fixed value set — see the honesty note in `pacs008-doc`'s docstring.

Where a source could not be corroborated with a second independent
reference (the `SttlmMtd` code list above), the implementation deliberately
validates only what was verified, rather than guessing at the rest.

## What this explicitly does NOT cover

- SWIFT MT: only MT103/MT202, not the full category catalogue. Within those
  two types, only the field subset each builder's docstring lists — see
  `kotoba.swift`'s `mt103`/`mt202` docstrings for the exact NOT-modeled tag
  list (13C, 23E, 26T, 36, 50A/50F, 51A, 53a-56a for MT103, 59A/59F, 71F,
  71G, 77B, etc.). Block 2 Output direction (a received message) is parsed
  only as an opaque `:swift/direction :output` marker, not decoded.
  Block 5's `CHK` is an opaque trailer subfield — SWIFT's proprietary
  checksum algorithm is not implemented.
- ISO 20022: only pain.001.001.09/pacs.008.001.08, not the full message
  catalogue (no camt.05x statements, no pacs.002/004/009, etc.). Within
  those two, no `PstlAdr`, no ultimate debtor/creditor, no payment
  purpose/category-purpose codes, no structured remittance.
- No XSD schema validation — `validate-iso20022` checks the structural
  presence of the elements this library itself models, not conformance to
  the real published XSD.
- No connection to SWIFTNet, FIN, or any bank. This library never will
  connect to a live banking network from this codebase; that step requires
  a licensed financial institution.

## Consequences

- A licensed operator plugging `kotoba.swift`/`kotoba.swift.iso20022` into
  a real banking backend gets a genuinely correct MT103/MT202 wire encoder
  and pain.001/pacs.008 XML encoder for the fields modeled — translation
  work is additive (more fields, more message types), not corrective
  (fixing a wrong wire shape).
- `kotoba.swift.ui`/`kotoba.swift.export` now render/export the real wire
  string and real XML, so an operator console or audit export shows exactly
  what would go over the wire, not an internal EDN approximation of it.
- `kotoba.swift.mt-message`/`kotoba.swift.iso-20022-envelope` (the old
  placeholder API) are removed, not deprecated-and-kept, because a survey
  of this superproject's consumers found only `kotoba-lang/kessai`
  depending on `kotoba.swift`, and only on `bic-valid?` (unchanged) — so
  the blast radius of the breaking change was verified to be zero before
  taking it.
- Test coverage grew from 42 assertions (BIC + placeholder EDN shape) to
  207 assertions (BIC unchanged + real MT wire round-trips for MT103/MT202
  + real XML round-trips for pain.001/pacs.008 + malformed-input rejection
  for both), covering the added wire-format surface at comparable rigor to
  the rest of this fleet's capability libraries.

## Rejected alternatives

- **Depend on a JVM-only SWIFT/ISO 20022 library** (e.g. Prowide's WMQ/
  Integrator products). Rejected: this repo's runtime priority order is
  kotoba wasm → clojurewasm → ClojureScript → nbb, with JVM demoted to a
  last resort; a JVM-only dependency would break portability to
  ClojureScript/SCI/GraalVM that this `.cljc` library currently has.
- **Use `clojure.data.xml` or a JVM XML parser for ISO 20022.** Rejected
  for the same portability reason — `clojure.data.xml` is JVM-only.
  `kotoba-lang/xml`'s dependency-free Hiccup→XML emitter plus a small
  hand-rolled recursive-descent parser (scoped to this library's own
  generated documents, not general-purpose XML) keeps the library
  `.cljc`-portable with no new runtime dependency surface.
- **Implement the full SWIFT MT category catalogue / full ISO 20022 message
  catalogue in one pass.** Rejected as scope creep for this upgrade — two
  message types per standard (MT103/MT202, pain.001/pacs.008) covers the
  wire-transfer and FI-to-FI-transfer use cases `cloud-itonami-isic-6493`
  actually needs, verified accurately, rather than a larger surface
  verified thinly.
