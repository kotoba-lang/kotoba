# kotoba browser node — web integration (ADR-2606013600)

Run the kotoba **read/query engine in the browser**: `kotoba-wasm`
(`kotoba-kqe` plus the Datomic `q` engine compiled to wasm) behind a transparent
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

## Scope (what runs locally vs. falls through)

- **Local (wasm)**: `app.bsky.actor.searchActors` /
  `com.etzhayyim.yoro.actor.searchActors` and current-graph
  `com.etzhayyim.apps.kotoba.datomic.q`.
- **Network fallback (hybrid)**: every other `/xrpc/*` and any local error —
  `event.respondWith(fetch(request))`. Posts/follows/writes stay on the network
  until P2 (`transact` + OPFS) and the wider reader surface land.

## Phase status (ADR-2606013600)

- **P0 ✅** kqe read engine on wasm32 (`cargo test -p kotoba-wasm`).
- **P1 ✅ (this)** `datomic.sync`/`datomic.datoms` hydration from the server's
  IPFS-backed Datomic head + Service-Worker transparent `/xrpc` shim +
  wasm-pack web bundle.
- **P1.5 ✅** browser-local Datomic `q` over hydrated datoms.
- **P1 remaining** IdbBlockStore persistence (survive reload without reseed) +
  delta sync from block/CID manifests.
- **P2** local `transact` + OPFS journal.
- **P3** `BrowserComponentRuntime` (jco) for in-browser Pregel/UDF guests.
