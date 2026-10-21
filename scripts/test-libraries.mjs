import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const libraryProject = path.join(repo, "lib");
const design = process.argv[2] === "--check-design";
assert.ok(design || process.argv.length === 2, "usage: test-libraries.mjs [--check-design ADR.kotoba...]");
let engine = process.env.KBB_ENGINE;
if (!engine) {
  const kbb = fs.realpathSync(execFileSync("which", ["kbb"], { encoding: "utf8" }).trim());
  engine = path.resolve(path.dirname(kbb), "../../org-babashka-nbb/cli.js");
}
assert.ok(fs.existsSync(engine), "set KBB_ENGINE to the installed .cljk-capable SCI engine");

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "kotoba-library-tests-"));
try {
  const bootstrap = path.join(repo, "lib/kotoba.text");
  assert.ok(fs.existsSync(path.join(bootstrap, "src/kotoba/lang/text.cljk")),
            "bundled text bootstrap is missing");

  const blocked = path.join(temporary, "blocked");
  fs.mkdirSync(blocked);
  const marker = path.join(temporary, "forbidden-host-used");
  for (const name of ["java", "javac", "clojure", "clj", "bb"]) {
    fs.writeFileSync(path.join(blocked, name),
      '#!/bin/sh\nprintf "%s\\n" "$0" >> "$KOTOBA_FORBIDDEN_HOST_MARKER"\nexit 97\n', { mode: 0o755 });
  }
  const env = { ...process.env, KBB_ENGINE: engine, KBB_NO_STDLIB: "1", KBB_NO_NPM: "1",
    KOTOBA_FORBIDDEN_HOST_MARKER: marker, PATH: blocked + path.delimiter + process.env.PATH };
  delete env.KBB_CLASSPATH_TAIL;
  const config = path.join(libraryProject, "nbb.edn");
  const resolved = spawnSync(process.execPath,
    [engine, "--config", config, "--classpath", path.join(bootstrap, "src"),
     path.join(repo, "bin/kbb_deps.cljk"), "-Spath", design ? "-M:design" : "-M:test"],
    { cwd: libraryProject, env, encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
  if (resolved.stderr) process.stderr.write(resolved.stderr);
  assert.equal(resolved.status, 0, "native dependency resolution failed");
  assert.ok(!resolved.stderr.includes("NOT on the classpath"), "a declared dependency is missing");
  const classpath = resolved.stdout.trim().split(path.delimiter)
    .map(entry => path.resolve(libraryProject, entry)).join(path.delimiter);
  const result = spawnSync(process.execPath,
    [engine, "--config", config, "--classpath", classpath,
     design ? "scripts/check-library-design.cljk" : "scripts/run-library-tests.cljk",
     ...(design ? process.argv.slice(3) : [])],
    { cwd: repo, env, stdio: "inherit" });
  assert.ok(!fs.existsSync(marker), "a JVM or tools.deps bootstrap was invoked");
  process.exitCode = result.status ?? 1;
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
