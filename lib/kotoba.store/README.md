# kotoba-lang/store

[![CI](https://github.com/kotoba-lang/store/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/store/actions/workflows/ci.yml)

A **capability-guarded key-value store** over an injected filesystem — a real
consumer of the kotoba-lang foundational stdlib:
[`fs`](https://github.com/kotoba-lang/fs) (IFilesystem backend),
[`io`](https://github.com/kotoba-lang/io) (byte streaming),
[`wit`](https://github.com/kotoba-lang/wit) (deny-by-default capability
gating), and [`coll`](https://github.com/kotoba-lang/coll) (key/path shaping).
M5 for all four. No third-party deps; every namespace is `.cljc` (JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

A capability-confined kotoba cell must not touch storage it wasn't granted.
`store` composes the stdlib into the natural storage layer: `fs` provides the
backend (the host injects a real or in-memory `IFilesystem`), `io` streams the
bytes, and `wit` gates every read/write behind a deny-by-default capability
token (`store:read` / `store:write`). Without a granted capability, an op is
denied — by construction, not convention.

## Current surface

`kotoba.lang.store`:

- `store` — make a store from an `IFilesystem` (fs) and a `wit` policy
- `put` / `get` / `delete` / `exists?` — capability-gated ops; `put`/`get`
  stream bytes through `io` (byte-buffer + copy)
- `with-policy` — return a store with a different granted-capability set
- `::denied` — returned when a capability is missing (deny-by-default)

Keys map to filesystem paths under a `:prefix` (default `store/`).

## Install

```clojure
io.github.kotoba-lang/store {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.store :as store]
         '[kotoba.lang.fs :as fs]
         '[kotoba.lang.wit :as wit])

(let [fsb (fs/mem-filesystem)
      pol (wit/grant (wit/policy) "store:read")     ; read-only
      s   (store/store fsb pol)]
  (store/put s "a" (byte-array [1 2 3]))            ;=> ::store/denied (no write cap)
  (let [s2 (store/with-policy s (-> (wit/policy) (wit/grant "store:read") (wit/grant "store:write")))]
    (store/put s2 "a" (byte-array [1 2 3]))
    (vec (store/get s2 "a"))))                       ;=> [1 2 3]
```

## Verify

```sh
kbb -M:test
```
