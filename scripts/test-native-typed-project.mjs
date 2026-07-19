import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const artifactPath = process.argv[2];
assert.ok(artifactPath, "generated typed project artifact path is required");

const generated = await import(pathToFileURL(artifactPath).href);
assert.equal(generated.kotobaArtifact.valueProfile, "typed-v1");
assert.match(generated.kotobaArtifact.moduleGraphDigest, /^[0-9a-f]{64}$/);
const api = generated.instantiateKotoba({});
assert.deepEqual(Object.keys(api), ["main"]);
assert.equal(api.main(), 42n);

console.log("native-typed-project: bounded Web project returned 42");
