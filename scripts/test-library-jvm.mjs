import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const run = (command, args) => {
  const result = spawnSync(command, args, { cwd: repo, stdio: "inherit" });
  assert.equal(result.status, 0, `${command} ${args.join(" ")} failed`);
};
run("clojure", ["-M:library-test"]);
// The imported async .kotoba oracle predates today's reserved take and abort
// export rules. Its original test-only Amu pin is isolated from the CLI graph.
// Passing this oracle does not qualify async against the current CLI compiler.
const classpath = execFileSync("clojure", ["-Spath"], {
  cwd: path.join(repo, "lib/async-test"), encoding: "utf8", maxBuffer: 4 * 1024 * 1024
}).trim().split(path.delimiter).map(entry => path.resolve(repo, "lib/async-test", entry))
  .join(path.delimiter);
run("java", ["-cp", classpath, "clojure.main", "-i", "tools/cljk_loader.cljk",
             "scripts/run-library-async-tests.cljk"]);
