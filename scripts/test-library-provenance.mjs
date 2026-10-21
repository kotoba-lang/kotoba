import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "kotoba-provenance-"));
try {
  fs.cpSync(path.join(repo, "lib"), path.join(temporary, "lib"), { recursive: true });
  fs.mkdirSync(path.join(temporary, "scripts"));
  const checker = path.join(temporary, "scripts/check-libraries.mjs");
  fs.copyFileSync(path.join(repo, "scripts/check-libraries.mjs"), checker);
  for (const name of ["run-library-tests.cljk", "run-library-jvm-tests.cljk", "run-library-async-tests.cljk"]) {
    fs.copyFileSync(path.join(repo, "scripts", name), path.join(temporary, "scripts", name));
  }
  const check = () => spawnSync(process.execPath, [checker], { encoding: "utf8", maxBuffer: 4 * 1024 * 1024 });
  const baseline = check();
  assert.equal(baseline.status, 0, baseline.stderr);
  const mutate = (relative, alter, message) => {
    const file = path.join(temporary, relative);
    const original = fs.readFileSync(file);
    try {
      fs.writeFileSync(file, alter(original));
      const result = check();
      assert.notEqual(result.status, 0, "mutation was accepted");
      assert.match(result.stderr, message);
    } finally { fs.writeFileSync(file, original); }
  };
  const reviews = JSON.parse(fs.readFileSync(path.join(temporary, "lib/branch-reviews.json"), "utf8"));
  const adapted = reviews.reviews.find(review => review["integrated-files"]);
  assert.ok(adapted, "exercise an adapted immutable branch");
  mutate(Object.values(adapted["source-snapshots"])[0],
         bytes => Buffer.concat([bytes, Buffer.from("; drift\n")]), /AssertionError/);
  mutate("lib/kotoba.async/src/kotoba/async.kotoba",
         bytes => Buffer.concat([bytes, Buffer.from("\n; changed facade\n")]), /added source drift/);
  const unexpected = path.join(temporary, "lib/kotoba.async/src/unreviewed.kotoba");
  fs.writeFileSync(unexpected, "(ns unreviewed)\n");
  try {
    const result = check();
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /no origin or explicit addition record/);
  } finally { fs.unlinkSync(unexpected); }

  const output = adapted["integrated-files"].find(file => file.path.includes("/src/"));
  const packageRoot = output.path.split("/").slice(0, 2).join("/");
  const relative = output.path.slice(packageRoot.length + 1);
  const changeFile = path.join(temporary, packageRoot, "local-changes.json");
  const originalChanges = fs.readFileSync(changeFile);
  const sourceFile = path.join(temporary, output.path);
  const originalSource = fs.readFileSync(sourceFile);
  try {
    const changed = Buffer.concat([originalSource, Buffer.from("\n; output drift\n")]);
    fs.writeFileSync(sourceFile, changed);
    const changes = JSON.parse(originalChanges);
    changes.files[relative].sha256 = createHash("sha256").update(changed).digest("hex");
    fs.writeFileSync(changeFile, JSON.stringify(changes));
    const result = check();
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /adapted source drift/,
                 "local-change receipts cannot replace reviewed branch-output bindings");
  } finally {
    fs.writeFileSync(sourceFile, originalSource);
    fs.writeFileSync(changeFile, originalChanges);
  }
  console.log("library provenance: four source/receipt mutation refusals passed");
} finally { fs.rmSync(temporary, { recursive: true, force: true }); }
