# kotoba-rcs

[![CI](https://github.com/kotoba-lang/rcs/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/rcs/actions/workflows/ci.yml)

**GSMA RCS Universal Profile (RCC.07) message, session and capability
records in pure Clojure.** A [kotoba-lang](https://github.com/kotoba-lang)
capability library modeling the application-layer records an RCS
client/server exchanges: 1-to-1 chat messages, group chat, is-composing
presence (RFC 3994-shaped), delivery/read receipts (IMDN, RFC 5438-shaped),
file transfer descriptors and capability-discovery results (the outcome of
a SIP OPTIONS exchange, not the exchange itself).

No network, no I/O. Endpoints are E.164 numbers, validated by delegating
to [`kotoba-lang/phone`](https://github.com/kotoba-lang/phone)'s
`e164-valid?` rather than re-implementing E.164 parsing. Scope, stated
plainly: this models *records*, not wire format — actual SIP/MSRP/CPIM
transport framing, GSMA IR.92/IR.94 network registration and TLS/IPsec
transport security are explicitly out of scope and not implemented here.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 71 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.rcs :as rcs])

(rcs/chat-message "M1" "+8190A" "+8190B" "hi")
(rcs/group-chat "G1" ["+8190A" "+8190B"] "Trip planning")
(rcs/group-message "G1" "M2" "+8190A" "hi all")
(rcs/is-composing "+8190A" "T1" :active)               ; nil on unrecognized state
(rcs/receipt "M1" :delivered)                          ; nil on unrecognized disposition
(rcs/file-transfer "F1" "+8190A" "+8190B" "photo.jpg" 204800 "image/jpeg")
(rcs/capabilities "+442079460958" #{:chat :group-chat}) ; nil on malformed E.164
(rcs/valid-chat-message? m)
(rcs/valid-receipt? r)
(rcs/valid-capabilities? c)
```

## Operator console (UI/UX)

A read-only HTML dashboard renders capability-checked E.164 endpoints,
recent chat messages and receipts for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.rcs.ui :as ui])

(ui/dashboard
  {:capabilities [(rcs/capabilities "+442079460958" #{:chat :group-chat})]
   :messages [(rcs/chat-message "M1" "+8190A" "+8190B" "hi")]
   :receipts [(rcs/receipt "M1" :delivered)]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting, including bare-CR row terminators) and
JSON (RFC 8259 full control-character escaping) for chat messages, receipts
and capability-discovery records.

```clojure
(require '[kotoba.rcs.export :as ex])

(ex/messages->csv messages)
(ex/receipts->csv receipts)
(ex/capabilities->csv caps)   ; valid/features
(ex/messages->json messages)
```

## Why

`kotoba-rcs` complements [`kotoba-lang/phone`](https://github.com/kotoba-lang/phone)
(E.164 numbering, SIP URIs, CDRs and SMS) with the RCS Universal Profile
message types — chat, group chat, presence, receipts, file transfer and
capability discovery — as pure data. It is one layer of a larger,
independent telecom-substrate design: capability libraries that stay
wire-compatible with real carrier SMS/RCS message formats and record
shapes without depending on carrier network infrastructure themselves. A
`PolicyGovernor` checks a proposed message or capability record against
this library's validators before an actor commits and sends it; this
library only defines the records and the validation contract, not the
transport or the policy decision.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
