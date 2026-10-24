# kotoba-logistics

[![CI](https://github.com/kotoba-lang/logistics/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/logistics/actions/workflows/ci.yml)

**Shipments, tracking numbers, routes and freight in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
[`cloud-itonami-4920`](https://github.com/gftdcojp/cloud-itonami-4920)
community freight-transport open business: shipment records with status,
tracking-number normalization and structural validation, multi-modal route
legs, and freight consignments.

No network, no I/O. Portable `.cljc` across JVM / ClojureScript / SCI /
GraalVM.


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 55 tests / 618 assertions on the JVM, 46 / 468 of them under nbb, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.logistics :as log])

(log/tracking-valid? "1Z 999 AA1 0123 4567")     ; => true
(log/shipment "SH1" "Tokyo" "Osaka" "Yamato" :tracking "1Z999AA101234" :weight 2.5)
(log/leg "A" "B" :road :distance-km 50)
(log/consignment "C1" sh [leg1 leg2] :declared-value 1000)
```

## Operator console (UI/UX)

A read-only HTML dashboard renders tracking validation, shipments (status badges) and consignments for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.logistics.ui :as ui])

(ui/dashboard
  {:trackings ["1Z999AA101234"]
   :shipments [(log/shipment "SH1" "Tokyo" "Osaka" "Yamato" :status :in-transit)]
   :consignments [(log/consignment "C1" sh [leg])]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC 4180 quoting: comma, quote, LF and a bare CR) and JSON
(RFC 8259 section 7: quote, backslash, and every control character
U+0000-U+001F) for tracking validation, shipments and consignments. Both are
tested by reading the output back with a reader written from the grammar, not
by matching substrings in it.

```clojure
(require '[kotoba.logistics.export :as ex])

(ex/trackings->csv trackings)
(ex/shipments->csv shipments)  ; status
(ex/trackings->json trackings)
```

## Test

```sh
kbb -M:test                              # everything, including the console
kbb --backend sci --classpath src:test run_tests.cljk      # the portable half, on a second runtime
```

The nbb run covers `kotoba.logistics` and `kotoba.logistics.export` -- the two
namespaces that claim to be portable and have no dependencies outside
`clojure.core`/`clojure.string`. It exists because a `.cljc` portability claim
that only ever runs on the JVM is a docstring: `json-hex4` avoids `Integer`
interop on purpose, and only a second runtime can tell whether it still does.

It reports three outcomes, not two: `0` with the marker `logistics: all green`,
`1` for a failure, and `2` for *refused* -- too few tests or assertions ran for
a pass to mean anything. Without that floor, a namespace dropped from the
runner's list prints the same `0 failures, 0 errors` as a full green run.

`kotoba.logistics.ui` is JVM-only here because it requires `html.core` and
`css.core`, which arrive as git dependencies.

## License

Apache License 2.0.
