// kotoba-opfs.js — OPFS append-only transaction journal (P2).
//
// ADR-2606013600 P2/D5. A local `transact()` lands in the wasm read engine
// immediately, but to survive a cold restart BEFORE the write is compacted into
// the IndexedDB snapshot, every batch is appended here as one NDJSON line
// (`[{e,a,v_edn}]\n`). On the next boot the Service Worker replays the journal
// on top of the snapshot via `node.replayJournal(text)` — idempotent, so a write
// already folded into the snapshot replays to a no-op.
//
// Lifecycle (write-through compaction, run by the SW on each write):
//   1. node.transact(batch)        — apply
//   2. appendTx(graph, batch)      — durability point (this file)
//   3. idb.putSnapshot(...)        — compaction (snapshot now includes the write)
//   4. resetJournal(graph)         — snapshot is authoritative; journal cleared
// A crash between 2 and 4 is safe: boot replays the journal and the resolved-CID
// dedup collapses the snapshot⊕journal overlap.
//
// Primary backend is OPFS (`navigator.storage.getDirectory()` →
// `createSyncAccessHandle`, available in Workers). Where OPFS sync handles are
// unavailable (e.g. Safari private mode) we fall back to an IndexedDB-backed
// append log so durability is preserved — same `read/append/reset` contract.

const DIR = "kotoba-journal";

function fileName(graph) {
  // Keep the per-graph file name filesystem-safe.
  return `${graph.replace(/[^a-zA-Z0-9._-]/g, "_")}.ndjson`;
}

async function opfsAvailable() {
  try {
    return (
      typeof navigator !== "undefined" &&
      navigator.storage &&
      typeof navigator.storage.getDirectory === "function"
    );
  } catch {
    return false;
  }
}

async function journalDir() {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(DIR, { create: true });
}

// ── OPFS backend (sync access handle — Worker-safe) ────────────────────────

async function opfsAppend(graph, line) {
  const dir = await journalDir();
  const fh = await dir.getFileHandle(fileName(graph), { create: true });
  const access = await fh.createSyncAccessHandle();
  try {
    const size = access.getSize();
    const bytes = new TextEncoder().encode(line.endsWith("\n") ? line : line + "\n");
    access.write(bytes, { at: size });
    access.flush();
  } finally {
    access.close();
  }
}

async function opfsRead(graph) {
  const dir = await journalDir();
  let fh;
  try {
    fh = await dir.getFileHandle(fileName(graph), { create: false });
  } catch {
    return ""; // no journal yet
  }
  const file = await fh.getFile();
  return file.text();
}

async function opfsReset(graph) {
  const dir = await journalDir();
  try {
    const fh = await dir.getFileHandle(fileName(graph), { create: false });
    const access = await fh.createSyncAccessHandle();
    try {
      access.truncate(0);
      access.flush();
    } finally {
      access.close();
    }
  } catch {
    /* nothing to reset */
  }
}

// ── IndexedDB fallback (append log) ────────────────────────────────────────

const FB_DB = "kotoba-journal-fb";
const FB_STORE = "lines";
let fbPromise = null;

function fbOpen() {
  if (fbPromise) return fbPromise;
  fbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(FB_DB, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(FB_STORE)) {
        // autoIncrement key preserves append order; `graph` index for scan.
        const os = db.createObjectStore(FB_STORE, { keyPath: "seq", autoIncrement: true });
        os.createIndex("graph", "graph", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return fbPromise;
}

async function fbAppend(graph, line) {
  const db = await fbOpen();
  return new Promise((resolve, reject) => {
    const req = db.transaction(FB_STORE, "readwrite").objectStore(FB_STORE).add({ graph, line });
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function fbRead(graph) {
  const db = await fbOpen();
  return new Promise((resolve, reject) => {
    const out = [];
    const idx = db.transaction(FB_STORE, "readonly").objectStore(FB_STORE).index("graph");
    const req = idx.openCursor(IDBKeyRange.only(graph));
    req.onsuccess = () => {
      const cur = req.result;
      if (cur) {
        out.push(cur.value.line);
        cur.continue();
      } else {
        resolve(out.join("\n"));
      }
    };
    req.onerror = () => reject(req.error);
  });
}

async function fbReset(graph) {
  const db = await fbOpen();
  return new Promise((resolve, reject) => {
    const idx = db.transaction(FB_STORE, "readwrite").objectStore(FB_STORE).index("graph");
    const req = idx.openCursor(IDBKeyRange.only(graph));
    req.onsuccess = () => {
      const cur = req.result;
      if (cur) {
        cur.delete();
        cur.continue();
      } else {
        resolve();
      }
    };
    req.onerror = () => reject(req.error);
  });
}

// ── public contract (auto-selects backend) ─────────────────────────────────

let useOpfs = null;
async function backend() {
  if (useOpfs === null) useOpfs = await opfsAvailable();
  return useOpfs;
}

/** Append one transact batch (a `[{e,a,v_edn}]` JSON string) to the journal. */
export async function appendTx(graph, batchJson) {
  const line = batchJson.replace(/\n/g, " "); // one batch per line
  return (await backend()) ? opfsAppend(graph, line) : fbAppend(graph, line);
}

/** Read the full journal text (newline-separated batches) for `graph`. */
export async function readJournal(graph) {
  return (await backend()) ? opfsRead(graph) : fbRead(graph);
}

/** Clear the journal for `graph` after its writes are compacted into a snapshot. */
export async function resetJournal(graph) {
  return (await backend()) ? opfsReset(graph) : fbReset(graph);
}

/** Which durability backend is active — for `status`/debug. */
export async function journalBackend() {
  return (await backend()) ? "opfs" : "indexeddb-fallback";
}
