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
const hostNamespaces = new Map();

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
  for (const [file, addition] of Object.entries(changes.added ?? {})) {
    const destination = path.resolve(root, file);
    assert.ok(destination.startsWith(root + path.sep), `unconfined addition: ${file}`);
    assert.ok(!seen.has(file), `imported source mislabeled as an addition: ${file}`);
    assert.ok(addition.reason?.trim(), `unexplained addition: ${file}`);
    assert.match(addition.sha256, shaPattern);
    assert.ok(fs.lstatSync(destination).isFile(), `non-regular addition: ${file}`);
    assert.equal(digest(fs.readFileSync(destination)), addition.sha256, `added source drift: ${file}`);
  }
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
        assert.ok(seen.has(relative) || changes.added?.[relative],
                  `${id}/${relative}: source has no origin or explicit addition record`);
        if (relative.startsWith("src/") && relative.endsWith(".cljk")) {
          const namespace = fs.readFileSync(path.join(root, relative), "utf8")
            .match(/\(ns\s+([^\s()]+)/)?.[1];
          if (namespace) {
            assert.ok(!hostNamespaces.has(namespace),
                      `${namespace}: duplicate active host source in ${hostNamespaces.get(namespace)} and ${id}/${relative}`);
            hostNamespaces.set(namespace, `${id}/${relative}`);
          }
        }
      }
    }
  };
  collect("src");
  collect("kotoba");
  const source = implementationFiles.sort().map(file =>
      [file, digest(fs.readFileSync(path.join(root, file)))]);
  console.log(`${id}: ${provenance.imports.length} source origins; source-sha256:${digest(JSON.stringify(source))}`);
}

// All imported suites have an explicit host. JVM-only origins are executed
// by run-library-jvm-tests; SCI executes every other registered suite.
const suites = readJSON(path.join(repo, "lib/test-suites.json"));
assert.equal(suites.schema, "kotoba.library-test-suites.v1");
const jvmRunner = ["run-library-jvm-tests.cljk", "run-library-async-tests.cljk"]
  .map(file => fs.readFileSync(path.join(repo, "scripts", file), "utf8")).join("\n");
const runner = fs.readFileSync(path.join(repo, "scripts/run-library-tests.cljk"), "utf8");
const registered = new Set();
for (const id of ids) {
  const tests = path.join(repo, "lib", id, "test");
  if (!fs.existsSync(tests)) continue;
  const visit = dir => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.name.endsWith("_test.cljk")) {
        const relative = path.relative(tests, file);
        const fullPath = path.relative(repo, file);
        const jvm = suites["jvm-only"].find(row => row.path === fullPath);
        const portable = suites.portable.find(row => row.path === fullPath);
        assert.ok(Boolean(jvm) !== Boolean(portable), `${fullPath}: choose exactly one test host`);
        registered.add(fullPath);
        if (jvm) {
          const origins = fs.readFileSync(path.join(repo, "lib", id, "cljk-origin.edn"), "utf8");
          assert.ok(origins.includes(`"test/${relative}" ".clj"`), `${fullPath}: no JVM-only origin`);
          assert.ok(jvmRunner.includes(`[${jvm.namespace}]`) && jvmRunner.includes(`'${jvm.namespace}`));
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
assert.deepEqual([...registered].sort(), [...suites.portable, ...suites["jvm-only"]].map(row => row.path).sort(),
                 "test registry contains a missing or duplicate suite");
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

// A reviewed branch is bound to exact source bytes and its retained tip.
// A prose decision cannot silently authorize different branch contents.
const reviews = readJSON(path.join(repo, "lib/branch-reviews.json"));
assert.equal(reviews.schema, "kotoba.library-branch-reviews.v1");
for (const review of reviews.reviews) {
  assert.match(review.commit, /^[0-9a-f]{40}$/);
  assert.ok(["integrate", "hold"].includes(review.decision));
  assert.ok(review.reason?.trim());
  if (review.decision !== "integrate") continue;
  const migration = migrations.repositories.find(row => row.repo === review.repo);
  assert.ok(migration, `reviewed branch without source migration: ${review.repo}`);
  assert.ok(migration["reviewed-branches"].some(row => row.commit === review.commit && row.branch === review.branch));
  if (review["integrated-files"]) {
    // Adapted ports retain the exact reviewed input beside separately bound
    // output bytes. Neither a prose decision nor an output hash alone proves
    // which immutable branch was reviewed.
    for (const file of review.files) {
      const snapshot = review["source-snapshots"]?.[file];
      assert.ok(snapshot?.startsWith(`${migration.destination}/provenance/branches/${review.commit}/`));
      const source = path.resolve(repo, snapshot);
      assert.ok(source.startsWith(repo + path.sep));
      assert.ok(fs.lstatSync(source).isFile());
      let bytes = fs.readFileSync(source);
      if (review["source-snapshot-encoding"] === "base64") {
        const encoded = bytes.toString("utf8").trimEnd();
        bytes = Buffer.from(encoded, "base64");
        assert.equal(bytes.toString("base64"), encoded, "noncanonical branch snapshot");
      } else {
        assert.equal(review["source-snapshot-encoding"], undefined);
      }
      assert.equal(digest(bytes), review["source-sha256"][file]);
      assert.ok(review["integrated-files"].some(row => row.sources.includes(file)),
                `${review.repo}/${file}: reviewed intent has no integrated destination`);
    }
    for (const file of review["integrated-files"]) {
      const destination = path.resolve(repo, file.path);
      assert.ok(destination.startsWith(repo + path.sep));
      assert.ok(file.reason?.trim() && file.sources.length > 0);
      assert.ok(file.sources.every(source => review.files.includes(source)));
      assert.match(file.sha256, shaPattern);
      assert.ok(fs.lstatSync(destination).isFile());
      assert.equal(digest(fs.readFileSync(destination)), file.sha256,
                   `${review.repo}@${review.commit}: adapted source drift`);
    }
    continue;
  }
  for (const file of review.files) {
    const source = path.resolve(repo, migration.destination, file);
    assert.ok(source.startsWith(path.resolve(repo, migration.destination) + path.sep));
    assert.equal(digest(fs.readFileSync(source)), review["source-sha256"][file],
                 `${review.repo}@${review.commit}: reviewed source changed`);
  }
}
