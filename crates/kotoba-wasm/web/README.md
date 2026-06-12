# kotoba browser node — web integration (ADR-2606013600)

Run the kotoba **read/query engine in the browser**: `kotoba-wasm`
(`kotoba-query` plus the Datomic `q` engine compiled to wasm) behind a transparent
Service Worker, so yoro feed reads and Datomic queries resolve locally with no
server query round-trip after sync.

## Build the wasm bundle

```sh
# from crates/kotoba-wasm  (use the rustup toolchain — Homebrew rust lacks wasm32 std)
PATH="$HOME/.cargo/bin:$PATH" wasm-pack build --target web --out-dir web/pkg --release
```

Produces `web/pkg/{kotoba_wasm.js, kotoba_wasm_bg.wasm}` (~87 KiB gzip — within
the baien edge invariant, ADR-2605241900).

## Try it

Serve `web/` over HTTP (service workers require a secure/localhost origin):

```sh
cd web && python3 -m http.server 8088   # then open http://localhost:8088/demo.html
```

`demo.html` registers `kotoba-sw.js` and issues the *same* request
`@etzhayyim/yoro-rw-free` makes — `GET /xrpc/app.bsky.actor.searchActors?q=…` —
which the Service Worker answers from the local wasm node (`x-kotoba-sw: local-wasm`).
It also serves same-origin `POST /xrpc/com.etzhayyim.apps.kotoba.datomic.q` from the
hydrated local Datomic DB (`x-kotoba-sw: local-wasm-datomic`) when the request
targets the synced graph and does not ask for time-travel/history/remote reads.

## Wire into the yoro SvelteKit app

The reader already hits same-origin `/xrpc` (search/+page.svelte). Two steps:

1. **Ship the bundle**: copy `web/pkg/*` + `web/kotoba-sw.js` into the app's
   `static/` (so they serve at the origin root), e.g. `static/kotoba/pkg/*` and
   `static/kotoba-sw.js` (the SW imports `./pkg/kotoba_wasm.js` — keep them
   adjacent, so place `kotoba-sw.js` at `static/kotoba/kotoba-sw.js` with
   `pkg/` beside it, or adjust the import path).

2. **Register early** (e.g. in `+layout.svelte` `onMount`, browser-only):

   ```ts
   if ('serviceWorker' in navigator) {
     navigator.serviceWorker.register('/kotoba/kotoba-sw.js', { type: 'module' });
   }
   ```

That is the whole integration — the SW intercepts the existing `/xrpc`
searchActors fetches; nothing in `yoro-rw-free` or the search page changes.

## Sync source

On activate the SW calls `com.etzhayyim.apps.kotoba.datomic.sync` and then pulls
`com.etzhayyim.apps.kotoba.datomic.datoms` once from `https://kotoba.etzhayyim.com`
(graph `yoro-social-v1`). The server side resolves the IPNS/Datomic head and
reads the IPFS-backed blocks; the browser hydrates those Datoms into the local
KQE and Datomic engines. Re-point it at runtime:

```js
navigator.serviceWorker.controller.postMessage({ type: 'config', remote: 'https://…', graph: 'bafy…' });
```

## Persistence & durability (P1 IndexedDB + P2 OPFS journal)

The node is no longer a reseed-every-boot cache. Two small glue modules give it
durable, offline-first state:

- **`kotoba-idb.js`** — IndexedDB snapshot store. One row per graph holding the
  node's canonical content-addressed snapshot (`node.snapshot()` →
  `[{e,a,v_edn}]` JSON) + its head CID (`node.snapshotCid()`). On boot the SW
  loads this **before any network**, so `/search` works offline.
- **`kotoba-opfs.js`** — OPFS append-only tx journal (one `transact` batch per
  NDJSON line), with an IndexedDB fallback where OPFS sync handles are
  unavailable. On boot the SW replays it on top of the snapshot
  (`node.replayJournal(text)`) to recover any un-compacted write.

**Write-through compaction** (SW, per write): `transact` → `appendTx` (durability
point) → `putSnapshot` (snapshot now includes the write) → `resetJournal`. A crash
between the durability point and journal truncation is safe — boot replays the
journal and the node's **resolved-entity-CID dedup** collapses the snapshot⊕journal
overlap, so re-sync/replay is idempotent (no duplicate rows in the kqe vectors).

## Scope (what runs locally vs. falls through)

- **Local (wasm)**: `app.bsky.actor.searchActors` /
  `com.etzhayyim.yoro.actor.searchActors`; current-graph
  `com.etzhayyim.apps.kotoba.datomic.q`; **`…datomic.transact`** (P2 local write);
  **`…node.status`** (datom count + head CID + journal backend).
- **Network fallback (hybrid)**: every other `/xrpc/*`, time-travel/history/remote
  reads, cross-graph requests, and any local error —
  `event.respondWith(fetch(request))`. A background `datomic.datoms` **delta**
  refresh folds server state in idempotently and re-persists.

## Verify

- **Core logic (native):** `cargo test -p kotoba-wasm` — idempotent reload,
  deterministic snapshot CID, cold-restart journal replay without dupes.
- **JS↔wasm boundary:** `node web/integration.test.mjs` — drives the real wasm
  bindings through the exact P1/P2 call sequence the SW performs (snapshot ⇄
  reload ⇄ journal replay ⇄ compaction). 16 assertions.
- **Real browser:** serve `web/`, open `demo.html`, click **transact**, then
  **reload WITHOUT reseeding** — the write is still there (IndexedDB snapshot +
  OPFS journal), served `x-kotoba-sw: local-wasm` with no network.

## Phase status (ADR-2606013600)

- **P0 ✅** kqe read engine on wasm32 (`cargo test -p kotoba-wasm`).
- **P1 ✅** `datomic.sync`/`datomic.datoms` hydration + transparent `/xrpc` SW
  shim + wasm-pack bundle + **IndexedDB snapshot persistence** (reseed-free
  reload) + idempotent background **delta** refresh.
- **P1.5 ✅** browser-local Datomic `q` over hydrated datoms.
- **P2 ✅** local **`transact`** + **OPFS append-only journal** + write-through
  compaction (write survives cold restart; verified native + JS↔wasm).
- **P3 ✅ (Prolly traversal)** the browser reads the **canonical content-addressed
  Datom log**, not a JSON snapshot: a **CID-verifying `BlockCache`** + the same
  `ProllyTree::scan_prefix` the server uses + a `missingBlockCids` BFS driver.
  `kotoba-blocks.js` syncs blocks (`block.get` → IndexedDB, CID re-verified on
  ingest) then `hydrateFromProlly(root)`. Bindings: `ingestBlock` /
  `hydrateFromProlly` / `missingBlockCids` / `blockCount`. Verified native (incl.
  multi-level block-sync + tamper rejection) + JS↔wasm. (ADR-2606013600 D5 /
  ADR-2606022150 P3.)
- **P3 (guests, next)** `BrowserComponentRuntime` (jco) for in-browser Pregel/UDF
  guests (spikes under `web/p3-*`).
