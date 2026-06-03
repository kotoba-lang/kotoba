// kotoba-idb.js — IndexedDB snapshot store for the browser kotoba node (P1).
//
// ADR-2606013600 P1/D5. The wasm `KotobaNode` holds an in-memory kqe
// arrangement; this module gives it **durable, reseed-free** persistence by
// storing the node's canonical content-addressed snapshot (`node.snapshot()`,
// a `[{e,a,v_edn}]` JSON keyed per graph) plus its head CID.
//
// On cold start the Service Worker loads the snapshot from here BEFORE touching
// the network, so `/search` works offline and the laptop-tunnel read dependency
// is gone. A later remote `datomic.datoms` pull is folded in as an idempotent
// delta and re-persisted (the wasm node dedups by resolved entity CID).
//
// One row per graph: { graph, datomsJson, cid, count, ts }. The store is tiny
// (one snapshot per graph), so we overwrite in place rather than diffing blocks
// — the content-addressed `cid` lets callers skip a write when the head is
// unchanged.

const DB_NAME = "kotoba-node";
const DB_VERSION = 1;
const STORE = "snapshots";

let dbPromise = null;

function openIdb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "graph" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function tx(db, mode) {
  return db.transaction(STORE, mode).objectStore(STORE);
}

/** Load the persisted snapshot for `graph`, or null if none. */
export async function getSnapshot(graph) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const req = tx(db, "readonly").get(graph);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

/**
 * Persist the node's current snapshot for `graph`.
 * @param {string} graph
 * @param {{datomsJson: string, cid: string, count: number}} snap
 */
export async function putSnapshot(graph, snap) {
  const db = await openIdb();
  const row = {
    graph,
    datomsJson: snap.datomsJson,
    cid: snap.cid,
    count: snap.count,
    ts: Date.now(),
  };
  return new Promise((resolve, reject) => {
    const req = tx(db, "readwrite").put(row);
    req.onsuccess = () => resolve(row);
    req.onerror = () => reject(req.error);
  });
}

/** Drop the persisted snapshot for `graph` (debug / forced reseed). */
export async function clearSnapshot(graph) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const req = tx(db, "readwrite").delete(graph);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}
