import crypto from "node:crypto";
import fs from "node:fs";
import {canonical, privateCheckpointMaterial} from "./checkpoint-material.mjs";

const sha256 = value => crypto.createHash("sha256").update(value).digest("hex");

export function verifyTransparencyLog({file, publicKey}) {
  const verifier = publicKey?.type === "public" ? publicKey : crypto.createPublicKey(publicKey);
  const publicKeyDer = verifier.export({type: "spki", format: "der"}).toString("base64");
  const receipts = [];
  const byIdempotencyKey = new Map();
  for (const [index, line] of fs.readFileSync(file, "utf8").split("\n").entries()) {
    if (!line) continue;
    let receipt;
    try { receipt = JSON.parse(line); } catch { throw new Error(`invalid transparency JSON at line ${index + 1}`); }
    const {receipt_sha256: recordedHash, signature, ...unsigned} = receipt;
    const expectedPrevious = receipts.at(-1)?.receipt_sha256 ?? null;
    if (receipt.sequence !== receipts.length + 1 || receipt.previous_receipt_sha256 !== expectedPrevious ||
        receipt.signer_public_key !== publicKeyDer ||
        !crypto.verify(null, Buffer.from(canonical(unsigned)), verifier, Buffer.from(signature, "base64")) ||
        recordedHash !== sha256(canonical({...unsigned, signature})))
      throw new Error(`transparency receipt verification failed at line ${index + 1}`);
    const existing = byIdempotencyKey.get(receipt.idempotency_key);
    if (existing && existing.checkpoint_digest !== receipt.checkpoint_digest)
      throw new Error(`transparency idempotency conflict at line ${index + 1}`);
    receipts.push(receipt);
    byIdempotencyKey.set(receipt.idempotency_key, receipt);
  }
  return receipts;
}

export class SignedTransparencyAnchor {
  constructor({file, privateKey, disclosureSalt, clock = () => new Date().toISOString()}) {
    if (!file || !privateKey) throw new Error("transparency anchor requires file and signing key");
    this.file = file;
    this.privateKey = privateKey;
    this.publicKey = crypto.createPublicKey(privateKey);
    this.publicKeyDer = this.publicKey.export({type: "spki", format: "der"}).toString("base64");
    this.disclosureSalt = disclosureSalt;
    this.clock = clock;
    this.receipts = [];
    this.byIdempotencyKey = new Map();
    fs.closeSync(fs.openSync(file, "a", 0o600));
    fs.chmodSync(file, 0o600);
    this.#replay();
    this.fd = fs.openSync(file, "a");
  }

  #replay() {
    for (const receipt of verifyTransparencyLog({file: this.file, publicKey: this.publicKey})) {
      this.receipts.push(receipt);
      this.byIdempotencyKey.set(receipt.idempotency_key, receipt);
    }
  }

  append(effect) {
    const material = privateCheckpointMaterial(effect, this.disclosureSalt);
    const existing = this.byIdempotencyKey.get(material.idempotencyKey);
    if (existing) {
      if (existing.checkpoint_digest !== material.checkpointDigest)
        throw new Error("transparency idempotency conflict");
      return {created: false, receipt: structuredClone(existing)};
    }
    const unsigned = {schema: "kotobase.signed-checkpoint-receipt.v1", authoritative: false,
      sequence: this.receipts.length + 1,
      previous_receipt_sha256: this.receipts.at(-1)?.receipt_sha256 ?? null,
      idempotency_key: material.idempotencyKey, checkpoint_digest: material.checkpointDigest,
      anchored_at: this.clock(), signer_public_key: this.publicKeyDer};
    const signature = crypto.sign(null, Buffer.from(canonical(unsigned)), this.privateKey).toString("base64");
    const receipt = {...unsigned, signature, receipt_sha256: sha256(canonical({...unsigned, signature}))};
    fs.writeSync(this.fd, `${JSON.stringify(receipt)}\n`);
    fs.fsyncSync(this.fd);
    this.receipts.push(receipt);
    this.byIdempotencyKey.set(receipt.idempotency_key, receipt);
    return {created: true, receipt: structuredClone(receipt)};
  }

  close() { if (this.fd !== undefined) { fs.closeSync(this.fd); this.fd = undefined; } }
}

export function generateTransparencyIdentity() {
  return crypto.generateKeyPairSync("ed25519");
}
