import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const bundleUrl = new URL("../src/lexicons.gen.json", import.meta.url);
const original = readFileSync(bundleUrl, "utf8");
const docs = JSON.parse(original);
const input = mkdtempSync(join(tmpdir(), "lexicons-bundle-build-"));
try {
  docs.forEach((doc, index) => writeFileSync(join(input, `${index.toString().padStart(5, "0")}.json`), JSON.stringify(doc)));
  const result = spawnSync(process.execPath, [new URL("./build-bundle.mjs", import.meta.url).pathname, input], { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
  const rebuilt = JSON.parse(readFileSync(bundleUrl, "utf8"));
  if (JSON.stringify(rebuilt) !== JSON.stringify(docs)) throw new Error("rebuilt bundle differs from the extracted source artifact");
  console.log(`[ok] deterministic rebuild retained ${docs.length} documents in canonical order`);
} finally {
  writeFileSync(bundleUrl, original);
  rmSync(input, { recursive: true, force: true });
}
