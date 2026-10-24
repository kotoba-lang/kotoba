# kotoba-swift

[![CI](https://github.com/kotoba-lang/swift/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/swift/actions/workflows/ci.yml)

**Real SWIFT MT wire format and real ISO 20022 XML, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library that gives
banking-adjacent actors in this fleet (e.g. `cloud-itonami-isic-6493`,
factoring) genuine message-construction/parsing capability for interbank
messaging — BIC (ISO 9362) identification, the actual
`{1:...}{2:...}{3:...}{4:...}{5:...}` SWIFT FIN brace-block wire format for
MT103 and MT202, and real generated/parsed ISO 20022 XML for pain.001.001.09
and pacs.008.001.08.

No network, no I/O — this is message CONSTRUCTION and PARSING only. It does
not connect to SWIFTNet or any bank; that requires a licensed financial
institution, out of scope for this codebase. Portable `.cljc` across JVM /
ClojureScript / SCI / GraalVM.

**This upgrades a prior placeholder.** An earlier version of this library
modeled MT messages and ISO 20022 envelopes as plain EDN records ("SWIFT MT
on the wire uses brace blocks and ISO 20022 is XML; here both are EDN"). That
placeholder is gone — see `docs/adr/0001-real-wire-format.md` for the
upgrade rationale and cited sources.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 207 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Scope — what's real, what's covered, what's NOT

This is **not** a full SWIFT Standards MT implementation or a full ISO 20022
message catalogue. It covers exactly:

- **SWIFT MT**: message types **MT103** (Single Customer Credit Transfer)
  and **MT202** (General Financial Institution Transfer) only, out of
  SWIFT's full MT category catalogue. Within those two types: the real
  Block 1 (Basic Header) / Block 2 (Application Header, **Input direction
  only** — a message this actor sends, not a received Output message) /
  Block 3 (User Header, generic pass-through) / Block 4 (Text Block, real
  field tags) / Block 5 (Trailer, generic pass-through) structure, generated
  as an actual brace-delimited wire string and parsed back losslessly.
  Field 50 (Ordering Customer) and field 59 (Beneficiary Customer) support
  only the plain name+address line form (option K / no-letter) — not the
  BIC-only (A) or structured (F) variants. Party/institution fields
  (52A/53A/54A/56A/57A/58A) support only the BIC (option A) form. Block 5's
  `CHK` value is an opaque trailer subfield — **this library does not
  implement SWIFT's proprietary checksum algorithm**. NOT modeled: fields
  13C, 23E, 26T, 36, 50A/50F, 51A, 59A/59F, 71F, 71G, 77B and others outside
  each builder's documented field list (see `kotoba.swift`'s `mt103`/`mt202`
  docstrings for the exact tag list).
- **ISO 20022**: message definitions **pain.001.001.09**
  (CustomerCreditTransferInitiation) and **pacs.008.001.08**
  (FIToFICustomerCreditTransfer) only, out of the full ISO 20022 message
  catalogue. Real element hierarchy and namespace, real generated XML
  (`<?xml ...?>` declaration + actual tags), parsed back losslessly. NOT
  modeled: postal address (`PstlAdr`), ultimate debtor/creditor, payment
  purpose/category-purpose codes, structured remittance, `camt.05x`
  statements, and most other optional branches of the real schema.
- Amounts are integers in the currency's minor unit (e.g. cents), matching
  `kotoba-lang/banking`'s convention — no BigDecimal assumption, and no
  full ISO 4217 minor-unit-per-currency table (pass `:decimals` for
  non-2-decimal currencies like JPY).
- Field-format validators (dates, amounts, code lists) only encode
  constraints independently verified against the sources below — this
  library does not invent or approximate constraints it hasn't verified,
  and it is **not a substitute for the licensed SWIFT Standards MT /
  ISO 20022 XSD documentation**.

### Verified against

Researched and cross-checked (not reconstructed from memory) against:
Standards MT field-tag reference pages (iotafinance.com MT103/MT202 detail
views), SWIFT MT block-structure references (paymentsdomain.com, Prowide
Software's `dev.prowidesoftware.com` SWIFT MT developer guide,
swiftmt103.com's raw-message example — the `-}`  block-4 termination and the
`{1:}{2:}{3:}` example strings are taken from these), SWIFT usage-rule
error-code T26 documentation (field 20/21 reference shape:
`knowledge.xmldation.com`), field 23B / 71A code-list references
(xmldation.com, sepaforcorporates.com and related), the ISO 20022 message
definition catalogue at iso20022.org together with implementation guides
that quote the real element hierarchy verbatim (docs.lhv.com's
pain.001.001.09 format guide, a real pacs.008.001.08 example at
ohmyfin.ai), and the ISO 20022 `ChargeBearerType1Code` external code list
(xmldation.com / mx-message.com). See `docs/adr/0001-real-wire-format.md`
for the full source list against each specific field/element claim.

## Contract

```clojure
(require '[kotoba.swift :as swift])

;; BIC (ISO 9362) — unchanged from the prior version
(swift/bic-valid? "DEUTDEFF500")            ; => true
(swift/parse-bic "DEUTDEFF500")             ; => {:swift/bank "DEUT" ...}
(swift/validate-bic "BAD")                  ; => {:swift/valid? false ...}

;; MT103 — real wire format
(def m (swift/mt103
         {:sender-bic "DEUTDEFFXXX" :receiver-bic "CHASUS33XXX"
          :transaction-reference "REF20260714" :bank-operation-code "CRED"
          :value-date "260714" :currency "USD" :amount-minor 150075
          :ordering-customer-name-address "ACME TRADING GMBH"
          :beneficiary-name-address "GLOBAL SUPPLIES INC"
          :details-of-charges "SHA"}))

(swift/mt->wire m)
;; => "{1:F01DEUTDEFFXXXX0001000001}{2:I103CHASUS33XXXXN}{4:\r\n:20:REF20260714\r\n...-}"

(= m (swift/parse-mt-wire (swift/mt->wire m)))  ; => true (lossless round trip)
(swift/validate-mt m)                            ; => {:swift/valid? true :swift/mt "103"}
```

```clojure
(require '[kotoba.swift.iso20022 :as iso])

(def doc (iso/pain001-doc
           {:msg-id "MSG-1" :creation-date-time "2026-07-14T09:30:00Z"
            :initiating-party-name "Acme Factoring Ltd" :payment-info-id "PMT-1"
            :requested-execution-date "2026-07-15" :charge-bearer "SLEV"
            :debtor-name "Acme Trading GmbH" :debtor-iban "DE89370400440532013000"
            :debtor-bic "COBADEFFXXX"
            :transactions [{:end-to-end-id "INV-1" :amount-minor 750000 :currency "USD"
                             :creditor-name "Global Supplies Inc"
                             :creditor-iban "GB82WEST12345698765432"
                             :creditor-bic "CHASUS33XXX"}]}))

(iso/xml->str doc)
;; => "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pain.001.001.09\">...</Document>"

(= doc (iso/parse-xml (iso/xml->str doc)))       ; => true (lossless round trip)
(iso/validate-iso20022 doc)                       ; => {:swift/valid? true :swift/message-type "pain.001.001.09"}
```

## Operator console (UI/UX)

A read-only HTML dashboard renders BIC validation, the **real MT wire
string**, and the **real ISO 20022 XML** for an operator (not the old EDN
shape). Built on [`kotoba-lang/html`](https://github.com/kotoba-lang/html)
(Hiccup→HTML) + [`kotoba-lang/css`](https://github.com/kotoba-lang/css)
(EDN→CSS). Pure data → markup; the console never exposes a write surface
(no `<form>`/`<button>`) — writes stay behind the governor.

```clojure
(require '[kotoba.swift.ui :as ui])

(ui/dashboard
  {:bics ["DEUTDEFF500" "BAD"]
   :messages [m]
   :iso20022-docs [doc]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (every C0 control character
escaped) for BIC validation, MT messages (including the real wire string),
and ISO 20022 documents (including the real generated XML).

```clojure
(require '[kotoba.swift.export :as ex])

(ex/bics->csv bics)
(ex/mt-messages->csv messages)          ; mt,valid,sender,receiver,reference,wire
(ex/iso20022-docs->csv docs)            ; message-type,valid,msg-id,xml
(ex/bics->json bics)
(ex/mt-messages->json messages)
(ex/iso20022-docs->json docs)
```

## Test

```sh
kbb -M:test
```

## Why

A community bank / factoring operator must prove, before a message is
committed, that the sender is identified, the message type is in a
permitted set, and the wire-format construction is structurally sound
against the real specification — not an approximation of it.
`kotoba-swift` is the pure-data + wire-format layer a `PolicyGovernor`
checks against before an actor commits anything; the actor decides
permission, the audit ledger records proof. No live SWIFTNet/bank
connection is attached here or ever will be from this codebase — that is
explicitly the responsibility of a licensed financial institution plugging
this library in downstream.

## License

Apache License 2.0.
