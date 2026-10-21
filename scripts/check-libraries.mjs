import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const readJSON = file => JSON.parse(fs.readFileSync(file, "utf8"));
const shaPattern = /^[0-9a-f]{64}$/;
let origins = 0;
let files = 0;
const ids = fs.readdirSync(path.join(repo, "lib"))
  .filter(id => fs.existsSync(path.join(repo, "lib", id, "imports.json"))).sort();
const catalogIDs = [...fs.readFileSync(path.join(repo, "lib/catalog.edn"), "utf8")
  .matchAll(/:id\s+"([^"]+)"/g)].map(match => match[1]).sort();
assert.deepEqual(ids, catalogIDs, "every catalog package must have a checked import inventory");

for (const id of ids) {
  const root = path.join(repo, "lib", id);
  const provenance = readJSON(path.join(root, "imports.json"));
  const changes = readJSON(path.join(root, "local-changes.json"));
  assert.equal(provenance.schema, "kotoba.library-imports.v1");
  assert.equal(changes.schema, "kotoba.library-local-changes.v1");
  const seen = new Map();
  const usedChanges = new Set();
  for (const origin of provenance.imports) {
    assert.match(origin.commit, /^[0-9a-f]{40}$/);
    assert.match(origin.tree, /^[0-9a-f]{40}$/);
    assert.equal(origin.url, `https://github.com/kotoba-lang/${origin.repo}.git`);
    assert.ok(origin.files.some(file => file.source === "LICENSE"), `${origin.repo}: license missing`);
    for (const file of origin.files) {
      assert.match(file.sha256, shaPattern);
      const destination = path.resolve(root, file.path);
      assert.ok(destination.startsWith(root + path.sep), `unconfined import: ${file.path}`);
      assert.ok(fs.lstatSync(destination).isFile(), `not a regular file: ${destination}`);
      const previous = seen.get(file.path);
      assert.ok(!previous || previous === file.sha256, `conflicting source origins: ${file.path}`);
      seen.set(file.path, file.sha256);
      const change = changes.files[file.path];
      if (change) {
        usedChanges.add(file.path);
        assert.equal(change["imported-sha256"], file.sha256);
        assert.ok(change.reason?.trim(), `unexplained local change: ${file.path}`);
        assert.match(change.sha256, shaPattern);
      }
      assert.equal(digest(fs.readFileSync(destination)), change?.sha256 ?? file.sha256,
                   `${id}/${file.path}: source drift needs an explicit local-change record`);
      assert.equal(Boolean(fs.statSync(destination).mode & 0o111), file.mode === "100755",
                   `${id}/${file.path}: executable mode changed`);
      files++;
    }
    origins++;
  }
  assert.deepEqual([...usedChanges].sort(), Object.keys(changes.files).sort(), "unused local-change entry");
  // A deterministic source inventory digest, NOT a fabricated package CID or
  // DefCID. It covers implementation and dependency declarations, not repo HEAD.
  const implementationFiles = ["deps.edn"];
  const collect = directory => {
    if (!fs.existsSync(path.join(root, directory))) return;
    for (const entry of fs.readdirSync(path.join(root, directory), { withFileTypes: true })) {
      const relative = `${directory}/${entry.name}`;
      if (entry.isDirectory()) collect(relative);
      else {
        assert.ok(entry.isFile(), `${id}/${relative}: non-regular source`);
        assert.ok(!/\.(clj|cljs|cljc)$/.test(relative),
                  `${id}/${relative}: imported Clojure-family sources must use .cljk`);
        implementationFiles.push(relative);
      }
    }
  };
  collect("src");
  collect("kotoba");
  const source = implementationFiles.sort().map(file =>
      [file, digest(fs.readFileSync(path.join(root, file)))]);
  console.log(`${id}: ${provenance.imports.length} source origins; source-sha256:${digest(JSON.stringify(source))}`);
}

// Every portable imported test is required AND executed. Preserve the one
// explicitly JVM-only oracle without pretending the SCI host ran it.
const runner = fs.readFileSync(path.join(repo, "scripts/run-library-tests.cljk"), "utf8");
for (const id of ids) {
  const tests = path.join(repo, "lib", id, "test");
  if (!fs.existsSync(tests)) continue;
  const visit = dir => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.name.endsWith("_test.cljk")) {
        const relative = path.relative(tests, file);
        if (id === "kotoba.json" && relative === "json/core_test.cljk") {
          assert.match(fs.readFileSync(path.join(repo, "lib", id, "cljk-origin.edn"), "utf8"),
                       /"test\/json\/core_test\.cljk"\s+"\.clj"/,
                       "the excluded test is no longer declared JVM-only; register it");
          continue;
        }
        const source = fs.readFileSync(file, "utf8");
        const namespace = source.match(/\(ns\s+([^\s()]+)/)?.[1];
        assert.ok(namespace, `${file}: missing test namespace`);
        assert.ok(runner.includes(`[${namespace}]`), `${namespace}: not required`);
        assert.ok(runner.includes(`'${namespace}`), `${namespace}: not executed`);
      }
    }
  };
  visit(tests);
}
console.log(`libraries: ${origins} pinned origins, ${files} imported files, portable test inventory verified`);

// Retirement eligibility is bound to reviewed default-source bytes, not just
// an old import commit. The live archive operation must still recheck GitHub
// and local WIP; this offline gate does not perform repository mutations.
const migrations = readJSON(path.join(repo, "lib/repository-migrations.json"));
assert.equal(migrations.schema, "kotoba.library-repository-migrations.v1");
assert.equal(migrations.repositories.length, origins);
const importedRepos = ids.flatMap(id => readJSON(path.join(repo, "lib", id, "imports.json"))
  .imports.map(origin => `kotoba-lang/${origin.repo}`)).sort();
assert.deepEqual(migrations.repositories.map(row => row.repo).sort(), importedRepos);
for (const row of migrations.repositories) {
  assert.match(row["reviewed-default-commit"], /^[0-9a-f]{40}$/);
  assert.ok(ids.some(id => row.destination === `lib/${id}`));
  assert.ok(["hold", "archive-after-main-verification"].includes(row.disposition));
  assert.equal(row.disposition === "hold", row.holds.length > 0);
  if (row.disposition === "hold") continue;
  assert.ok(row["current-source-files"].length > 0);
  const root = path.join(repo, row.destination);
  const changes = readJSON(path.join(root, "local-changes.json")).files;
  for (const file of row["current-source-files"]) {
    const destination = path.resolve(root, file.path);
    assert.ok(destination.startsWith(root + path.sep));
    const actual = digest(fs.readFileSync(destination));
    const approved = changes[file.path];
    assert.ok(actual === file.sha256 ||
      (approved?.["imported-sha256"] === file.sha256 && approved.sha256 === actual),
      `${row.repo}/${file.source}: reviewed default source is no longer integrated`);
    assert.equal(Boolean(fs.statSync(destination).mode & 0o111), file.mode === "100755");
  }
}
console.log(`repository migrations: ${migrations.repositories.filter(row => row.disposition !== "hold").length} eligible; held repositories retained`);
