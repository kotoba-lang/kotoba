import assert from "node:assert/strict";
import {
  head,
  openDatabase,
  pull,
  transact
} from "./generated/kotobase/engine.js";

class MemoryR2 {
  #objects = new Map();
  #version = 0;

  async get(key) {
    const stored = this.#objects.get(key);
    if (!stored) return null;
    return {
      etag: stored.etag,
      arrayBuffer: async () => stored.bytes.buffer.slice(
        stored.bytes.byteOffset,
        stored.bytes.byteOffset + stored.bytes.byteLength
      ),
      text: async () => new TextDecoder().decode(stored.bytes)
    };
  }

  async put(key, value, options = {}) {
    const current = this.#objects.get(key);
    const condition = options.onlyIf;
    if (condition?.etagDoesNotMatch === "*" && current) return null;
    if (condition?.etagMatches && current?.etag !== condition.etagMatches)
      return null;
    const bytes = typeof value === "string"
      ? new TextEncoder().encode(value)
      : new Uint8Array(value);
    const etag = `v${++this.#version}`;
    this.#objects.set(key, { bytes: bytes.slice(), etag });
    return { etag };
  }
}

const bucket = new MemoryR2();
const database = openDatabase(bucket, "test/kotobase");
assert.equal(await head(database), null);

const committed = await transact(database, [
  ["ndl:test", "library/source", "ndl"],
  ["ndl:test", "library/title", "吾輩は猫である"],
  ["ndl:test", "library/chunk-root", "sha256:test"]
]);
assert.equal(typeof committed, "string");
assert.equal(await head(database), committed);

const entity = await pull(database, "ndl:test", [
  "library/source", "library/title", "library/chunk-root"
]);
assert.deepEqual(entity["library/source"], ["ndl"]);
assert.deepEqual(entity["library/title"], ["吾輩は猫である"]);
assert.deepEqual(entity["library/chunk-root"], ["sha256:test"]);

console.log("Kotobase Engine R2 contract + transact/pull: ok");
