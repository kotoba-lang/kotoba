import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {generateTransparencyIdentity, SignedTransparencyAnchor,
  verifyTransparencyLog} from "../runtime/transparency-anchor.mjs";

const revision = execFileSync("git", ["rev-parse", "HEAD"], {encoding: "utf8"}).trim();
if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error("qualification requires a full Git revision");
if (execFileSync("git", ["status", "--porcelain"], {encoding: "utf8"}).trim())
  throw new Error("refusing to qualify a dirty worktree");
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "kotobase-transparency-evidence-"));
fs.chmodSync(dir, 0o700);
const file = path.join(dir, "receipts.jsonl");
const {privateKey, publicKey} = generateTransparencyIdentity();
const salt = `0x${crypto.randomBytes(32).toString("hex")}`;
let anchor = new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt});
const base = {"effect/type": "checkpoint/append", idempotency_key: "qualification-1",
  payload: {"payload/version": 1, "database-id": "private/qualification", epoch: 1,
    "logical-checkpoint-root": crypto.randomBytes(32).toString("hex")}};
const first = anchor.append(base);
const duplicate = anchor.append(base);
const second = anchor.append({...base, idempotency_key: "qualification-2",
  payload: {...base.payload, epoch: 2}});
anchor.close();
const witnessReceipts = verifyTransparencyLog({file, publicKey});
anchor = new SignedTransparencyAnchor({file, privateKey, disclosureSalt: salt});
if (!first.created || duplicate.created || anchor.receipts.length !== 2 ||
    witnessReceipts.length !== 2 ||
    second.receipt.previous_receipt_sha256 !== first.receipt.receipt_sha256)
  throw new Error("transparency qualification invariant failed");
anchor.close();
console.log(JSON.stringify({schema: "kotobase.transparency-anchor-qualification.v1",
  source_revision: revision, receipts: 2, duplicate_suppressed: true,
  chain_verified_after_restart: true, public_key_witness_verified: true,
  final_receipt_sha256: second.receipt.receipt_sha256,
  raw_log_sha256: crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex"),
  raw_log: file}, null, 2));
