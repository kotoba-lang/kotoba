# kotobase-browser-worker

kotobase-peer's **browser shell** — the sibling to
[`kotobase-cljc-worker`](https://github.com/kotoba-lang/kotobase-cljc-worker)
(the Cloudflare/R2 shell), wiring the SAME pure XRPC handler
(`kotobase.cljc-worker.handler`) and the SAME block-miss trampoline
(`kotobase.cljc-worker.r2/with-blocks`, reused verbatim) to IndexedDB
instead of R2 — so the whole `transact`/`datoms`/`q`/`pull`/`fold`
datom-plane surface runs entirely inside a browser tab, no server
required for storage or compute (ADR-2607051700, app-aozora).

## Why

`kotobase.aozora.app` in production already runs `kotobase-cljc-worker`
(built on `kotobase-peer`). This repo proves the same engine, unmodified,
also runs client-side: an actor's browser can hold its own graph locally
(IndexedDB blocks + head), transact/query it purely offline, and only
need a network round-trip to sync with a remote peer/relay for
federation — not for correctness. See
[`kotoba-lang/kotoba`'s `docs/ADR-browser-cid-query-vs-p2p.md`](https://github.com/kotoba-lang/kotoba)
for the read-plane design this extends to writes.

## Phase 1 scope (what's here today)

- `src/kotobase/browser_worker/idb.cljc` — IndexedDB-backed block/head
  store (`get-bytes`/`put-bytes!`/`get-head`/`put-head-if-match!`), the
  browser counterpart to `kotobase.cljc-worker.r2`.
- `src/kotobase/browser_worker/browser.cljc` — `run-read`/`run-write`
  orchestration, mirroring `kotobase.cljc-worker.worker`'s
  `run-read`/`run-write-attempt`/`flush-and-cas!` exactly, including the
  read-your-own-writes fix for INCIDENT 2607032800 (a merged
  buffer+trampoline `:get-fn` during a write — see the docstring on
  `browser.cljc`'s `run-write-attempt`).
- No CACAO/HTTP layer yet — this is local-same-page use (a caller in the
  same tab already holds the signing key). Wiring a real actor identity,
  and a fetch-handler for OTHER pages/peers to call over the network, is
  a follow-up, not required to prove the storage/engine claim.

## Verify

```bash
npm install
npm run build-test          # amu compile --target wasm32-browser browser-test → out/browser-test/
cd out/browser-test && python3 -m http.server 8823
# open http://localhost:8823/index.html in an actual browser — cljs.test
# results print to the page and console. All tests transact/fold/read
# against a REAL IndexedDB, not a mock.
```

## Dependency closure

Same as `kotobase-cljc-worker` (`shadow-cljs.edn` source-paths, relative
to the west checkout): `kotobase-peer`, `datom`, `arrangement`,
`prolly-tree`, `chain`, `ipld`, `multiformats`, `dag-cbor`,
`kotobase-cljc-worker` (for `handler`/`r2`, reused rather than
duplicated).
