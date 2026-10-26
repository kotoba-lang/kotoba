import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { runKotobaScript } from "./kotoba-script-host.mjs";
import { createHash } from "node:crypto";

const dir = await mkdtemp(join(tmpdir(), "kotoba-script-host-"));
const guest = join(dir, "guest.mjs");
const source = `
export const kotobaArtifact=Object.freeze({schema:'kotoba-js-artifact/v1',sourceDigest:'source',kirDigest:'kir',compilerVersion:'compiler',requiredCapabilities:Object.freeze([])});
export function instantiateKotoba(grants){
  if(Object.keys(grants).length) throw new Error('unexpected-grant');
  return Object.freeze({main(){return 42n;}});
}`;
await writeFile(guest, source);
const manifest = {
  "kotoba.artifact/schema": "kotoba-js-artifact/v1",
  "kotoba.artifact/source-digest": "source",
  "kotoba.artifact/kir-digest": "kir",
  "kotoba.artifact/compiler-version": "compiler",
  "kotoba.artifact/output-digest": createHash("sha256").update(source).digest("hex")
};
const verification = { sourceText: source, manifest };

const result = await runKotobaScript(pathToFileURL(guest).href, { verification });
assert.equal(result.value, 42n);
await assert.rejects(() => runKotobaScript(pathToFileURL(guest).href,
  { providers: new Map([[7, value => value]]), verification }), /capability-grant-mismatch/);
await assert.rejects(() => runKotobaScript(pathToFileURL(guest).href,
  { verification: { sourceText: `${source}\n// tampered`, manifest } }), /output-digest-mismatch/);
console.log("kotoba-script host: ok");
