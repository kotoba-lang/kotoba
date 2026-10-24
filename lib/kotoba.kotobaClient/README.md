# kotoba-client

`kotoba-lang/kotoba-client` is the shared CLJC home for browser-oriented
orchestration over kotoba's content-addressed graph: CID-verified block
ingest and hydrate-to-convergence over injected fetch/store ports. It
mirrors the deleted `KotobaNode.ingestBlock` / `hydrateViaBlocks` JS/wasm
client (git-history-only since `kotoba-lang/kotoba` commit `604896171b`,
2026-07-01 — the whole Rust workspace, including the browser client, was
removed with no CLJC replacement plan). See
`90-docs/adr/2607010930-clj-wgsl-migration.md` Phase 6.

This is the top of the dependency chain landed for that phase:
`multiformats`/`dag-cbor` (existing) → `ipld` → `prolly-tree` → `quad-store`
→ `kqe` → `kotoba-client` (this repo).

**Disambiguation (ADR-2607050900):** not to be confused with
[`kotobase-client`](https://github.com/kotoba-lang/kotobase-client) (a
separate, CACAO-authed ClojureScript client specific to the kotobase.net
tenant Datom plane) or [`kotobase`](https://github.com/kotoba-lang/kotobase)
(the server-side umbrella datom database `kotobase-client` talks to). This
repo has no CACAO auth and is not scoped to any single tenant — it's a
generic block-ingest client any browser-side consumer (e.g. `p2p`) can use.

Since the tag-42 migration (see the superproject ADR), the walk is
**generic**: `kotoba-client.ipld-hydrate/missing-cids` follows real IPLD
links via `ipld.core/links`, so one walker hydrates prolly-tree nodes,
quad-store commit blocks, and commit-dag commits alike.
`kotoba-client.prolly-hydrate` remains as a delegating compatibility
facade.

## Use

```clojure
(require '[kotoba-client.core :as kc]
         '[kotoba-client.ipld-hydrate :as ih]
         '[prolly-tree.core :as pt])

;; server side: build a tree, keep its blocks in `server`
(def server (atom {}))
(def root (pt/build-tree (fn [cid bytes] (swap! server assoc cid bytes))
                          (sort-by first [["a" 1] ["b" 2]])))

;; client side: start empty, hydrate over injected ports
(def client (atom {}))
(def client-store {:put! (fn [cid bytes] (swap! client assoc cid bytes))
                    :get-fn (fn [cid] (get @client cid))})

(kc/hydrate-via-blocks {:missing-cids ih/missing-cids
                         :fetch-block (fn [cid] (get @server cid))
                         :store client-store}
                        root)

(pt/lookup (:get-fn client-store) root "a")  ;=> 1, resolved entirely client-side
```

`kotoba-client.core/ingest-block` re-hashes every fetched block and throws
on a CID mismatch — untrusted bytes from `fetch-block` are never accepted
into `store` unverified.

## IPNS-record signature verification

`kotoba-client.core/verify-ipns-head` (ADR-2607061800, `:clj`-only)
resolves the gap the deleted client's `hydrate-and-query-verified!` once
covered: a fetched IPNS head record's signature is checked against its
own `:public_key_multibase` did:key (via `kotoba-lang/tech-ipfs-specs-
ipns`'s `ipns.head`), with no server trusted to have told the truth —
`hydrate-via-blocks` should only be pointed at `(:value record)` once
`:valid?` comes back true.

## What is NOT in this landing

A `:cljs` port of `verify-ipns-head` — `ipns.head` itself is `:clj`-only
(tracked as its own follow-up, not fabricated here).

A Service-Worker-equivalent request interception (the deleted `kotoba-sw.js`
transparently answering same-origin `datomic.q` fetches from the local
wasm store) is also out of scope here — that is host/browser-glue, not
domain logic, and belongs in a thin adapter once this core is proven.

## Test

```bash
kbb -M:test
```

## License

MIT
