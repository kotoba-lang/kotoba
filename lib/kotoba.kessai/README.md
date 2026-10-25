# kotoba-kessai

[![CI](https://github.com/kotoba-lang/kessai/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kessai/actions/workflows/ci.yml)

**決済 (settlement/payment) — a rail-agnostic payment-gateway abstraction in
pure Clojure.** A [kotoba-lang](https://github.com/kotoba-lang) capability
library that gives any ISIC-vertical actor (credit, securities, insurance,
...) a single `authorize`/`capture`/`refund`/`void` port instead of a bespoke
payment integration per actor, built on the international standards three
sibling libraries already model: [`kotoba-lang/card`](https://github.com/kotoba-lang/card)
(ISO 8583 card messages, ISO/IEC 7812 PAN), [`kotoba-lang/banking`](https://github.com/kotoba-lang/banking)
(ISO 13616 IBAN, double-entry ledger), and [`kotoba-lang/swift`](https://github.com/kotoba-lang/swift)
(BIC/ISO 9362, SWIFT MT, ISO 20022 envelope). `kessai` adds the ISO 20022
`pain.001` (CustomerCreditTransferInitiation) credit-transfer record and its
XML rendering for the wire/SWIFT rail — it does not reimplement BIC
validation, which already exists in `kotoba-swift`.

The library models **records, not the wire transport**. Real ISO 8583 uses a
4-byte message indicator and BCD-packed fields — the card rail is EDN so a
governor or test harness can reason structurally without a codec. The wire
rail's `pain.001` XML is genuinely emitted (via `kotoba-swift`'s
`kotoba.swift.iso20022`, itself built on `kotoba-lang/xml`'s Hiccup->XML
emitter) rather than a hand-rolled string renderer — see ADR-2607142340. No
network, no I/O either way.

## Maturity

| | |
|---|---|
| Role | capability |
| Payment port | rail-agnostic `authorize`/`capture`/`refund`/`void` protocol + mock adapter |
| Card rail | ISO 8583 (MTI/data-element) bridge, via `kotoba-card` |
| Wire rail | ISO 20022 `pain.001` credit-transfer, via `kotoba-banking` (IBAN) + `kotoba-swift` (BIC) |
| Ledger tie-in | double-entry settlement postings, via `kotoba-banking` |
| Tests | card + wire + core, all green |

## Contract

```clojure
(require '[kotoba.kessai :as kessai]
         '[kotoba.kessai.card :as kcard]
         '[kotoba.kessai.wire :as wire])

;; Card rail (ISO 8583 / ISO 7812 PAN via kotoba-card)
(def card-req (kcard/card-request "4111111111111111" 1999 "USD"))
(def port (kessai/mock-payment-port))
(def auth (kessai/authorize port card-req))         ; => {:kessai/status :authorized ...}
(def captured (kessai/capture port auth))           ; => {:kessai/status :captured ...}

;; Wire rail (ISO 20022 pain.001 + BIC via kotoba-banking IBAN)
(def ct (wire/credit-transfer
          {:msg-id "MSG1" :end-to-end-id "E2E1"
           :debtor-iban "GB82WEST12345698765432" :debtor-bic "NWBKGB2L"
           :debtor-name "Acme UK Ltd"
           :creditor-iban "DE89370400440532013000" :creditor-bic "DEUTDEFF"
           :creditor-name "Acme GmbH" :amount 100.5 :currency "EUR"
           :creation-date-time "2026-07-15T09:00:00Z"
           :payment-info-id "PMTINF1"
           :requested-execution-date "2026-07-15"}))
(wire/->pain001-xml ct)                             ; => "<?xml ...><Document ...>" (real emitted XML)
(kessai/authorize port (wire/wire-request ct))      ; => {:kessai/rail :wire :kessai/status :authorized ...}

;; Ledger tie-in (double-entry via kotoba-banking)
(kessai/settlement-posting "posting-1" captured "clearing-account" "merchant-account")
```

## Why

An ISIC-vertical actor (credit, securities brokerage, insurance, ...) needs to
authorize, capture, refund or void a payment and post it to a ledger — today
each actor either reimplements this or reaches for a different ad hoc rail
(a raw Stripe REST call, a bespoke crypto rail). `kotoba-kessai` is the
pure-data layer that lets any actor's `PolicyGovernor` reason about payment
state structurally, on top of the ISO 8583/ISO 20022/IBAN/BIC international
standards `kotoba-card`, `kotoba-banking` and `kotoba-swift` already model —
without reinventing card or wire message shapes.

## Follow-ups

- **Real network adapters** (Stripe/card-network REST, SWIFT/bank gateway
  connectivity) are not implemented — only the mock adapter is. A real
  adapter implements `kotoba.kessai/IPaymentPort` and sends the ISO
  8583/ISO 20022 data this library builds.
- **pacs.008** (FIToFICustomerCreditTransfer, the interbank leg) and
  **camt.053** (account statement) are not modeled — `kessai` currently
  covers the customer-initiated `pain.001` leg only.
- **Operator console (UI/UX)** and **CSV/JSON export** (as `kotoba-card`/
  `kotoba-banking` have) are not built here yet.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
