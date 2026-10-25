# org-ethereum-jsonrpc

[![CI](https://github.com/kotoba-lang/org-ethereum-jsonrpc/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ethereum-jsonrpc/actions/workflows/ci.yml)

An [Ethereum JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/)
client, [kotobase](https://github.com/kotoba-lang/kotobase)-backed
(ADR-2607172600 in `com-junkawasaki/root`).

## Permanent safety boundary — read this first

**This repo is a read-only observer of public Ethereum chain data. This is
not a v0.1-vs-later phasing decision — it is a standing, permanent scope
boundary:**

- It **never** calls or exposes `eth_sendTransaction`, `eth_sendRawTransaction`,
  `eth_sign`, `eth_signTransaction`, `eth_accounts`, any `personal_*` method,
  or any other method that constructs, signs, or broadcasts a transaction.
- It **never** handles a private key. It has **no wallet functionality** of
  any kind. It does not implement contract deployment.
- It **bundles no hardcoded provider credentials or API keys.** The target
  node/provider URL (`:endpoint`) is always a value the caller / deploy
  shell supplies — see `kotobase.ethereum.client/create-client`.
- `eth_call` is included and is **read-only**: it executes a contract call
  as a state-read simulation against node state and returns the result. It
  does not execute any state-changing operation and cannot broadcast
  anything.

The method whitelist enforcing this (`kotobase.ethereum.rpc/eth-method-whitelist`)
is **enforced in code**, not just documented: every request-building
(`build-request`) and result-decoding (`decode-result`) entry point checks
it and throws `ex-info` (`:type :kotobase.ethereum.rpc/disallowed-method`)
for anything else — see `test/kotobase/ethereum/rpc_test.cljk`'s
`whitelist-rejects-out-of-scope-methods` test, which asserts the whitelist
actually rejects `eth_sendTransaction`/`eth_sendRawTransaction`/`eth_sign`/
`personal_*`/an arbitrary unknown method, not merely that this repo's own
call sites happen not to use them.

```clojure
(require '[kotobase.ethereum.rpc :as rpc])

rpc/eth-method-whitelist
;; => #{"eth_blockNumber" "eth_getBlockByNumber" "eth_getBlockByHash"
;;      "eth_getTransactionByHash" "eth_getBalance" "eth_call"
;;      "eth_getLogs" "eth_chainId"}

(rpc/build-request "eth_sendTransaction" [{}] 1)
;; => throws ex-info: "method not on the read-only whitelist ..."
```

## Layout

| Namespace | File | Shape |
|---|---|---|
| `kotobase.ethereum.rpc` | `src/kotobase/ethereum/rpc.cljk` | Pure JSON-RPC 2.0 request/response shaping, the whitelist, hex-quantity decode, block/transaction/log decode into clean EDN. No I/O. |
| `kotobase.ethereum.client` | `src/kotobase/ethereum/client.cljk` | `.cljs`-only HTTP transport (Node's built-in `fetch`), caches observed data into a `kotobase.store/IStore`. |

Same core/transport split as every sibling repo in this project
(`kotoba-lang/dtn`, `kotoba-lang/nostr`, `kotoba-lang/org-bitcoin-p2p`, ...):
`rpc.cljc` has zero HTTP/socket concepts and is fully unit-testable on both
`nbb`/cljs and the JVM compat suite; `client.cljs` is the only namespace
that touches the network, and it's a thin, pure consumer of `rpc.cljc`.

## Usage

```clojure
(require '[kotobase.ethereum.client :as client])

(def c (client/create-client {:endpoint "https://ethereum-sepolia-rpc.publicnode.com"}))
;; :endpoint is always caller-supplied — nothing here is hardcoded.

(-> (client/chain-id! c) (.then #(println "chain id:" %)))
;; => chain id: 11155111

(-> (client/get-block-by-number! c "latest" false)
    (.then (fn [block] (println "block #" (:number block) (:hash block)))))

(-> (client/get-balance! c "0x000000000000000000000000000000000000dEaD" "latest")
    (.then #(println "balance (wei, decimal string):" %)))

(-> (client/call-contract! c {"to" "0xfFf9976782d46cC05630D1f6eBAb18b2324d6B14"
                              "data" "0x95d89b41"} ;; symbol() read-only call
                            "latest")
    (.then #(println "raw ABI-encoded return data:" %)))
```

## Decode conventions

`kotobase.ethereum.rpc` decodes the Ethereum JSON-RPC spec's own
QUANTITY/DATA field distinction:

- **QUANTITY** fields expected to stay well inside the platform safe-integer
  range (block number, timestamp, gas, index, chain id, nonce, ...) decode
  to a plain integer (`hex->long`).
- **QUANTITY** fields that can genuinely need full 256-bit precision (wei
  amounts: balance, `value`, `gasPrice`, `maxFeePerGas`, ...) decode to an
  exact **decimal string** (`hex->decimal-string`) — arbitrary-precision on
  both `:clj` and `:cljs`, avoiding float64/int64 precision loss.
- **DATA** fields (hashes, addresses, calldata/`input`, signature `r`/`s`/`v`,
  bloom filters, ...) are opaque byte strings, not numbers — they pass
  through as the original `0x...` hex string.
- `eth_call`'s result is ABI-encoded contract-return bytes. Decoding that
  requires the target contract's ABI, which this repo does not implement
  (out of scope — this is a JSON-RPC transport, not an ABI/contract
  library), so it passes through as the raw hex string.

Decoded maps use kebab-case keywords mirroring the spec's own field names
(`:blockNumber` -> `:block-number`, `:gasPrice` -> `:gas-price`, ...).

## Caching policy (`kotobase.ethereum.client`)

Kept deliberately simple for v0.1 — not over-engineered:

| Method | Cached? |
|---|---|
| `eth_chainId` | Forever, per `:cache-scope`. A network's chain id never changes. |
| `eth_getBlockByNumber` / `eth_getBlockByHash` | Forever, but **only** when the request identifies a *concrete* block (a numeric hex tag or a 32-byte hash) — never for `"latest"`/`"earliest"`/`"pending"`/`"safe"`/`"finalized"`. Caveat: a block within roughly the last ~2 epochs of the real chain tip could in principle still be reorged out even though it was returned for a concrete number/hash at fetch time — this is a "confirmed data" cache, not a canonical-chain guarantee for the most recent handful of blocks. |
| `eth_getTransactionByHash` | Only once the transaction is actually mined (decoded result has a non-nil `:block-hash`). A pending transaction (result `nil`, or unmined) is never cached, so a later call can observe it land. |
| `eth_getLogs` | Forever, but **only** when both `fromBlock` and `toBlock` in the filter are concrete hex quantities (not a mutable tag) — an already-finalized historical log range doesn't change. |
| `eth_blockNumber`, `eth_getBalance`, `eth_call` | Never. Current/mutable-state reads; `eth_getBalance`/`eth_call` do accept a block-tag parameter and a correct per-`(address, block)` cache is possible in principle, but that's more machinery than this v0.1 needs. |

Every cache collection is namespaced under `:cache-scope` (default: the
endpoint URL) so one shared `IStore` can safely serve multiple
networks/endpoints without key collisions.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority):

```bash
git clone https://github.com/kotoba-lang/kotobase ../kotobase
git clone https://github.com/kotoba-lang/kotobase-protocols ../kotobase-protocols
git clone https://github.com/kotoba-lang/text ../text
kbb --backend sci --classpath "src:test:../kotobase/src:../kotobase-protocols/src:../text/src" bin/run_tests.cljk
```

`../text` is required (`kotobase.ethereum.rpc` requires `kotoba.lang.text`);
without it the run stops at `Could not find namespace: kotoba.lang.text`.
[`docs/operator-quickstart.md`](docs/operator-quickstart.md) walks the whole
path, with dependencies pinned to the `deps.edn` SHAs, the expected output of
each step, and a check that the whitelist refuses a write method.

`test/kotobase/ethereum/rpc_test.cljk` is pure-logic unit tests against
**real fixture JSON** — every fixture in that file was captured live from a
real, free, public Sepolia testnet JSON-RPC endpoint
(`https://ethereum-sepolia-rpc.publicnode.com`, no API key), not
hand-invented shapes; see the namespace docstring for exactly which calls
were captured.

`test/kotobase/ethereum/client_test.cljk` unit-tests
`kotobase.ethereum.client`'s caching policy and whitelist enforcement
against an **injected fake `:fetch-fn`** — deterministic, no real network
I/O, safe to run on every CI push.

`test/kotobase/ethereum/live_smoke_demo.cljk` is **not** a unit test — it's
an executable demo that makes real outbound HTTP JSON-RPC calls against a
real public Sepolia endpoint (`eth_chainId`, `eth_blockNumber`,
`eth_getBlockByNumber`, `eth_getBlockByHash`, `eth_getBalance`), proving a
genuine live round-trip. It is **not** run by CI (network
availability/flakiness — the same reason `kotoba-lang/dtn`'s real-socket
transport demos live outside its deterministic test suite); run it
manually:

```bash
kbb --backend sci --classpath "src:test:../kotobase/src:../kotobase-protocols/src:../text/src" \
  test/kotobase/ethereum/live_smoke_demo.cljk
```

Verified live 2026-07-17 against `https://ethereum-sepolia-rpc.publicnode.com`
— all 5 calls round-tripped (chain id `11155111`, a real block number/hash,
`eth_getBlockByHash` round-tripping to the same block fetched by number,
and a real balance query), `RESULT: all live calls round-tripped`, exit 0.

The `:test` alias in `deps.edn` is the JVM **compat** suite for
`kotobase.ethereum.rpc` only (`client.cljs` is `.cljs`-only and needs a
Node-hosted `fetch`, so it isn't part of the JVM suite):

```bash
kbb -X:test
```

## License

Apache-2.0
