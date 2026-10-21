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
const declaredText = fs.readFileSync(path.join(repo, "deps.edn"), "utf8")
  .match(/io\.github\.kotoba-lang\/text\s+\{:git\/sha\s+"([0-9a-f]{40})"/);
assert.ok(declaredText, "bootstrap text must be pinned in deps.edn");
const textCommit = declaredText[1];
let engine = process.env.KBB_ENGINE;
if (!engine) {
  const kbb = fs.realpathSync(execFileSync("which", ["kbb"], { encoding: "utf8" }).trim());
  engine = path.resolve(path.dirname(kbb), "../../org-babashka-nbb/cli.js");
}
assert.ok(fs.existsSync(engine), "set KBB_ENGINE to the installed .cljk-capable SCI engine");

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "kotoba-library-tests-"));
try {
  // Bootstrap the existing native deps resolver from a declared immutable
  // text snapshot, never the working files of a sibling or an implicit
  // workspace classpath. This also avoids nbb's JVM tools.deps adapter.
  const gitlibs = process.env.GITLIBS ?? path.join(os.homedir(), ".gitlibs");
  const candidates = [path.join(gitlibs, "libs/io.github.kotoba-lang/text", textCommit),
    path.resolve(repo, "../text")];
  let textRepo = candidates.find(dir => fs.existsSync(dir) &&
    spawnSync("git", ["-C", dir, "cat-file", "-e", `${textCommit}^{commit}`],
              { stdio: "ignore" }).status === 0);
  if (!textRepo) {
    textRepo = path.join(temporary, "text.git");
    execFileSync("git", ["clone", "--bare", "https://github.com/kotoba-lang/text.git", textRepo],
                 { stdio: "inherit" });
  }
  const bootstrap = path.join(temporary, "bootstrap");
  fs.mkdirSync(bootstrap);
  const archive = execFileSync("git", ["-C", textRepo, "archive", textCommit, "src"],
                               { maxBuffer: 8 * 1024 * 1024 });
  execFileSync("tar", ["-xf", "-", "-C", bootstrap], { input: archive });

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
