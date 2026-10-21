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

for (const id of ["kotoba.coll", "kotoba.spec", "kotoba.json"]) {
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
for (const id of ["kotoba.coll", "kotoba.spec", "kotoba.json"]) {
  const tests = path.join(repo, "lib", id, "test");
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
