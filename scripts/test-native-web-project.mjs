import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "generated project ESM artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.equal(generated.kotobaArtifact.valueProfile, "typed-v1");
assert.match(generated.kotobaArtifact.moduleGraphDigest, /^[0-9a-f]{64}$/);
assert.ok(Object.isFrozen(generated.kotobaArtifact.moduleSourceDigests));
assert.deepEqual(Object.keys(generated.kotobaArtifact.moduleSourceDigests), [
  "fixture.app",
  "fixture.text",
]);
for (const digest of Object.values(generated.kotobaArtifact.moduleSourceDigests)) {
  assert.match(digest, /^[0-9a-f]{64}$/);
}
const api = generated.instantiateKotoba({});
assert.deepEqual(Object.keys(api), ["welcome"]);
assert.equal(api.welcome("言葉"), "こんにちは、言葉");
assert.throws(() => api.welcome(1n), /invalid-string/);

console.log("native-web-project: closed module graph passed");
