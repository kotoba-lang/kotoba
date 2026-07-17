import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "generated ESM artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.equal(generated.kotobaArtifact.entry, null);

const api = generated.instantiateKotoba({});
assert.ok(Object.isFrozen(api));
assert.deepEqual(Object.keys(api), ["add1"]);
assert.equal(api.add1(41n), 42n);

console.log("native-web-library: entryless frozen export boundary passed");
