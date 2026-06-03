// integration.test.mjs — JS↔wasm boundary test of the P1/P2 persistence cycle.
//
//   node web/integration.test.mjs
//
// Drives the real `KotobaNode` wasm bindings (pkg-node) through the exact call
// sequence the Service Worker + kotoba-idb.js + kotoba-opfs.js perform, with the
// IndexedDB snapshot and the OPFS journal modelled as plain strings (which is
// all they ever store). Proves P1 (reseed-free reload from snapshot, idempotent
// delta) and P2 (write survives cold restart via journal replay) across the
// wasm-bindgen boundary — the layer the native Rust tests don't exercise.

import { KotobaNode } from "../pkg-node/kotoba_wasm.js";

let failures = 0;
function check(name, cond) {
  if (cond) {
    console.log(`  ok   ${name}`);
  } else {
    failures++;
    console.error(`  FAIL ${name}`);
  }
}
function actorCount(node, q = "") {
  return JSON.parse(node.searchActors(q)).actors.length;
}

// Models of the two durable backends the glue owns.
let IDB = null; // kotoba-idb.js snapshot row { datomsJson, cid }
let JOURNAL = []; // kotoba-opfs.js append-only lines

function persist(node) {
  IDB = { datomsJson: node.snapshot(), cid: node.snapshotCid() };
  JOURNAL = []; // compaction: snapshot now authoritative
}

console.log("P1 — seed, persist, reseed-free cold reload");
{
  const live = new KotobaNode();
  const seed = JSON.stringify([
    { e: "bafySeed", a: ":yoro.profile/did", v_edn: '"did:web:etzhayyim.com:actor:tsumugi"' },
    { e: "bafySeed", a: ":yoro.profile/displayName", v_edn: '"紡ぎ Tsumugi"' },
  ]);
  check("seed loads 2 datoms", live.loadDatoms(seed) === 2);
  persist(live); // → IndexedDB
  check("snapshot has a content CID", typeof IDB.cid === "string" && IDB.cid.length > 8);

  // Cold reload: brand-new node, NO seed, NO network — only the IDB snapshot.
  const cold = new KotobaNode();
  check("reload from snapshot restores 2 datoms", cold.loadDatoms(IDB.datomsJson) === 2);
  check("tsumugi searchable after reseed-free reload", actorCount(cold, "tsumugi") === 1);
  check("cold snapshot CID == persisted CID (stable identity)", cold.snapshotCid() === IDB.cid);
}

console.log("P1 — idempotent delta (re-sync never duplicates)");
{
  const node = new KotobaNode();
  const delta = JSON.stringify([
    { e: "bafyA", a: ":yoro.profile/did", v_edn: '"did:web:etzhayyim.com:actor:watatsuna"' },
  ]);
  check("first delta applies 1", node.loadDatoms(delta) === 1);
  check("same delta re-applies 0 (idempotent)", node.loadDatoms(delta) === 0);
  check("exactly one profile after double sync", actorCount(node, "watatsuna") === 1);
}

console.log("P2 — write survives cold restart via OPFS journal replay");
{
  // Running node: seed compacted into IDB; a local write appended to the journal.
  const live = new KotobaNode();
  live.loadDatoms(
    JSON.stringify([{ e: "bafySeed", a: ":yoro.profile/did", v_edn: '"did:web:etzhayyim.com:actor:tsumugi"' }]),
  );
  persist(live); // snapshot = seed only, journal empty

  // transact (write-through): apply + append to journal — but DON'T compact yet
  // (simulates a crash after the durability point, before snapshot rewrite).
  const writeBatch = JSON.stringify([
    { e: "w1", a: ":yoro.profile/did", v_edn: '"did:web:etzhayyim.com:actor:newcomer"' },
    { e: "w1", a: ":yoro.profile/displayName", v_edn: '"✍ newcomer"' },
  ]);
  check("transact applies 2", live.transact(writeBatch) === 2);
  JOURNAL.push(writeBatch); // OPFS append (durability point)

  // ── CRASH ── cold restart: new node ← IDB snapshot, then replay the journal.
  const cold = new KotobaNode();
  cold.loadDatoms(IDB.datomsJson);
  const replayed = cold.replayJournal(JOURNAL.join("\n"));
  check("journal replay recovers the un-compacted write (2)", replayed === 2);
  check("seed actor present after restart", actorCount(cold, "tsumugi") === 1);
  check("written actor present after restart", actorCount(cold, "newcomer") === 1);

  // Re-replay the same journal (crash before journal truncation) → no dupes.
  check("re-replay is a no-op (snapshot⊕journal dedup)", cold.replayJournal(JOURNAL.join("\n")) === 0);
  check("still exactly one written actor", actorCount(cold, "newcomer") === 1);

  // Now compact and confirm the journal becomes empty against the new snapshot.
  persist(cold);
  const next = new KotobaNode();
  next.loadDatoms(IDB.datomsJson);
  check("post-compaction journal replays 0", next.replayJournal(JOURNAL.join("\n")) === 0);
  check("written actor still present from compacted snapshot", actorCount(next, "newcomer") === 1);
}

console.log("P3 — CID-verified block ingest + block-sync driver bindings");
{
  const node = new KotobaNode();
  const cid = node.snapshotCid(); // a valid CIDv1 dag-cbor sha2-256 multibase
  // Empty cache → the root block is reported missing (drives the BFS pull).
  const missing = node.missingBlockCids(cid);
  check("missingBlockCids on empty cache returns [root]", missing.length === 1 && missing[0] === cid);
  // Tampered ingest: bytes that don't hash to the claimed CID are rejected.
  let threw = false;
  try {
    node.ingestBlock(cid, new Uint8Array([1, 2, 3]));
  } catch {
    threw = true;
  }
  check("ingestBlock rejects a CID/bytes mismatch (trustless)", threw);
  check("rejected block is not cached", node.blockCount() === 0);
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
