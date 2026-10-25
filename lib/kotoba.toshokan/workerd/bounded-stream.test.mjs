import assert from "node:assert/strict";
import fs from "node:fs";
import { chunkText, frameXmlElements } from "./bounded-stream.mjs";
import { instantiateKotoba } from "./generated/ndl-parser.mjs";

const xml = fs.readFileSync("test/fixtures/ndl-sru-multi-sample.xml", "utf8");
const manifest = await chunkText(xml);
assert.equal(manifest.totalBytes, 85_797);
assert.equal(manifest.chunks.length, 3);
assert.match(manifest.rootSha256, /^[0-9a-f]{64}$/);

const frames = frameXmlElements(xml, "recordData");
assert.equal(frames.length, 8);
assert.ok(frames.every(frame => new TextEncoder().encode(frame).byteLength <= 65_536));

const outcomes = frames.map(frame => {
  try {
    const parser = instantiateKotoba({});
    const record = parser["record-data"](
      `<searchRetrieveResponse>${frame}</searchRetrieveResponse>`, 0n
    );
    assert.equal(record[1], true);
    const title = parser["bib-title"](record[2], 0n);
    assert.equal(title[1], true);
    return { ok: true, title: title[2] };
  } catch (error) {
    return { ok: false, error: error.message };
  }
});
assert.equal(outcomes.length, 8);
assert.ok(outcomes.some(outcome => outcome.ok && outcome.title));
console.log("bounded stream + Kotoba record parser: ok");
