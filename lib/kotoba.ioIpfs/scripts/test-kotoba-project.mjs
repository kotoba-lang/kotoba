import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "compiled Kotoba artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.match(generated.kotobaArtifact.moduleGraphDigest, /^[0-9a-f]{64}$/);
assert.deepEqual(Object.keys(generated.kotobaArtifact.moduleSourceDigests), [
  "kotoba.lang.ipfs.http-status",
  "kotoba.lang.ipfs.status-bounds",
]);

const api = generated.instantiateKotoba({});
for (const status of [199n, 200n, 204n, 299n, 300n, 500n]) {
  const expected = status >= 200n && status <= 299n ? 1n : 0n;
  assert.equal(api["http-ok"](status), expected);
}

console.log("io-ipfs Kotoba closed-project pilot passed");
