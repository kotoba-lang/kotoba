// kotoba-sw.js — transparent Service-Worker shim for the browser kotoba node.
//
// ADR-2606013600 D3 + P1 (IndexedDB persistence) + P2 (OPFS tx journal).
// Registered as a MODULE service worker:
//   navigator.serviceWorker.register('/kotoba-sw.js', { type: 'module' })
//
// It intercepts same-origin `/xrpc/...` reads (`searchActors`, `datomic.q`) and
// writes (`datomic.transact`) and serves them from the in-browser kotoba read
// engine (kotoba-wasm). `@etzhayyim/yoro-rw-free` is unchanged: it just does
// `fetch('/xrpc/...')` and cannot tell the local wasm node from a remote server.
//
// Durability (the P1/P2 upgrade over the P0 "reseed every boot" shim):
//   • boot loads the persisted snapshot from IndexedDB and replays the OPFS tx
//     journal BEFORE any network — `/search` works offline, no laptop tunnel;
//   • a remote `datomic.datoms` pull is folded in as an idempotent DELTA in the
//     background and re-persisted (the wasm node dedups by resolved entity CID);
//   • `transact` writes through: apply → append to OPFS journal → persist
//     snapshot → clear journal (write-through compaction).
//
// Build the pkg next to this file:  wasm-pack build --target web --out-dir pkg

import init, { KotobaNode } from "./pkg/kotoba_wasm.js";
import { getSnapshot, putSnapshot } from "./kotoba-idb.js";
import { appendTx, readJournal, resetJournal, journalBackend } from "./kotoba-opfs.js";

// Remote peer to seed/delta the local arrangement from (P1 sync source).
let REMOTE = "https://kotoba.etzhayyim.com";
let GRAPH = "bafyreibljg5gzye47fldkfq6m4vgy55kcjyez2vx432dubttou36g5yryq"; // yoro-social-v1

const SEARCH_NSIDS = new Set([
  "app.bsky.actor.searchActors",
  "com.etzhayyim.yoro.actor.searchActors",
]);
const DATOMIC_Q_NSID = "com.etzhayyim.apps.kotoba.datomic.q";
const TRANSACT_NSID = "com.etzhayyim.apps.kotoba.datomic.transact";
const STATUS_NSID = "com.etzhayyim.apps.kotoba.node.status";

let node = null;
let ready = null;

// Persist the node's current state and clear the now-compacted journal.
async function persist() {
  if (!node) return;
  await putSnapshot(GRAPH, {
    datomsJson: node.snapshot(),
    cid: node.snapshotCid(),
    count: node.datomCount(),
  });
  await resetJournal(GRAPH);
}

// Background delta sync from the remote peer — never blocks `ready`.
async function deltaSync() {
  try {
    await fetch(`${REMOTE}/xrpc/com.etzhayyim.apps.kotoba.datomic.sync`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ graph: GRAPH }),
    }).catch(() => null);
    const r = await fetch(`${REMOTE}/xrpc/com.etzhayyim.apps.kotoba.datomic.datoms`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ graph: GRAPH, index: ":aevt" }),
    });
    if (!r.ok) {
      console.warn(`[kotoba-sw] delta HTTP ${r.status} — keeping local state`);
      return;
    }
    const j = await r.json();
    const applied = node.loadDatoms(JSON.stringify(j.datoms || [])); // idempotent
    console.log(`[kotoba-sw] delta merged ${applied} new datoms (head ${node.snapshotCid().slice(0, 12)}…)`);
    if (applied > 0) await persist();
  } catch (e) {
    console.warn("[kotoba-sw] delta sync failed (offline?) — local state intact", e);
  }
}

async function boot() {
  await init(); // instantiate kotoba_wasm_bg.wasm
  node = new KotobaNode();

  // P1: offline-first — load the persisted snapshot before any network.
  try {
    const snap = await getSnapshot(GRAPH);
    if (snap && snap.datomsJson) {
      const n = node.loadDatoms(snap.datomsJson);
      console.log(`[kotoba-sw] restored ${n} datoms from IndexedDB snapshot`);
    }
  } catch (e) {
    console.warn("[kotoba-sw] snapshot restore failed", e);
  }

  // P2: replay the OPFS tx journal on top of the snapshot (recovers any write
  // not yet compacted). Idempotent against the snapshot.
  try {
    const journal = await readJournal(GRAPH);
    if (journal && journal.trim()) {
      const n = node.replayJournal(journal);
      console.log(`[kotoba-sw] replayed ${n} datoms from ${await journalBackend()} journal`);
      if (n > 0) await persist(); // fold recovered writes into the snapshot
    }
  } catch (e) {
    console.warn("[kotoba-sw] journal replay failed", e);
  }

  // The node is usable now (offline). Refresh from the peer in the background.
  deltaSync();
}

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  ready = boot();
  event.waitUntil(self.clients.claim());
});

// Page control: (re)point the sync source / force a reseed, or push a
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
      await persist(); // seed is durable immediately
      console.log(`[kotoba-sw] seeded ${n} datoms (same-origin) → persisted`);
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
  if (!m) return;
  const nsid = m[1];
  const ours =
    SEARCH_NSIDS.has(nsid) ||
    nsid === DATOMIC_Q_NSID ||
    nsid === TRANSACT_NSID ||
    nsid === STATUS_NSID;
  if (!ours) return; // not ours → default network

  event.respondWith(
    (async () => {
      try {
        if (ready) await ready;
        if (!node) throw new Error("kotoba node not ready");

        // ── P2 write path: local transact + journal + compaction ──────────
        if (nsid === TRANSACT_NSID) {
          if (event.request.method !== "POST") return fetch(event.request);
          const req = await event.request.clone().json();
          if (req.graph && req.graph !== GRAPH) return fetch(event.request);
          const batch = Array.isArray(req.datoms) ? req.datoms : req;
          const batchJson = JSON.stringify(batch);
          const applied = node.transact(batchJson);
          await appendTx(GRAPH, batchJson); // durability point
          await persist(); // compaction: snapshot now includes the write, journal cleared
          return json({ applied, cid: node.snapshotCid(), count: node.datomCount() }, "local-wasm-transact");
        }

        // ── node status ───────────────────────────────────────────────────
        if (nsid === STATUS_NSID) {
          return json(
            { graph: GRAPH, count: node.datomCount(), cid: node.snapshotCid(), journal: await journalBackend() },
            "local-wasm-status",
          );
        }

        // ── datomic.q read ────────────────────────────────────────────────
        if (nsid === DATOMIC_Q_NSID) {
          if (event.request.method !== "POST") return fetch(event.request);
          const req = await event.request.clone().json();
          if (req.graph && req.graph !== GRAPH) return fetch(event.request);
          if (req.as_of || req.since || req.history || req.remote_peer || req.remote_ipns_name) {
            return fetch(event.request); // time-travel / federation → server
          }
          const body = node.datomicQ(req.query_edn || "", JSON.stringify(req.inputs_edn || []));
          return new Response(body, {
            status: 200,
            headers: { "content-type": "application/json; charset=utf-8", "x-kotoba-sw": "local-wasm-datomic" },
          });
        }

        // ── searchActors read ─────────────────────────────────────────────
        const q = url.searchParams.get("q") || "";
        const body = node.searchActors(q); // JSON string: {"actors":[...]}
        return new Response(body, {
          status: 200,
          headers: { "content-type": "application/json; charset=utf-8", "x-kotoba-sw": "local-wasm" },
        });
      } catch (e) {
        // Hybrid fallback: anything the local node can't serve → network.
        return fetch(event.request);
      }
    })(),
  );
});

function json(obj, tag) {
  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8", "x-kotoba-sw": tag },
  });
}
