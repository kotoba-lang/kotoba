// kotoba-blocks.js — P3 block-sync: hydrate the browser node by traversing the
// canonical Prolly tree over CID-verified blocks (ADR-2606013600 D5 / 2606022150).
//
// Unlike the P1 JSON-snapshot path, this pulls the actual content-addressed
// Prolly blocks and runs the SAME `scan_prefix` read engine the server runs:
//
//   1. BFS the tree by frontier — `node.missingBlockCids(root)` tells us which
//      blocks (referenced from `root`) we don't have yet; node decoding stays in
//      Rust/wasm;
//   2. fetch each missing block (IndexedDB cache first, else `block.get` from a
//      peer), hand it to `node.ingestBlock(cid, bytes)` which **re-verifies the
//      CID** (rejects tampered blocks), and persist the raw block to IndexedDB;
//   3. repeat until no block is missing, then `node.hydrateFromProlly(root)`.
//
// The raw blocks are stored content-addressed (CID → bytes) so a cold start
// replays the tree from IndexedDB with zero network — and any block, from any
// gateway, is trustless because its CID is re-derived on ingest.

const DB_NAME = "kotoba-node";
const DB_VERSION = 2; // bump from kotoba-idb.js v1 → adds the "rawblocks" store
const SNAP_STORE = "snapshots"; // shared with kotoba-idb.js
const BLOCK_STORE = "rawblocks";

let dbPromise = null;
function openIdb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(SNAP_STORE)) {
        db.createObjectStore(SNAP_STORE, { keyPath: "graph" });
      }
      if (!db.objectStoreNames.contains(BLOCK_STORE)) {
        db.createObjectStore(BLOCK_STORE); // key = CID multibase, value = Uint8Array
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function idbGetBlock(cid) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(BLOCK_STORE, "readonly").objectStore(BLOCK_STORE).get(cid);
    req.onsuccess = () => resolve(req.result ? new Uint8Array(req.result) : null);
    req.onerror = () => reject(req.error);
  });
}

async function idbPutBlock(cid, bytes) {
  const db = await openIdb();
  return new Promise((resolve, reject) => {
    const req = db
      .transaction(BLOCK_STORE, "readwrite")
      .objectStore(BLOCK_STORE)
      .put(bytes, cid);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// Fetch one block by CID from a remote peer's content-addressed gateway.
// `com.etzhayyim.apps.kotoba.block.get?cid=...` → { data_b64 }.
async function fetchBlockRemote(remote, cid) {
  const r = await fetch(`${remote}/xrpc/com.etzhayyim.apps.kotoba.block.get?cid=${encodeURIComponent(cid)}`);
  if (!r.ok) throw new Error(`block.get ${cid} → HTTP ${r.status}`);
  const j = await r.json();
  const b64 = j.data_b64;
  if (!b64) throw new Error(`block.get ${cid} → no data_b64`);
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

/**
 * Hydrate `node` by syncing the Prolly tree rooted at `root` over CID-verified
 * blocks (IndexedDB first, then `remote`), then traversing it locally.
 *
 * @param {KotobaNode} node  the wasm node (exposes ingestBlock / missingBlockCids / hydrateFromProlly)
 * @param {string} root      EAVT (or other index) root CID, multibase
 * @param {{remote: string, maxRounds?: number}} opts
 * @returns {Promise<number>} datoms applied
 */
export async function hydrateViaBlocks(node, root, opts) {
  const remote = opts.remote;
  const maxRounds = opts.maxRounds || 64;
  let rounds = 0;
  for (;;) {
    const missing = node.missingBlockCids(root); // Rust decodes; we just pull
    if (missing.length === 0) break;
    for (const cid of missing) {
      let bytes = await idbGetBlock(cid);
      if (!bytes) {
        bytes = await fetchBlockRemote(remote, cid);
      }
      node.ingestBlock(cid, bytes); // throws on CID mismatch — trustless
      await idbPutBlock(cid, bytes); // durable for cold start
    }
    if (++rounds > maxRounds) throw new Error("block sync did not converge");
  }
  return node.hydrateFromProlly(root);
}

/** Pre-seed the node's block cache from IndexedDB only (offline cold start). */
export async function hydrateFromIdbBlocks(node, root) {
  let rounds = 0;
  for (;;) {
    const missing = node.missingBlockCids(root);
    if (missing.length === 0) break;
    let progressed = false;
    for (const cid of missing) {
      const bytes = await idbGetBlock(cid);
      if (bytes) {
        node.ingestBlock(cid, bytes);
        progressed = true;
      }
    }
    if (!progressed) return null; // tree not fully cached offline → caller falls back
    if (++rounds > 64) break;
  }
  return node.hydrateFromProlly(root);
}
