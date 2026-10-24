# kotoba-labor

[![CI](https://github.com/kotoba-lang/labor/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/labor/actions/workflows/ci.yml)

**Employment contracts, timesheets and payroll in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
[`cloud-itonami-9700`](https://github.com/gftdcojp/cloud-itonami-9700)
community domestic-employment open business: employment contracts (hourly
or monthly), timesheet entries, wage calculation, and payroll records with
deductions.

No network, no I/O. Amounts are plain numbers in the smallest currency unit
(e.g. cents) — no BigDecimal assumption, keeping the library portable
`.cljc` across JVM / ClojureScript / SCI / GraalVM.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 53 assertions on the JVM, 46 of them also on ClojureScript |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.labor :as labor])

(labor/contract "C1" "worker" "employer" "nanny" :hourly 1500)
(labor/total-hours [(labor/timesheet "worker" "2026-07-01" 8)])
(labor/wages-for contract timesheet-entries)
(labor/payroll "P1" "worker" "2026-07" 21000 :deductions 2000)
```

## Operator console (UI/UX)

A read-only HTML dashboard renders contracts, timesheets and payroll (gross/deductions/net) for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.labor.ui :as ui])

(ui/dashboard
  {:contracts [(labor/contract "C1" "worker" "employer" "nanny" :hourly 1500)]
   :timesheets [(labor/timesheet "worker" "2026-07-01" 8)]
   :payrolls [(labor/payroll "P1" "worker" "2026-07" 12000 :deductions 2000)]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (every control character
escaped per RFC 8259) for contracts, timesheets and payroll.

Amounts are written as bare JSON numbers, so the exporters refuse a value
that is not one instead of emitting it unquoted. Verified against Python's
`json` module: a rate of `15,"approved":true` did not produce a wrong rate,
it produced a *second key* on the object -- a value supplied in one field
became a field of its own. Escaping cannot close that, because the hole is
that the field is not quoted at all.

```clojure
(require '[kotoba.labor.export :as ex])

(ex/contracts->csv contracts)
(ex/payrolls->csv payrolls)   ; gross/deductions/net
(ex/payrolls->json payrolls)
```

## Test

Two hosts, because the library claims to work on more than one.

```sh
kbb -M:test                                    # JVM: every namespace
kbb --backend sci --classpath "src:test" test/run_portable.cljk  # ClojureScript
```

The `.cljc` sources are portable, but until the second runner existed only
the JVM ever executed an assertion, so the portability claim was unmeasured
rather than satisfied -- and an unmeasured claim looks exactly like a
satisfied one, because both produce no output. The first ClojureScript run
found the difference immediately: `(+ 8 nil)` throws `NullPointerException`
on the JVM and evaluates to `8` on ClojureScript, so a timesheet with one
entry missing its hours crashed one host and quietly under-reported the
other. The second number is not an error value -- it flows through
`wages-for` into a payroll `gross` and gets paid, indistinguishable from a
shorter shift. `total-hours` and `payroll` now refuse a non-numeric amount
identically on both hosts.

`test/run_portable.cljk` exits `0` when the portable namespaces ran and
passed, `1` when they ran and something failed, and `2` when it cannot
vouch for what it covered -- a test file under `test/` that no runner lists,
or a namespace that reported no tests. Without the third code, a run that
silently covered less than the tree contains prints `0 failures, 0 errors`
and exits `0`, which is what a fully passing run also prints.

`kotoba.labor.ui-test` is JVM-only: it renders through the kotoba-lang
`html` and `css` libraries, which `deps.edn` names by git coordinate. The
portable runner names that exclusion rather than skipping it silently.

## Why

A household-employer operator must never pay a worker without a valid
contract, and must never net a payroll that differs from gross minus
documented deductions. `kotoba-labor` is the pure-data layer a
`PolicyGovernor` checks against; the actor (`cloud-itonami-9700`) decides
permission, the audit ledger records proof.

## License

Apache License 2.0.
