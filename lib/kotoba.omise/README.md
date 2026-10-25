# kotoba-omise

[![CI](https://github.com/kotoba-lang/omise/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/omise/actions/workflows/ci.yml)

**Stores (お店), opening hours and pickup points in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
[`cloud-itonami-isic-5320`](https://github.com/cloud-itonami/cloud-itonami-isic-5320)
community last-mile courier open business: store records with status,
weekly opening-hours windows and pure `open-at?` checks, pickup points,
and haversine geo distance.

No network, no I/O, **no clock access** — the caller always passes the
day/time to check, so every function is a pure, deterministic contract.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

See ADR-2607121900 (com-junkawasaki/root) for the design decision this
library is part of (Shippify-class last-mile delivery, replaced by an
open, governed courier actor).

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 52 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.omise :as omise])

(def s (omise/store "st-1" "Kanda Books" "1-1 Kanda, Tokyo"
                    :hours {:mon [["09:00" "18:00"]]}
                    :jurisdiction "JPN" :pickup-ready? true))

(omise/open-at? s :mon "10:00")            ; => true  (close is exclusive)
(omise/pickup-available? s :mon "10:00")   ; => true  (:active + pickup-ready + open)
(omise/pickup-point "pp-1" "st-1" "front counter" :geo {:lat 35.69 :lng 139.77})
(omise/distance-km {:lat 35.6762 :lng 139.6503} {:lat 34.6937 :lng 135.5023}) ; ~400km
```

`pickup-available?` is the single question the
`cloud-itonami-isic-5320` Courier Governor asks before a delivery
dispatch may proceed: the origin store must be `:active`, flagged
`:pickup-ready?`, and open at the caller-supplied moment.

## Operator console (UI/UX)

A read-only HTML dashboard renders stores (open/closed badges for a
caller-supplied moment) and pickup points for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.omise.ui :as ui])

(ui/dashboard {:stores [s]
               :pickup-points [(omise/pickup-point "pp-1" "st-1" "front counter")]
               :at [:mon "10:00"]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for stores, pickup points and per-moment open reports.

```clojure
(require '[kotoba.omise.export :as ex])

(ex/stores->csv stores)
(ex/pickup-points->csv points)
(ex/open-report->csv stores [:mon "10:00"])
(ex/stores->json stores)
```

## Test

```sh
kbb -M:test
```

## License

Apache License 2.0.
