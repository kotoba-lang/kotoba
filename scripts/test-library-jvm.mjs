import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const run = (command, args) => {
  const result = spawnSync(command, args, { cwd: repo, stdio: "inherit" });
  assert.equal(result.status, 0, `${command} ${args.join(" ")} failed`);
};
run("clojure", ["-M:library-test"]);
// Async now runs in the same immutable compiler graph as the launcher. Actual
// selfhost compilation/execution is separately required by the native CI job.
