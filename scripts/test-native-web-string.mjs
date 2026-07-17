import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "generated ESM artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.equal(generated.kotobaArtifact.valueProfile, "typed-v1");
assert.deepEqual(generated.kotobaArtifact.stringLimits, {
  literalBytes: 4096,
  moduleLiteralBytes: 65536,
  valueBytes: 65536,
});

const api = generated.instantiateKotoba({});
assert.equal(api.greet("言葉"), "こんにちは、言葉");
assert.equal(api["byte-length"]("言葉"), 6n);
assert.throws(() => api.greet(1n), /invalid-string/);
assert.throws(() => api.greet("x".repeat(65536)), /string-too-large/);

console.log("native-web-string: typed UTF-8 boundary passed");
