import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {DurableAnchorJournal} from "../journal-store.mjs";

test("journal survives restart and enforces revision CAS", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fevm-journal-"));
  const file = path.join(dir, "anchor.jsonl");
  const initial = {revision: 0, status: "pending"};
  const claimed = {revision: 1, status: "pending", lease: "worker-a"};
  let store = new DurableAnchorJournal(file);
  assert.equal(store.putIfAbsent("job-a", initial), true);
  assert.equal(store.putIfAbsent("job-a", initial), false);
  assert.equal(store.compareAndSet("job-a", 1, claimed), false);
  assert.equal(store.compareAndSet("job-a", 0, claimed), true);
  store.recordReceipt("tx-a", {block_hash: "block-a", confirmations: 5});
  store.recordEvidence("finality", {finalized: true});
  store.close();

  store = new DurableAnchorJournal(file);
  assert.deepEqual(store.getJob("job-a"), claimed);
  assert.deepEqual(store.getReceipt("tx-a"), {block_hash: "block-a", confirmations: 5});
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  store.close();
});

test("journal replay fails closed on tampering", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fevm-journal-tamper-"));
  const file = path.join(dir, "anchor.jsonl");
  const store = new DurableAnchorJournal(file);
  store.putIfAbsent("job-a", {revision: 0});
  store.close();
  fs.appendFileSync(file, `${JSON.stringify({sequence: 2, sha256: "0".repeat(64),
    event: {type: "evidence", kind: "forged"}})}\n`);
  assert.throws(() => new DurableAnchorJournal(file), /journal integrity failure/);
});
