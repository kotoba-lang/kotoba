# kotoba-card

[![CI](https://github.com/kotoba-lang/card/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/card/actions/workflows/ci.yml)

**Payment cards, ISO 8583 messages and authorization in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library that gives
the [`cloud-itonami-6619`](https://github.com/gftdcojp/cloud-itonami-6619)
card-transaction-processing open business the records a card-processing
operator keeps: PAN (ISO/IEC 7812) account numbers with Luhn (ISO/IEC
7812-1) checksum and network classification, ISO 8583 message headers and
data elements, and an authorization/decision contract.

The library models **records, not the wire format**. ISO 8583 on the wire
uses a 4-byte message indicator, a 16-bit primary bitmap and BCD-packed
fields; here messages are EDN so a `PolicyGovernor` or test harness can
reason structurally without a codec. No network, no I/O. Amounts are plain
numbers in the smallest unit of the transaction currency (e.g. cents) — no
BigDecimal assumption, keeping the library portable `.cljc` across JVM /
ClojureScript / SCI / GraalVM.

> PANs are kept whole only for the structural model. A separate
> tokenization layer must replace them in any real system; this library
> never persists raw PANs.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | all green, measured 2026-09-09: 51 tests / 721 assertions (`kbb -M:test`), of which 41 / 233 are the `.cljc` suites alone (`kbb -M:test-pure`) |
| Records (PAN / ISO 8583 / authorization) | yes |
| Issuer-side lifecycle state machine | yes (`kotoba.card.lifecycle`) — mirrors the issuer governor's own allowlist |
| Issuer-side host ports (propose-only) | yes (`kotoba.card.ports`) |
| Post-approval actuation contract | yes (`kotoba.card.actuation`) |
| Acquirer-side ports | no — deliberately, see below |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.card :as card])

(card/pan-valid? "4111111111111111")          ; => true (Visa test PAN)
(card/parse-pan "4111111111111111")           ; => {:card/iin "411111" :card/network :visa ...}
(card/message "0100" {2 "4111111111111111" 4 "300620261000"})
(card/authorization "4111111111111111" 1999 :approve)
(card/authorization "4111111111111111" 1999 :partial-approve :approved 1000)
(card/validate-pan "4111111111111112")        ; => {:card/valid? false :card/error :bad-checksum}
```

## Card lifecycle (`kotoba.card.lifecycle`)

A **pure state machine** so that *is this lifecycle transition even reachable
from the state we have on record?* is answered by a total, deterministic
function — no I/O, no model, no policy. It is the intended callee of a consent
surface's pre-check, which must reject an unreachable transition *before* any
human approval is requested. Same posture as
[`kotoba.esim.lifecycle`](https://github.com/kotoba-lang/esim).

```
:intake  (pre-issuance; no lifecycle event leaves it — :card/issue does)

:issued --activate--> :active --block--> :blocked
   |                     |                   |
   |                     |    reissue (mints a NEW card reference)
   |                     |                   |
   |                     |     +-------------+
   |                     |     v
   |                     |  :active
   +--------close--------+--------close------+---> :closed  (terminal)
```

> **This table is not this library's invention — it mirrors the deployed issuer
> side.** `cardissuing.governor/legal-predecessor` decides which state each event
> is legal from, and `cardissuing.store/lifecycle!` decides which state it lands
> in. The reason to extract them here is *not* that the issuer side lacked them
> (it has enforced this allowlist all along) but that a consent surface must ask
> the same question **before** requesting human approval, and a second copy of
> these rules would drift. One table, two readers — so when the governor's table
> changes, this one must follow, and `lifecycle_test.cljc` transcribes the
> issuer's two tables verbatim so a divergence fails the suite.

```clojure
(require '[kotoba.card.lifecycle :as lc])

(lc/reachable? :blocked :activate)   ; => false — unblocking is NOT an activate
(lc/reachable? :blocked :reissue)    ; => true  — reissue is the recovery path
(lc/describe :blocked :reissue)
;=> "reissue: blocked -> active (new card reference)"
```

Two rules are easy to guess wrong, so they are worth stating:

- **`:activate` is legal only from `:issued`.** A blocked card does not simply
  resume; the issuer side's recovery path from `:blocked` is `:reissue`.
- **`:reissue` is legal only from `:blocked`, lands in `:active`, and mints a new
  card reference** — `cardissuing.store/lifecycle!` calls
  `register-card-issuance` with the next sequence for the BIN. The successor is
  created by the same operation, so `apply-event` reports
  `:card/mints-successor? true` rather than pretending the caller must issue the
  replacement separately.

`apply-event` is total, returns data, never throws, and every refusal carries a
reason a governor can cite.

## Issuer-side ports (`kotoba.card.ports`)

Protocols a host implements; the host — a governed actor such as
[`cloud-itonami-card-issuing`](https://github.com/cloud-itonami/cloud-itonami-card-issuing)
— injects the real scheme/processor connection, or fixtures offline. Modeled on
[`kotoba-lang/koe`](https://github.com/kotoba-lang/koe)'s voice ports.

| Protocol | Operation vocabulary |
|---|---|
| `ICardholderProvisioning` | `:cardholder/intake` |
| `ICardProgram` | `:bin/assess`, `:bin/sponsor` |
| `ICardIssuance` | `:card/issue`, `:card/lifecycle` |
| `IAuthorizationDecision` | `:authorization/decide` |
| `IDisputeInitiation` | `:dispute/initiate` |

> **Every operation is propose-only.** An implementation returns a proposal
> record for a governor and a human to decide on; it does not sponsor a real
> BIN, issue a real card, move real funds or file a real chargeback. That is the
> containment the issuer-side actor is built around, made structural here so a
> caller cannot mistake a port for an actuator.

The split is load-bearing, not decorative — the contract test asserts a host can
implement `IAuthorizationDecision` **without** thereby gaining the ability to
propose issuing a card or sponsoring a BIN. Authorization is the only hot path
(per transaction, latency-bound, available independently of issuance), and BIN
sponsorship is a once-per-program licensing act.

**Acquirer-side ports are deliberately absent.** Chargeback hold release and
settlement finalization belong to
[`cloud-itonami-isic-6619`](https://github.com/cloud-itonami/cloud-itonami-isic-6619).
One actor holding both sides of a dispute is the conflict of interest the split
exists to prevent. No SDK, endpoint, scheme membership, HSM handle or credential
lives in this library.

## After a decision: `kotoba.card.actuation`

`kotoba.card.ports` is **propose-only** and says so — a host that actuates inside
one of those methods has moved a licensed act behind an interface that reads as a
query. That leaves a hole: once a governor has cleared a proposal and a licensed
operator has approved it, something has to actually issue the card.

`kotoba.card.actuation` is that something, and it is a **separate protocol** so the
difference is visible at the call site rather than only in a docstring:
`ports/issue-card` drafts, `actuation/issue-card!` does. A test asserts a
propose-only host does not satisfy `ICardActuation` and vice versa.

Three properties a caller may rely on:

- **Nothing runs without an approval.** Every function takes an approval carrying
  `{:by … :reference …}` — **both**, because a reference with no approver cannot be
  audited and an approver with no reference cannot be tied to what they saw.
- **Every call is idempotent on a caller-supplied key.** `:idempotency-key` is
  required and is *not* generated for the caller: only the caller knows whether
  this is a retry. A retried `issue-card!` must not produce a second live card.
- **Refusals are data**, not exceptions — a thrown exception loses the provider's
  reason somewhere up the stack.

`precheck` is the guard an implementation runs **before any outbound call**. A
provider that reaches the network and then discovers the approval was unnamed has
already acted.

### Providers must publish their state mapping

`state-mapping-complete?` requires a provider to give **every** lifecycle state a
provider-side representation, mapping to `nil` the ones it cannot express.
Folding is forbidden because that is how `:issued` and `:active` become the same
thing and a card that was never activated starts working.

This is not hypothetical: Stripe Issuing has three card statuses (`active`,
`inactive`, `canceled`) where this lifecycle has five. A provider must say so —
see [`kotoba-lang/io-stripe-issuing`](https://github.com/kotoba-lang/io-stripe-issuing).

## Operator console (UI/UX)

A read-only HTML dashboard renders PAN validation (masked), ISO 8583 messages and authorization decisions for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.card.ui :as ui])

(ui/dashboard
  {:pans ["4111111111111111"]
   :messages [(card/message "0100" {2 "4111111111111111"})]
   :authorizations [(card/authorization "4111111111111111" 1999 :approve)]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for PAN validation (masked), messages and authorizations.

```clojure
(require '[kotoba.card.export :as ex])

(ex/pans->csv pans)                ; PANs masked to last 4
(ex/authorizations->csv auths)    ; action/approved/reason
(ex/pans->json pans)
```

## Why

A card-processing operator must never settle a transaction whose PAN fails
the Luhn checksum or whose authorization was declined, and must never
over-charge a partially-approved amount. `kotoba-card` is the pure-data layer
a `PolicyGovernor` checks against; the actor (`cloud-itonami-6619`) decides
permission, the audit ledger records proof.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test        # everything, including the .kotoba parity suite
kbb -M:test-pure   # the .cljc suites alone, with no compiler dependency
```

### Why `kotoba.card.actuation` is still `.cljc`

`kotoba.card.lifecycle` has moved to `.kotoba` (with a `.cljk` twin, compared by
artifact). `kotoba.card.actuation` has not, and the reason is asserted rather than
written down:

```bash
kbb --backend sci test/kotoba/card/actuation_kotoba_blocked_probe.cljk
#   exit 0  still blocked
#   exit 1  open-world protocol dispatch is admitted -- migrate
#   exit 2  REFUSED: the control failed, or the refusal was for a different reason
```

Protocols are not missing from the language -- the probe compiles and RUNS a
closed-world one. What is refused is the port shape, a method called on a value
whose record is not statically known, which is what `ICardActuation` and
`ICardholderActuation` are: their implementers live in other repositories on
purpose. The probe goes red the day that changes.
