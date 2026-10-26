// kuro-opfs-worker.js — the OPFS block store Worker (S2 of ADR-2609041240).
//
// Runs INSIDE a Worker (OPFS sync access handles are Worker-only). Speaks the
// request/reply wire contract declared in kuro.host.opfs (`:kuro.opfs/*`).
//
//   put     {bytes: Uint8Array}            -> {cid}      (mint + cache write)
//   get     {cid}                          -> {bytes|nil} (cache, nil on miss;
//                                                          gateway fetch is the
//                                                          page's job via its
//                                                          own fetch in v1 —
//                                                          the Worker has no
//                                                          credential scope)
//   delete  {cid}                          -> {removed}  (idempotent: not-cached is success)
//   publish {cids: [..], bytesByCid: {..}} -> {published: n}  (explicit op —
//                                                          never automatic)
//   stats   {}                             -> {count, bytes}
//   drop-cache {}                          -> {removed: n} (partial failure is visible)
//
// Storage layout: one flat directory, file name = the CID string, file
// content = the raw block bytes. Sync access handles keep get-block
// synchronous inside the Worker, which is what kuro.fs's injected
// `get-block` seam needs.

const HEADER_LEN = 4;

// --- CID mint (same math as kuro.host.cid, on Uint8Array + WebCrypto) ------

const B32 = "abcdefghijklmnopqrstuvwxyz234567";

function base32LowerNoPad(bytes) {
  let bits = 0, value = 0, out = "";
  for (const b of bytes) {
    value = ((value << 8) | b) >>> 0;
    bits += 8;
    while (bits >= 5) {
      bits -= 5;
      out += B32[(value >>> bits) & 31];
    }
  }
  if (bits > 0) out += B32[(value << (5 - bits)) & 31];
  return out;
}

async function mintCid(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const cid = new Uint8Array(HEADER_LEN + digest.length);
  cid[0] = 0x01; cid[1] = 0x55; cid[2] = 0x12; cid[3] = 0x20;
  cid.set(digest, HEADER_LEN);
  return "b" + base32LowerNoPad(cid);
}

// --- OPFS handle management ------------------------------------------------

let rootDir = null;
const handles = new Map(); // cid string -> sync access handle

async function getRoot() {
  if (!rootDir) {
    rootDir = await navigator.storage.getDirectory();
  }
  return rootDir;
}

function handleKey(cid) {
  // CID strings are filesystem-safe (base32 lower), but keep a prefix so a
  // stray non-CID name can never collide with the block namespace.
  return "blk-" + cid;
}

async function putBlock(cid, bytes) {
  const dir = await getRoot();
  const key = handleKey(cid);
  const fh = await dir.getFileHandle(key, { create: true });
  const h = await fh.createSyncAccessHandle();
  h.truncate(0);
  h.write(bytes, { at: 0 });
  h.flush();
  h.close();
  handles.set(key, { size: bytes.length });
  return bytes.length;
}

async function getBlock(cid) {
  const dir = await getRoot();
  const key = handleKey(cid);
  let fh;
  try {
    fh = await dir.getFileHandle(key, { create: false });
  } catch (e) {
    return null; // cache miss — NOT an error; the gateway fetch is upstream's job
  }
  const h = await fh.createSyncAccessHandle();
  try {
    const size = h.getSize();
    const buf = new Uint8Array(size);
    h.read(buf, { at: 0 });
    return buf;
  } finally {
    h.close();
  }
}

async function deleteBlock(cid) {
  // Contract (issue #54, settled): delete on a cid that is not cached is
  // IDEMPOTENT SUCCESS — the cache is origin-scoped and custody is upstream,
  // so "was never cached" and "already removed" are the same final state. It
  // reports {removed: false}, not an error. A REAL failure (open handle,
  // permission, quota) propagates as an error reply — never a bare ok:false.
  const dir = await getRoot();
  const key = handleKey(cid);
  try {
    await dir.getFileHandle(key, { create: false });
  } catch (e) {
    handles.delete(key);
    return { removed: false };
  }
  await dir.removeEntry(key);
  handles.delete(key);
  return { removed: true };
}

async function stats() {
  const dir = await getRoot();
  let count = 0, total = 0;
  for await (const name of dir.keys()) {
    if (!name.startsWith("blk-")) continue;
    count += 1;
    const fh = await dir.getFileHandle(name, { create: false });
    const f = await fh.getFile();
    total += f.size;
  }
  return { count, bytes: total };
}

async function dropCache() {
  // Contract (issue #54, settled): drop-cache reports {removed: n} so a
  // partial failure is visible. A removeEntry that throws midway leaves some
  // blocks deleted; the reply must say how many went, not just a generic
  // worker-error with null. The error propagates AFTER recording what was
  // actually removed.
  const dir = await getRoot();
  const names = [];
  for await (const name of dir.keys()) {
    if (name.startsWith("blk-")) names.push(name);
  }
  let removed = 0;
  try {
    for (const n of names) {
      await dir.removeEntry(n);
      removed += 1;
    }
  } finally {
    handles.clear();
  }
  return { removed };
}

// --- request/reply dispatch ------------------------------------------------

async function dispatch(msg) {
  const op = msg["kuro.opfs/op"] || msg.kuro_opfs_op;
  // Workers receive structured clones; keyword namespaced keys survive as
  // plain string keys. Normalize here so the page glue can send either.
  const p = msg["kuro.opfs/payload"] || msg.kuro_opfs_payload || {};
  switch (op) {
    case "put": {
      const bytes = p.bytes;
      if (!(bytes instanceof Uint8Array)) return { error: "bytes-required" };
      const cid = await mintCid(bytes);
      await putBlock(cid, bytes);
      return { result: { cid } };
    }
    case "get": {
      const bytes = await getBlock(p.cid);
      return { result: { bytes: bytes || null } };
    }
    case "delete": {
      return { result: await deleteBlock(p.cid) };
    }
    case "publish": {
      // v1: the page passes blocks it already holds; the Worker verifies each
      // block's bytes hash to its claimed CID before counting it published.
      let published = 0;
      for (const cid of p.cids || []) {
        const bytes = p.bytesByCid[cid];
        if (!bytes) continue;
        const actual = await mintCid(bytes);
        if (actual !== cid) return { error: "cid-mismatch" };
        await putBlock(cid, bytes);
        published += 1;
      }
      return { result: { published } };
    }
    case "stats":
      return { result: await stats() };
    case "drop-cache":
      return { result: await dropCache() };
    default:
      return { error: "unknown-op" };
  }
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  const id = msg["kuro.opfs/id"] || msg.kuro_opfs_id;
  const op = msg["kuro.opfs/op"] || msg.kuro_opfs_op;
  let out;
  try {
    const r = await dispatch(msg);
    out = {
      "kuro.opfs/type": "reply",
      "kuro.opfs/id": id,
      "kuro.opfs/op": op,
      "kuro.opfs/result": r.result ?? null,
      "kuro.opfs/error": r.error ?? null,
    };
  } catch (e) {
    out = {
      "kuro.opfs/type": "reply",
      "kuro.opfs/id": id,
      "kuro.opfs/op": op,
      "kuro.opfs/result": null,
      "kuro.opfs/error": "worker-error",
    };
  }
  self.postMessage(out);
};
