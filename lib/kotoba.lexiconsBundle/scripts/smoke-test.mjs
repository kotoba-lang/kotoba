import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Lexicons } from "@atproto/lexicon";

const docs = JSON.parse(readFileSync(new URL("../src/lexicons.gen.json", import.meta.url), "utf8"));
assert.ok(Array.isArray(docs) && docs.length > 0, "bundle must contain lexicon documents");
for (let index = 1; index < docs.length; index++) {
  assert.ok(docs[index - 1].id.localeCompare(docs[index].id) <= 0, "bundle must be sorted by id");
}
for (const doc of docs) {
  assert.equal(typeof doc.id, "string");
  assert.equal(typeof doc.lexicon, "number");
  assert.equal(typeof doc.defs, "object");
}
const duplicateCount = docs.length - new Set(docs.map(({ id }) => id)).size;
const uniqueDocs = [...new Map(docs.map((doc) => [doc.id, doc])).values()];
new Lexicons(uniqueDocs);
console.log(`[ok] loaded and validated ${docs.length} lexicon documents (${duplicateCount} duplicate ids retained from source)`);
