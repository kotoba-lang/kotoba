# ekyc

[![CI](https://github.com/kotoba-lang/ekyc/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/ekyc/actions/workflows/ci.yml)

eKYC session and evidence substrate for kotoba-lang.

## First-party Kotoba Identity components (September 2026)

The new `ekyc.passport`, `ekyc.identity-policy`, `ekyc.identity-crypto` and
`ekyc.identity-authority` namespaces add cryptographic TD3 passport verification,
review/credential lifecycle, holder-bound signed presentations and commit-gated
free-quota effects. `native/ios` adds the NFC capture transport.

The v2 profile adds a [Web-first weighted trust route](docs/weighted-trust-routes.md):
signed Web review contributes 60 points and an independently reviewed app passport
route contributes 80, capped at 100. Review, scope and screening remain hard gates.

[Continuous session evidence](docs/continuous-session-evidence.md) adds signed
observer events, discounted Beta/Subjective Logic support, persistent alerts,
source-key revocation checks and a current-session gate before free reservations.
The model is explicitly uncalibrated; production observers remain unconnected.

These are tested components, **not a deployed identity provider**. Read
[the implemented profile and activation boundaries](docs/kotoba-identity-v1.md).
The original method catalog described below remains structural; its claims do
not establish assurance for the new host.

Provider APIs are host ports. This repo stores lifecycle and evidence references,
not document images or provider secrets.

## kotoba.ekyc — non-face-to-face identity-verification method catalog

**Real, spec-conformant electronic KYC (eKYC) verification-method catalog and
structural session validation, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library seeded for
[`cloud-itonami-isic-6493`](https://github.com/cloud-itonami/cloud-itonami-isic-6493)
(a factoring-business governed actor) and any other actor that needs to
reject an unrecognized or evidentially-incomplete identity-verification
method *before* accepting a client/debtor.

Models the ten non-face-to-face (非対面) identity-verification methods
enumerated in Japan's 犯罪による収益の移転防止に関する法律施行規則 (Act on
Prevention of Transfer of Criminal Proceeds, Enforcement Regulation) Article
6 Paragraph 1 — sub-items ホ/ヘ/ト(1)/ト(2)/ル/カ/ワ/ヨ for natural-person
customers and ロ/ホ for corporate customers, verified against the current
consolidated text (e-Gov 法令検索, law id `420M60000F5A001`) and cross-checked
against 金融庁 (FSA) and 警察庁 JAFIC reference material — each with its real
required-evidence combination, cross-referenced against NIST Special
Publication 800-63A-4 (*Digital Identity Guidelines: Identity Proofing and
Enrollment*, final, July 2025) Identity Assurance Levels (IAL1/IAL2/IAL3).
The IAL mapping is deliberately honest where it doesn't cleanly apply (see
`docs/adr/0001-architecture.md`) rather than forced onto a level.

No network, no I/O, **no biometric matching, no liveness detection, no
document OCR/authenticity forensics**. This library models the
STRUCTURAL/LEGAL shape of a verification record — which method was claimed,
whether its required evidence combination and printed/encoded fields are
present, whether required live-capture signals are set, whether the subject
claim carries its core attributes — not the biometric processing itself. A
real vendor integration (actual biometric face-matching, document forgery
detection, real NFC/IC-chip reads, real My Number Card cryptographic
verification) is explicitly out of scope; that requires a licensed operator
with real vendor contracts. Portable `.cljc` across JVM / ClojureScript /
SCI / GraalVM.

This is a different layer than the `ekyc.core`/`ekyc.model`/`ekyc.adapters.*`
namespaces elsewhere in this repo, which model a provider *session
lifecycle* (host ports, evidence custody, VC issuance) for wiring to a real
vendor. `kotoba.ekyc` models which method a specified business operator is
legally allowed to rely on and what a `PolicyGovernor` should check
structurally before that session's chosen method + evidence set is accepted
as legally valid — the two are meant to compose, not compete.

### Maturity

| | |
|---|---|
| Role | capability |
| Tests | 174 assertions in `kotoba.ekyc.*` (213 total in this repo), all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |
| Jurisdictions covered | JPN only — see Why (missing jurisdictions are uncovered, never fabricated) |
| Cross-repo linkage graph | yes — `kotoba.ekyc.jurisdiction-graph` (Datomic + DataScript, 188 real `cloud-itonami-iso3166-*` countries structurally present, JPN researched) |

### Contract

```clojure
(require '[kotoba.ekyc :as ekyc])

(ekyc/method :ho)                    ; => 犯収法施行規則6条1項1号ホ catalog entry
(ekyc/methods-for :individual)       ; => the 8 non-face-to-face individual methods
(ekyc/methods-for :corporate)        ; => the 2 corporate methods
(ekyc/legally-recognized-method? :made-up-method) ; => false

(def claim (ekyc/subject-claim "Yamada Taro" "1-1-1 Chiyoda, Tokyo" "1990-01-01"))

(def v (ekyc/verification "V-1" :he claim
         [(ekyc/evidence :ic-chip-read "chip-ref"
                          :fields-confirmed [:name :address :dob :photo])
          (ekyc/evidence :facial-image "face-ref" :captured-live? true)]))

(ekyc/validate v)
;; => {:ekyc.result/disposition :pass :ekyc.result/assurance-level :ial2 ...}

(ekyc/validate (ekyc/verification "V-2" :fabricated-method claim []))
;; => {:ekyc.result/disposition :fail :ekyc.result/reasons [:unrecognized-method]}
```

### Operator console (UI/UX)

A read-only HTML dashboard renders verification records, the method they
claim, and the recognized method catalog for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`,
no evidence images) — writes stay behind the governor.

```clojure
(require '[kotoba.ekyc.ui :as ui])

(ui/dashboard {:verifications [v]})
;; => "<html>...read-only · governor-gated...</html>"
```

### Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for compliance export, never including evidence payloads
themselves (those stay opaque refs held by a real vendor/custody adapter).

```clojure
(require '[kotoba.ekyc.export :as ex])

(ex/verifications->csv verifications)   ; id, method, citation, disposition, assurance_level, reasons
(ex/methods->csv ekyc/method-catalog)   ; the recognized-method reference table
(ex/verifications->json verifications)
```

### `kotoba.ekyc.jurisdiction-graph` — cross-repo regulatory-linkage graph

A real, queryable graph linking `kotoba.ekyc`'s method catalog to the
`cloud-itonami-iso3166-*` family (per-country "Market-Entry Compliance"
actor repos in the `cloud-itonami` GitHub org), loadable into both
**Datomic** (JVM, server-side queryable) and **DataScript** (in-browser
queryable) — not more static markdown citations.

```clojure
(require '[kotoba.ekyc.jurisdiction-graph :as jg])

(count jg/countries)          ; => 188 -- real per-country repos, verified
                               ;    (not 223; see docs/adr/0002 for why)
jg/schema-datomic             ; full Datomic schema vocabulary
jg/schema-datascript          ; the empirically-verified DataScript subset
                               ; (derive-datascript-schema jg/schema-datomic)

(jg/coverage-report)
;; => {:total-countries 188 :researched 1 :researched-jurisdictions ["JPN"]
;;     :not-yet-researched 187 :note "... never fabricate ..."}
```

**Honest coverage: 1 of 188, not "223-country KYC regulatory database."**
Every one of the 188 real `cloud-itonami-iso3166-*` country repos gets a
structurally complete `:country/*` entity (queryable across the whole
family), but `:country/recognizes-method` edges — each carrying its own
jurisdiction-specific legal-basis citation via a reified `:recognition/*`
edge entity, since the citation is jurisdiction-specific even when a
method concept is shared — exist ONLY for JPN, derived from
`kotoba.ekyc/method-catalog`'s real 犯収法施行規則 citations. The other 187
countries carry `:country/coverage-status :not-yet-researched` — absence
of an edge means "not yet researched," never "no requirements," matching
this repo's own "missing jurisdictions are uncovered, never fabricated"
rule and the rest of the `cloud-itonami-*` fleet's citation-honesty
convention (e.g. `vcfund.facts/coverage`).

DataScript compatibility is proven, not claimed:
`test/kotoba/ekyc/jurisdiction_graph_test.cljk` transacts
`schema-datascript` + real tx-data into an actual `datascript.core` conn
(`datascript/datascript` on the JVM — the real portable `.cljc` DataScript
library, same code that compiles to run in a browser) and runs the
example Datalog queries in `jg/queries` against it. See
[`docs/adr/0002-iso3166-jurisdiction-graph.md`](docs/adr/0002-iso3166-jurisdiction-graph.md)
for the empirical schema-compatibility probe, the 223→188 verification
method, and the design rationale.

### Why

A specified business operator (特定事業者) under 犯収法 must never accept a
client using an identity-verification method that isn't one of the
regulation's own enumerated combinations, and must know honestly how that
method compares to the assurance-level vocabulary the rest of this fleet's
facts catalogs use (NIST SP 800-63A-4). `kotoba.ekyc` is the pure-data layer
a `PolicyGovernor` checks against; the actor (`cloud-itonami-isic-6493`)
decides permission, a real vendor integration performs the actual biometric/
document verification, and the audit ledger records proof. This library
deliberately does not attempt biometric matching, liveness detection, or
document forensics — those require a real licensed vendor and real
biometric processing that is out of scope for this codebase to fabricate.

## License

MIT — see [LICENSE](LICENSE).

## Test

```bash
kbb -M:test
```

Browser intake, signed review and per-case encrypted vault components are described
in [the intake and vault contract](docs/browser-intake-and-vault.md). Production
private storage/KMS and reviewer enrollment remain unconnected; intake is closed.
