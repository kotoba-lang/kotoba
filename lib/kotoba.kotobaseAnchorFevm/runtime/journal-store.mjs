import fs from "node:fs";
import crypto from "node:crypto";

function digest(value) { return crypto.createHash("sha256").update(value).digest("hex"); }
function stable(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
}

export class DurableAnchorJournal {
  constructor(file) {
    this.file = file;
    this.jobs = new Map();
    this.receipts = new Map();
    this.sequence = 0;
    fs.closeSync(fs.openSync(file, "a", 0o600));
    fs.chmodSync(file, 0o600);
    this.#replay();
    this.fd = fs.openSync(file, "a");
  }

  #replay() {
    const body = fs.readFileSync(this.file, "utf8");
    for (const [index, line] of body.split("\n").entries()) {
      if (!line) continue;
      let envelope;
      try { envelope = JSON.parse(line); } catch { throw new Error(`invalid journal JSON at line ${index + 1}`); }
      const encoded = stable(envelope.event);
      if (envelope.sequence !== this.sequence + 1 || envelope.sha256 !== digest(encoded))
        throw new Error(`journal integrity failure at line ${index + 1}`);
      this.sequence = envelope.sequence;
      this.#apply(envelope.event);
    }
  }

  #apply(event) {
    if (event.type === "job-put" || event.type === "job-cas") this.jobs.set(event.key, event.record);
    else if (event.type === "receipt") this.receipts.set(event.transaction_hash, event.receipt);
  }

  #append(event) {
    const encoded = stable(event);
    const line = JSON.stringify({sequence: ++this.sequence, sha256: digest(encoded), event}) + "\n";
    fs.writeSync(this.fd, line);
    fs.fsyncSync(this.fd);
    this.#apply(event);
  }

  putIfAbsent(key, record) {
    if (this.jobs.has(key)) return false;
    this.#append({type: "job-put", key, record});
    return true;
  }

  compareAndSet(key, expectedRevision, record) {
    const current = this.jobs.get(key);
    if (!current || current.revision !== expectedRevision || record.revision !== expectedRevision + 1) return false;
    this.#append({type: "job-cas", key, expected_revision: expectedRevision, record});
    return true;
  }

  recordReceipt(transactionHash, receipt) {
    this.#append({type: "receipt", transaction_hash: transactionHash, receipt});
  }

  recordEvidence(kind, evidence) { this.#append({type: "evidence", kind, evidence}); }
  getJob(key) { return structuredClone(this.jobs.get(key)); }
  getReceipt(hash) { return structuredClone(this.receipts.get(hash)); }
  close() { if (this.fd !== undefined) { fs.closeSync(this.fd); this.fd = undefined; } }
}
