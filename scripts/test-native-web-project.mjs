import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "generated project ESM artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.equal(generated.kotobaArtifact.valueProfile, "typed-v1");
const api = generated.instantiateKotoba({});
assert.deepEqual(Object.keys(api), ["welcome"]);
assert.equal(api.welcome("言葉"), "こんにちは、言葉");
assert.throws(() => api.welcome(1n), /invalid-string/);

console.log("native-web-project: closed module graph passed");
