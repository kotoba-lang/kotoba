// kotoba-sw.js — transparent Service-Worker shim for the browser kotoba node.
//
// ADR-2606013600 D3. Registered as a MODULE service worker:
//   navigator.serviceWorker.register('/kotoba-sw.js', { type: 'module' })
//
// It intercepts same-origin `/xrpc/...searchActors` reads and serves them from
// the in-browser kotoba read engine (kotoba-wasm) hydrated from a one-time
// `datomic.datoms` sync. `@etzhayyim/yoro-rw-free` is unchanged: it just does
// `fetch('/xrpc/...')`, and cannot tell the local wasm node from a remote
// server. Anything we can't serve falls through to the network (hybrid).
//
// Build the pkg next to this file:  wasm-pack build --target web --out-dir pkg

import init, { KotobaNode } from "./pkg/kotoba_wasm.js";

// Remote peer to seed the local arrangement from (P1 sync source). Override by
// posting {type:'config', remote, graph} to the SW, or editing here.
let REMOTE = "https://kotoba.etzhayyim.com";
let GRAPH = "bafyreibljg5gzye47fldkfq6m4vgy55kcjyez2vx432dubttou36g5yryq"; // yoro-social-v1

// NSIDs we resolve locally (both the bsky alias and the yoro-native form).
const SEARCH_NSIDS = new Set([
  "app.bsky.actor.searchActors",
  "app.etzhayyim.yoro.actor.searchActors",
]);

let node = null;
let ready = null;

async function boot() {
  await init(); // instantiate kotoba_wasm_bg.wasm
  node = new KotobaNode();
  // P1 sync: pull the yoro-social datoms once, CID-addressed + verifiable
  // upstream, and hydrate the kqe arrangement.
  try {
    const r = await fetch(`${REMOTE}/xrpc/ai.gftd.apps.kotoba.datomic.datoms`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ graph: GRAPH, index: ":aevt" }),
    });
    if (r.ok) {
      const j = await r.json();
      const n = node.loadDatoms(JSON.stringify(j.datoms || []));
      console.log(`[kotoba-sw] hydrated ${n} datoms from ${REMOTE}`);
    } else {
      console.warn(`[kotoba-sw] sync HTTP ${r.status} — serving empty until reseed`);
    }
  } catch (e) {
    console.warn("[kotoba-sw] hydrate failed (offline?) — empty node", e);
  }
}

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  ready = boot();
  event.waitUntil(self.clients.claim());
});

// Allow the page to (re)point the sync source / force a reseed, or to push a
// same-origin datoms snapshot directly (CORS-free seeding, used by demo.html).
self.addEventListener("message", (event) => {
  const m = event.data || {};
  if (m.type === "config") {
    if (m.remote) REMOTE = m.remote;
    if (m.graph) GRAPH = m.graph;
    ready = boot();
  } else if (m.type === "seed" && Array.isArray(m.datoms)) {
    ready = (async () => {
      await init();
      node = new KotobaNode();
      const n = node.loadDatoms(JSON.stringify(m.datoms));
      console.log(`[kotoba-sw] seeded ${n} datoms (same-origin)`);
    })();
    if (event.ports && event.ports[0]) ready.then(() => event.ports[0].postMessage({ ok: true }));
  }
});

self.addEventListener("fetch", (event) => {
  let url;
  try {
    url = new URL(event.request.url);
  } catch {
    return;
  }
  if (url.origin !== self.location.origin) return; // same-origin only
  const m = url.pathname.match(/^\/xrpc\/([^/?]+)$/);
  if (!m || !SEARCH_NSIDS.has(m[1])) return; // not ours → default network

  event.respondWith(
    (async () => {
      try {
        if (ready) await ready;
        if (!node) throw new Error("kotoba node not ready");
        const q = url.searchParams.get("q") || "";
        const body = node.searchActors(q); // JSON string: {"actors":[...]}
        return new Response(body, {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
            "x-kotoba-sw": "local-wasm",
          },
        });
      } catch (e) {
        // Hybrid fallback: anything the local node can't serve → network.
        return fetch(event.request);
      }
    })(),
  );
});
