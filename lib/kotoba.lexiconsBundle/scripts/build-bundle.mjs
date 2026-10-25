#!/usr/bin/env node
/**
 * build-bundle.mjs — Walk 00-contracts/lexicons/**\/*.json and emit
 * 10-protocol/lexicons-bundle/src/lexicons.gen.json as a single array of
 * LexiconDoc objects.
 *
 * Run: pnpm --filter @etzhayyim/lexicons-bundle build
 * or:  node 10-protocol/lexicons-bundle/scripts/build-bundle.mjs
 */
import { readdirSync, readFileSync, writeFileSync, statSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const LEX_DIR = resolve(process.argv[2] ?? process.env.ETZHAYYIM_LEXICONS_DIR ?? "00-contracts/lexicons");
const OUT_FILE = join(HERE, "..", "src", "lexicons.gen.json");

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, acc);
    else if (name.endsWith(".json")) acc.push(full);
  }
  return acc;
}

const files = walk(LEX_DIR);
const docs = [];
let skipped = 0;

for (const f of files) {
  let json;
  try {
    json = JSON.parse(readFileSync(f, "utf8"));
  } catch (err) {
    console.warn(`[skip] ${f}: parse error: ${err.message}`);
    skipped++;
    continue;
  }
  if (typeof json?.lexicon !== "number" || typeof json?.id !== "string" || !json?.defs) {
    console.warn(`[skip] ${f}: not a lexicon doc (missing lexicon/id/defs)`);
    skipped++;
    continue;
  }
  docs.push(json);
}

docs.sort((a, b) => a.id.localeCompare(b.id));
mkdirSync(join(HERE, "..", "src"), { recursive: true });
writeFileSync(OUT_FILE, JSON.stringify(docs));
console.log(`[lexicons-bundle] wrote ${docs.length} docs (skipped ${skipped}) -> ${OUT_FILE}`);
console.log(`[lexicons-bundle] file size: ${(JSON.stringify(docs).length / 1024).toFixed(1)} KiB`);
