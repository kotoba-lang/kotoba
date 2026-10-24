# kotoba-phone

[![CI](https://github.com/kotoba-lang/phone/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/phone/actions/workflows/ci.yml)

**Telephony numbering, SIP URIs, call records and SMS in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library that gives
the [`cloud-itonami-6190`](https://github.com/gftdcojp/cloud-itonami-6190)
community telecommunications-access open business the records a telecom
operator keeps: E.164 (ITU-T) international subscriber numbers with
country-code splitting, SIP (RFC 3261) URI parsing, call detail records
(CDR) and SMS message records.

No network, no I/O. The library expects international-form input (a leading
`+` or an international access prefix `00` / `011`); national trunk-prefix
translation is the operator's numbering-plan concern, not the contract layer.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 40 tests / 177 assertions, all green |
| Numbering, porting, origination | yes (lifecycle · numbering · porting · origination · ports) |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.phone :as phone])

(phone/normalize-e164 "+44 20 7946 0958")      ; => "+442079460958"
(phone/parse-e164 "+819012345678")             ; => {:phone/country-code "81" ...}
(phone/parse-sip-uri "sip:alice@example.com;transport=tcp?subject=hi")
(phone/cdr "C1" "+8190A" "+8190B" :outbound 120)
(phone/sms "S1" "+8190A" "+8190B" "hi")
(phone/validate-e164 "x")                      ; => {:phone/valid? false ...}
```

## Numbering, portability and outbound calling

The records above say what a number *is*. These four namespaces say what may
be *done* with one, as total deterministic functions with no I/O — the layer a
consent surface's pre-check calls before any human is asked
(ADR-2607300300 / ADR-2608034000). Same shape as `kotoba.esim.lifecycle` and
`kotoba.card.lifecycle`, on purpose.

```clojure
(require '[kotoba.phone.lifecycle   :as lifecycle]   ; MSISDN state machine
         '[kotoba.phone.numbering   :as numbering]   ; blocks, allocation (払い出し)
         '[kotoba.phone.porting     :as porting]     ; MNP port-in / port-out
         '[kotoba.phone.origination :as origination] ; placing a call (発信)
         '[kotoba.phone.ports       :as ports])      ; host-injected protocols

;; Recycling cannot be routed around: :assign is unreachable from :released,
;; and :recycle refuses unless the aged-out window is stated as a fact.
(lifecycle/reachable? :released :assign)                       ; => false
(lifecycle/apply-event records "+819012340001" :recycle)
;; => {:phone/ok? false :phone/issues [{:phone/issue :recycle/quarantine-incomplete}]}

;; Allocation is two recorded decisions, not one.
(numbering/plan-allocation {:blocks blocks :records records :now-ms now
                            :msisdn "+819012340020" :subject "did:key:z6…"})
;; => {:phone/ok? true :phone/plan [[:reserve {}] [:assign {:phone/subject "did:key:z6…"}]]}

;; A port-out naming someone other than the holder is the port-out scam.
(porting/port-out-issues {:records records :request request :now-ms now})
;; => [{:phone/issue :porting/subject-mismatch …}]

;; An emergency number is never the destination of a governed proposal, and the
;; calling number must be one the subject holds AND has active.
(origination/origination-issues {:destination "110" …})
;; => [{:phone/issue :origination/emergency-destination …}]
```

`kotoba.phone.lifecycle/takeover-signals` is the vocabulary a cross-domain
posture reads: whoever takes over a number has taken over the second factor for
everything else, so a port-out lowers the same subject's card posture. The rule
lives here so every consumer reads one definition of “the line changed hands”.

## Operator console (UI/UX)

A read-only HTML dashboard renders E.164 validation, recent calls (CDR) and SMS for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.phone.ui :as ui])

(ui/dashboard
  {:numbers ["+442079460958" "bad"]
   :cdrs [(phone/cdr "C1" "+8190A" "+8190B" :outbound 120)]
   :sms [(phone/sms "S1" "+8190A" "+8190B" "hi")]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for E.164 validation, CDRs and SMS.

```clojure
(require '[kotoba.phone.export :as ex])

(ex/numbers->csv numbers)  ; valid/normalized
(ex/cdrs->csv cdrs)
(ex/numbers->json numbers)
```

## Why

A community telecom operator must prove, before a call or message is
committed and billed, that the calling and called numbers are valid E.164
addresses and that the SIP endpoint is well-formed. `kotoba-phone` is the
pure-data layer a `PolicyGovernor` checks against; the actor
(`cloud-itonami-6190`) decides permission, the audit ledger records proof.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
