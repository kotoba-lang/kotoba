import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function git(args, cwd) {
  const result = spawnSync("git", args, { cwd, encoding: "utf8" });
  if (result.status !== 0) throw new Error(`evaluation workspace git command failed: ${args[0]}`);
  return result.stdout.trim();
}

export function prepareEvaluationWorkspace(scriptUrl) {
  const suiteRoot = path.resolve(path.dirname(fileURLToPath(scriptUrl)), "..");
  const workspaceRoot = process.env.KOTOBA_EVAL_WORKDIR
    ? path.resolve(process.env.KOTOBA_EVAL_WORKDIR)
    : null;
  if (!workspaceRoot) {
    throw new Error("set KOTOBA_EVAL_WORKDIR to a fresh worktree at eval/v1/manifest.json baseline_revision");
  }

  const manifest = JSON.parse(fs.readFileSync(path.join(suiteRoot, "eval/v1/manifest.json"), "utf8"));
  const baselineRevision = manifest.baseline_revision;
  if (typeof baselineRevision !== "string" || !/^[a-f0-9]{40}$/.test(baselineRevision)) {
    throw new Error("eval/v1/manifest.json must pin a 40-character baseline_revision");
  }
  const sourceRevision = git(["rev-parse", "HEAD"], workspaceRoot);
  if (sourceRevision !== baselineRevision) {
    throw new Error(`evaluation worktree must be at pinned baseline ${baselineRevision}`);
  }
  if (git(["status", "--porcelain", "--untracked-files=all"], workspaceRoot)) {
    throw new Error("KOTOBA_EVAL_WORKDIR must be clean before benchmark fixtures are installed");
  }

  const sourceFile = path.join(workspaceRoot, "src/agent/turn_loop.kotoba");
  const source = fs.readFileSync(sourceFile, "utf8");
  if (/\(defn\s+run-budget-remaining\b/.test(source)) {
    throw new Error("evaluation baseline already contains the requested export");
  }

  const taskPath = path.join(suiteRoot, manifest.task_file);
  const skillPath = path.join(suiteRoot, ".agents/skills/kotoba-coding/SKILL.md");
  const verifierPath = path.join(suiteRoot, manifest.acceptance.verifier);
  const evaluationReadmePath = path.join(suiteRoot, "eval/v1/README.md");
  const evaluationReadme = fs.readFileSync(evaluationReadmePath, "utf8");
  const resultSection = evaluationReadme.indexOf("## Pilot results (");
  const readingSection = resultSection < 0 ? -1 : evaluationReadme.indexOf("## Reading results", resultSection);
  const agentReadme = resultSection >= 0 && readingSection >= 0
    ? `${evaluationReadme.slice(0, resultSection)}${evaluationReadme.slice(readingSection)}`
    : evaluationReadme;

  const fixtures = [
    [".agents/skills/kotoba-coding/SKILL.md", fs.readFileSync(skillPath)],
    ["eval/v1/README.md", Buffer.from(agentReadme)],
    ["eval/v1/manifest.json", fs.readFileSync(path.join(suiteRoot, "eval/v1/manifest.json"))],
    ["eval/v1/result.schema.json", fs.readFileSync(path.join(suiteRoot, "eval/v1/result.schema.json"))],
    [manifest.task_file, fs.readFileSync(taskPath)],
    ["scripts/score-kotoba-eval.mjs", fs.readFileSync(path.join(suiteRoot, "scripts/score-kotoba-eval.mjs"))],
    [manifest.acceptance.verifier, fs.readFileSync(verifierPath)],
  ];
  for (const [relativePath, contents] of fixtures) {
    const destination = path.join(workspaceRoot, relativePath);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.writeFileSync(destination, contents);
  }

  const task = fs.readFileSync(path.join(workspaceRoot, manifest.task_file), "utf8");
  const skill = fs.readFileSync(path.join(workspaceRoot, ".agents/skills/kotoba-coding/SKILL.md"), "utf8");
  return {
    suiteRoot,
    workspaceRoot,
    sourceRevision,
    baselineRevision,
    manifest,
    task,
    skill,
    taskSha256: sha256(task),
    skillSha256: sha256(skill),
    verifierSha256: sha256(fs.readFileSync(verifierPath)),
    evaluationReadmeSha256: sha256(agentReadme),
  };
}
