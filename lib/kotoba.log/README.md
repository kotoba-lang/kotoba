# kotoba-lang/log

[![CI](https://github.com/kotoba-lang/log/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/log/actions/workflows/ci.yml)

**Structured logging + telemetry** (trace/span) as **pure data**, with a
**host-injected sink**. A capability-confined kotoba cell does not get stdout —
the host grants a log sink. Consumes
[`kotoba-lang/coll`](https://github.com/kotoba-lang/coll) for field shaping. No
third-party deps; `.cljc` (JVM / SCI / CLJS / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

`aiueos` has an append-only audit trail, but the general-purpose observability
layer — structured log records, trace spans, span context propagation — was
missing. `log` is that layer, split the stdlib way: the **records** are pure
data (`{:level :message :fields :ts :span}`), the **transport** is a
host-injected `sink` fn (`(sink record)`). A cell with no sink logs to nothing —
deny-by-default.

## Current surface

`kotoba.lang.log`:

- `make-logger` — make a logger from a host-injected `sink` fn + opts (default
  level, context fields)
- `log` — emit a record at a level (`:trace :debug :info :warn :error :fatal`)
- `with-context` / `with-span` — thread context/span through logs
- `trace`/`debug`/`info`/`warn`/`error` — level convenience fns
- `start-span` / `end-span` — span lifecycle (returns span record with duration
  when given an elapsed-ms)
- `level-enabled?` — predicate (a logger filters by its min level)

A record is `{:level :message :fields :ts :span-id :parent-id}`.

## Install

```clojure
io.github.kotoba-lang/log {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.log :as log])

(let [sink (fn [rec] (println rec))           ; host-injected
      lg   (log/make-logger sink {:level :info :context {:service "cell"})]
  (log/info lg "started" {:pid 42})
  (let [[lg' span] (log/start-span lg "work")]
    (log/info lg' "doing work")
    (log/end-span lg' span 15)))               ; 15ms elapsed
```

## Verify

```sh
kbb -M:test
```
