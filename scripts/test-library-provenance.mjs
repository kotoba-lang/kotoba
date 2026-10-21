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
  fs.cpSync(path.join(repo, "hermes"), path.join(temporary, "hermes"), { recursive: true });
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
  const worktrees = JSON.parse(fs.readFileSync(path.join(temporary, "lib/worktree-reviews.json"), "utf8"));
  mutate(worktrees.reviews[0]["source-snapshot"],
    bytes => Buffer.concat([bytes, Buffer.from("invalid")]), /AssertionError/);
  mutate("lib/worktree-reviews.json", bytes => {
    const data = JSON.parse(bytes);
    data.reviews[0]["integrated-files"][0].sha256 = "0".repeat(64);
    return JSON.stringify(data);
  }, /reviewed worktree output drift/);
  mutate("lib/worktree-reviews.json", bytes => {
    const data = JSON.parse(bytes); data.reviews.pop();
    return JSON.stringify(data);
  }, /worktree review inventory mismatch/);
  const homes = JSON.parse(fs.readFileSync(path.join(temporary, "lib/profile-homes.json"), "utf8"));
  mutate(homes.profiles[0].files[0].destination,
    bytes => Buffer.concat([bytes, Buffer.from("\n; drift\n")]), /preserved profile source drift/);
  mutate("lib/profile-homes.json", bytes => {
    const data = JSON.parse(bytes); data.profiles[0].files = [];
    return JSON.stringify(data);
  }, /incomplete profile source inventory/);
  const config = homes.profiles[0].files.find(file => file.destination.endsWith("/config.yaml"));
  const configPath = path.join(temporary, config.destination);
  const homesPath = path.join(temporary, "lib/profile-homes.json");
  const oldConfig = fs.readFileSync(configPath);
  const oldHomes = fs.readFileSync(homesPath);
  try {
    const changed = oldConfig.toString("utf8").replace("provider: openrouter", "provider: murakumo");
    assert.notEqual(changed, oldConfig.toString("utf8"));
    fs.writeFileSync(configPath, changed);
    const forged = JSON.parse(oldHomes);
    forged.profiles[0].files.find(file => file.destination === config.destination)["destination-sha256"] =
      createHash("sha256").update(changed).digest("hex");
    fs.writeFileSync(homesPath, JSON.stringify(forged));
    const result = check();
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Hermes profile uses a reserved native inference rail/);
  } finally {
    fs.writeFileSync(configPath, oldConfig); fs.writeFileSync(homesPath, oldHomes);
  }
  mutate("lib/kotoba.lsp/derivations.json", bytes => {
    const data = JSON.parse(bytes);
    data.derivations[0]["licensed-origin"].repository = "kotoba-lang/lsp-position";
    return JSON.stringify(data);
  }, /AssertionError/);
  mutate("lib/kotoba.lsp/derivations.json", bytes => {
    const data = JSON.parse(bytes);
    data.derivations[0]["licensed-origin"]["license-sha256"] = "0".repeat(64);
    return JSON.stringify(data);
  }, /derived input is not the immutable owner input/);
  mutate("lib/kotoba.lsp/derivations.json", bytes => {
    const data = JSON.parse(bytes);
    data.derivations[0]["reviewed-compatibility"]["source-imported"] = true;
    return JSON.stringify(data);
  }, /AssertionError/);
  console.log("library provenance: thirteen source/receipt/rail/derivation mutation refusals passed");
} finally { fs.rmSync(temporary, { recursive: true, force: true }); }
