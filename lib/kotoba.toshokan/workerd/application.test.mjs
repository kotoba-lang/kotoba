import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createApplication } from "./application.mjs";

class MemoryObjects {
  values = new Map();
  version = 0;

  get(key) {
    const value = this.values.get(key);
    return value
      ? { bytes: value.bytes.slice(), etag: value.etag }
      : null;
  }

  put(key, input, expected = undefined, immutable = false) {
    const current = this.values.get(key);
    if (immutable && current) return null;
    if (expected !== undefined && current?.etag !== expected) return null;
    const bytes = typeof input === "string"
      ? new TextEncoder().encode(input)
      : new Uint8Array(input);
    const value = { bytes: bytes.slice(), etag: `v${++this.version}` };
    this.values.set(key, value);
    return { etag: value.etag };
  }
}

const xml = await readFile(
  new URL("../test/fixtures/ndl-sru-multi-sample.xml", import.meta.url)
);
const objects = new MemoryObjects();
const token = "t".repeat(64);
const host = Object.freeze({
  config: Object.freeze({
    get: name => ({
      NDL_QUERY: "title=\"夏目漱石\"",
      NDL_MAX_RECORDS: "8"
    })[name] ?? null
  }),
  secret: Object.freeze({ get: name => name === "TOSHOKAN_RUN_TOKEN" ? token : null }),
  clock: Object.freeze({ now: () => 1_785_050_000_000 }),
  http: Object.freeze({
    fetch: async () => ({ status: 200, body: new Uint8Array(xml) })
  }),
  objectStore: Object.freeze({
    get: async (_binding, key) => objects.get(key),
    put: async (_binding, key, value) => objects.put(key, value),
    putImmutable: async (_binding, key, value) =>
      objects.put(key, value, undefined, true),
    compareAndSet: async (_binding, key, expected, value) => {
      const result = objects.put(key, value, expected);
      return result
        ? { won: true, etag: result.etag }
        : { won: false };
    }
  })
});

const application = createApplication(host);
const health = await application.fetch(new Request("https://example.test/health"));
assert.equal(health.status, 200);
assert.equal((await health.json()).host, "kotoba.generated-workerd/v1");

const denied = await application.fetch(new Request("https://example.test/run", {
  method: "POST"
}));
assert.equal(denied.status, 401);

const run = await application.fetch(new Request("https://example.test/run", {
  method: "POST",
  headers: { authorization: `Bearer ${token}` }
}));
assert.equal(run.status, 200);
const receipt = await run.json();
assert.equal(receipt.ok, true);
assert.equal(receipt.recordCount, 8);
assert.equal(receipt.records.filter(record => record.ok).length, 7);
assert.equal(receipt.records.filter(record => !record.ok).length, 1);
assert.equal(typeof receipt.kotobase.head, "string");
assert.equal(
  receipt.kotobase.entity["library/chunk-root"][0],
  receipt.chunkManifest.rootSha256
);

const latest = await application.fetch(new Request("https://example.test/latest"));
assert.equal(latest.status, 200);
assert.equal((await latest.json()).kotobase.head, receipt.kotobase.head);

console.log("closed generated-host application flow: ok");
