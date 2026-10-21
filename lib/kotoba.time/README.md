# kotoba-lang/time

[![CI](https://github.com/kotoba-lang/time/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/time/actions/workflows/ci.yml)

**Layer 3 (I/O) of the kotoba foundational stdlib** — `Instant` / `Duration` as
pure data, with wall-clock coming from a **host-injected `clock` capability**.
No `System/currentTimeMillis` in the library, so it runs on kotoba-WASM where
wall-clock is not available. Zero third-party runtime deps; every namespace is
`.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why host-injected clock

The kotoba-WASM premise excludes wall-clock — a capability-confined cell must
not read the clock unless the host granted it. So `now` takes an injected
`clock` fn (`(clock)` → epoch-millis). Without a clock, there is no time:
deny-by-default, the same property the rest of the stdlib upholds.

## Current surface

`kotoba.lang.time`:

- `instant`, `duration` — constructors from epoch-millis
- `millis`, `seconds`, `minutes`, `hours`, `days` — duration helpers
- `now` — `(now clock)` → instant from an injected clock fn (deny-by-default)
- `add`, `sub`, `before?`, `after?`, `between` — instant/duration arithmetic
- `->iso8601` / `iso8601->instant` — UTC `YYYY-MM-DDTHH:MM:SSZ` (no tz, portable)

## Install

```clojure
io.github.kotoba-lang/time {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.time :as t])

(t/->iso8601 (t/instant 0))                ;=> "1970-01-01T00:00:00Z"
(t/iso8601->instant "2026-06-30T12:00:00Z") ;=> <instant>
(t/now (fn [] 1750000000000))               ;=> <instant> from injected clock
(t/before? (t/instant 1000) (t/instant 2000)) ;=> true
```

## Verify

```sh
kbb -M:test
```
