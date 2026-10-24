import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {generateTransparencyIdentity, SignedTransparencyAnchor,
  verifyTransparencyLog} from "../transparency-anchor.mjs";

const salt = `0x${"12".repeat(32)}`;
const effect = {"effect/type": "checkpoint/append", idempotency_key: "job-1",
  payload: {"database-id": "private/db", epoch: 1, "logical-checkpoint-root": "private/root"}};

test("signed transparency receipts are durable, chained and idempotent", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "checkpoint-transparency-"));
  const file = path.join(dir, "receipts.jsonl");
  const {privateKey, publicKey} = generateTransparencyIdentity();
  let anchor = new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt,
    clock: () => "2026-08-04T00:00:00.000Z"});
  const first = anchor.append(effect);
  const duplicate = anchor.append(effect);
  const second = anchor.append({...effect, idempotency_key: "job-2",
    payload: {...effect.payload, epoch: 2}});
  assert.equal(first.created, true);
  assert.equal(duplicate.created, false);
  assert.equal(duplicate.receipt.receipt_sha256, first.receipt.receipt_sha256);
  assert.equal(second.receipt.previous_receipt_sha256, first.receipt.receipt_sha256);
  assert.equal(JSON.stringify(first.receipt).includes("private/db"), false);
  assert.equal(JSON.stringify(first.receipt).includes("private/root"), false);
  anchor.close();
  assert.equal(verifyTransparencyLog({file, publicKey}).length, 2,
    "witness verification must require only the public key");
  anchor = new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt});
  assert.equal(anchor.receipts.length, 2);
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  anchor.close();
});

test("transparency replay fails closed on modification", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "checkpoint-transparency-tamper-"));
  const file = path.join(dir, "receipts.jsonl");
  const {privateKey} = generateTransparencyIdentity();
  const anchor = new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt});
  anchor.append(effect);
  anchor.close();
  fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace(/"sequence":1/, '"sequence":2'));
  assert.throws(() => new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt}),
    /verification failed/);
});
