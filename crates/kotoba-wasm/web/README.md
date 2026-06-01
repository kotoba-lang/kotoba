# kotoba browser node — web integration (ADR-2606013600)

Run the kotoba **read engine in the browser**: `kotoba-wasm` (the `kotoba-kqe`
Datom arrangement compiled to wasm) behind a transparent Service Worker, so the
yoro feed reads resolve locally with no server query round-trip.

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

On activate the SW pulls `ai.gftd.apps.kotoba.datomic.datoms` once from
`https://kotoba.etzhayyim.com` (graph `yoro-social-v1`) and hydrates the
arrangement. Re-point it at runtime:

```js
navigator.serviceWorker.controller.postMessage({ type: 'config', remote: 'https://…', graph: 'bafy…' });
```

## Scope (what runs locally vs. falls through)

- **Local (wasm)**: `app.bsky.actor.searchActors` / `app.etzhayyim.yoro.actor.searchActors`.
- **Network fallback (hybrid)**: every other `/xrpc/*` and any local error —
  `event.respondWith(fetch(request))`. Posts/follows/writes stay on the network
  until P2 (`transact` + OPFS) and the wider reader surface land.

## Phase status (ADR-2606013600)

- **P0 ✅** kqe read engine on wasm32 (`cargo test -p kotoba-wasm`).
- **P1 ✅ (this)** `loadDatoms()` hydration from `datomic.datoms` + Service-Worker
  transparent `/xrpc` shim + wasm-pack web bundle. JS bindings verified in node.
- **P1 remaining** IdbBlockStore persistence (survive reload without reseed) +
  delta sync.
- **P2** local `transact` + OPFS journal.
- **P3** `BrowserComponentRuntime` (jco) for in-browser Pregel/UDF guests.
