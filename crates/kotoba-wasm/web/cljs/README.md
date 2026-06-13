# kotoba browser read-plane — ClojureScript

ClojureScript glue for the in-browser kotoba node. Implements
**docs/ADR-browser-cid-query-vs-p2p.md**: a browser queries a *pinned* graph with
**zero peer connection**, because query is content-addressed.

```
resolve+verify signed head   →   sync covering index roots
   (kotoba.ipns, gateway-untrusted)       (datomic.sync)
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
        CID-verified block pull (block.get)  →  hydrateFromProlly  →  datomicQ
                       kotoba.node — all in-browser, no libp2p / WebRTC
```

## Namespaces

| ns             | what                                                                    |
|----------------|-------------------------------------------------------------------------|
| `kotoba.ipns`  | `resolve-head` / `verify-record` — member-signed IPNS head, verified in-wasm (`KotobaNode.verifyIpnsRecord`). Whoever serves the record is untrusted. |
| `kotoba.idb`   | IndexedDB persistence (DB `kotoba-node` v2): `snapshots` + `rawblocks` stores. |
| `kotoba.blocks`| CID-verified, IndexedDB-cached block sync: `block-get`, `hydrate-via-blocks`, `hydrate-from-idb-blocks`. |
| `kotoba.node`  | `hydrate-and-query!` (works today, head via `datomic.sync`), `hydrate-and-query-verified!` (fully trustless head), plus `hydrate!` / `query` / `sync-index-roots`. |
| `kotoba.write` | `publish!` — trustless write: `block.put` push + `ipns.publish` (member-signed head advance). Sovereign/DID-scoped graphs only; shared graphs use CACAO `datomic.transact`. |

Trust lives in the CID (`ingestBlock` re-derives `sha2-256(dag-cbor)` and rejects
mismatches) and, for the mutable head, in the Ed25519 signature — never in the
transport. That is why no P2P is needed for read.

## Build

```sh
npm install            # once — pulls shadow-cljs
npm run build          # release → ../cljs-out/kotoba-node.js (ESM)
npm run watch          # dev, hot-reload
```

Output is `../cljs-out/kotoba-node.js`, importable as ESM.

## Use from the Service Worker (kotoba-sw.js)

```js
import { hydrateAndQuery } from "./cljs-out/kotoba-node.js";

// answer a datomic.q POST entirely in-browser:
const resultJson = await hydrateAndQuery(
  node, GRAPH, req.query_edn, req.inputs_edn, { remote: REMOTE });
```

`hydrate-and-query-verified!` additionally verifies the signed head first, via
`GET /xrpc/com.etzhayyim.apps.kotoba.ipns.head?graph=<cid>` (now implemented —
`xrpc::ipns_head`, lexicon `ipns/head.json`).

## Status

- `npm run build` → **0 cljs warnings**, emits `kotoba-node.js`.
- Read plane (`hydrate-and-query!`) is exercisable today against any
  `kotoba-server` that serves `datomic.sync` + `block.get` (Public graphs).
- `hydrate-and-query-verified!` is now fully trustless: signed `ipns.head`
  (`xrpc::ipns_head`) → `commitIndexRoots` derives the EAVT root from the verified
  head → CID-verified block sync. No `datomic.sync` trust on that path.
- `kotoba.write/publish!` completes the symmetric, signature-authorized write path
  (`block.put` + `ipns.publish`) for sovereign graphs.
- The original `kotoba-blocks.js` / `kotoba-idb.js` are superseded by
  `kotoba.blocks` / `kotoba.idb` (the JS files remain until `kotoba-sw.js`, itself
  still JS, is migrated to import the cljs `cljs-out/kotoba-node.js`).
