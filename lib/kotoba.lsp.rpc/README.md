# kotoba-lang/lsp-rpc

[![CI](https://github.com/kotoba-lang/lsp-rpc/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/lsp-rpc/actions/workflows/ci.yml)

**JSON-RPC framing over a host-injected transport** — closes the `:lsp-wire`
gap tracked in the foundational-stdlib ADR. The
[`lsp`](https://github.com/kotoba-lang/lsp) lib owns the data contract
(positions, ranges, diagnostics); `lsp-rpc` owns the JSON-RPC message framing
(`Content-Length` framing, request/response/notification, error codes); the
**transport** (send/recv bytes) stays **host-injected** — a capability-confined
kotoba cell can't open a socket, so the host grants a transport fn. Consumes
[`json`](https://github.com/kotoba-lang/json) for wire encode/decode. No
third-party deps; `.cljc` (JVM / SCI / CLJS / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why

The ADR's `:engineering-gaps` listed `:lsp-wire {:status :gap}` — `lsp` had the
data layer but no wire. `lsp-rpc` is the wire: JSON-RPC 2.0 framing (the same
shape `rust-analyzer`/`tsserver` speak over stdio), with diagnostics carried as
`lsp` records. A host wires its transport (stdio, a socket, a worker
postMessage) and `lsp-rpc` does the rest.

## Current surface

`kotoba.lang.lsp-rpc`:

- `make-server` — make a JSON-RPC server from a `handler` (fn of method+params
  → result) and a host-injected `send` fn (fn of string)
- `handle-message` — parse one framed message, dispatch, return the response
  string (or nil for notifications)
- `frame` / `unframe` — `Content-Length:` framing (the LSP wire envelope)
- `request` / `response` / `notification` — message constructors
- `error` codes (`-32700` parse error, `-32601` method not found, …)

## Install

```clojure
io.github.kotoba-lang/lsp-rpc {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.lsp-rpc :as rpc])
(let [sent (atom nil)
      srv (rpc/make-server (fn [method params]
                             (case method "ping" {:ok true}))
                           (fn [s] (reset! sent s)))]
  (rpc/handle-message srv (rpc/frame (rpc/request 1 "ping" {})))
  @sent)   ;=> the framed response: {\"id\":1,\"result\":{\"ok\":true}}
```

## Verify

```sh
kbb -M:test
```
