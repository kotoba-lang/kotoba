#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { randomUUID } from "node:crypto";
import os from "node:os";
import { prepareEvaluationWorkspace } from "./eval-workspace.mjs";

const workspace = prepareEvaluationWorkspace(import.meta.url);
const { suiteRoot, workspaceRoot, task } = workspace;
const cwd = workspaceRoot;
const taskPath = path.join(workspaceRoot, workspace.manifest.task_file);
const metricsPath = process.argv[2] ? path.resolve(suiteRoot, process.argv[2]) : null;
const model = process.env.KOTOBA_EVAL_CODEX_MODEL || "gpt-6.1-sol";
const timeBudgetMs = 300_000;
if (!metricsPath) {
  console.error("usage: KOTOBA_EVAL_CODEX_MODEL=MODEL node scripts/run-codex-kotoba-eval.mjs METRICS.json");
  process.exit(2);
}

const versionResult = spawnSync("codex", ["--version"], { encoding: "utf8" });
if (versionResult.status !== 0) throw new Error(`codex --version failed: ${versionResult.stderr}`);
const codexVersion = versionResult.stdout.trim().split(/\s+/).at(-1);
const sourceRevisionResult = spawnSync("git", ["rev-parse", "HEAD"], { cwd, encoding: "utf8" });
if (sourceRevisionResult.status !== 0) throw new Error("could not identify the benchmark source revision");
const amuRoot = process.env.AMU_ROOT;
if (!amuRoot) throw new Error("set AMU_ROOT to the fixed AMU compiler checkout used for this benchmark");
const kbbHome = amuRoot;
const kbbEngine = path.resolve(amuRoot, "..", "org-babashka-nbb", "cli.js");
if (!fs.existsSync(kbbEngine)) throw new Error("the fixed nbb engine is missing next to AMU_ROOT");
const compilerRevisionResult = spawnSync("git", ["-C", amuRoot, "rev-parse", "HEAD"], { encoding: "utf8" });
if (compilerRevisionResult.status !== 0) throw new Error("could not identify the AMU compiler revision");
const stage = (name) => {
  const marker = `## ${name}\n`;
  const start = task.indexOf(marker);
  if (start < 0) throw new Error(`missing ${name} in ${taskPath}`);
  return task.slice(start + marker.length).split(/\n## /, 1)[0].trim();
};

function observeEvents(args, prompt, timeoutMs) {
  return new Promise((resolve) => {
    const child = spawn("codex", args, {
      cwd,
      env: { ...process.env, KBB_HOME: kbbHome, KBB_ENGINE: kbbEngine },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let buffer = "";
    const observation = {
      threadIds: new Set(),
      rootThreadId: null,
      inputTokens: 0,
      outputTokens: 0,
      usageEvents: 0,
      turnCount: 0,
      commandCalls: 0,
      completedTurns: 0,
      failedTurns: 0,
    };
    let timedOut = false;
    let spawnFailed = false;
    let killTimer = null;
    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      killTimer = setTimeout(() => child.kill("SIGKILL"), 2_000);
    }, timeoutMs);
    const consumeLine = (line) => {
      if (!line.trim()) return;
      let event;
      try { event = JSON.parse(line); } catch { return; }
      const threadId = event.thread_id || event.session_id;
      if (typeof threadId === "string") {
        observation.threadIds.add(threadId);
        if (event.type === "thread.started" && observation.rootThreadId === null) {
          observation.rootThreadId = threadId;
        }
      }
      if (event.type === "turn.completed" && event.usage &&
          Number.isSafeInteger(event.usage.input_tokens) &&
          Number.isSafeInteger(event.usage.output_tokens)) {
        observation.inputTokens += event.usage.input_tokens;
        observation.outputTokens += event.usage.output_tokens;
        observation.usageEvents += 1;
      }
      if (event.type === "turn.completed") observation.completedTurns += 1;
      if (event.type === "turn.started") observation.turnCount += 1;
      if (event.type === "item.completed" && event.item?.type === "command_execution") {
        observation.commandCalls += 1;
      }
      if (event.type === "turn.failed") observation.failedTurns += 1;
    };
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      buffer += chunk;
      let newline;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        consumeLine(line);
      }
    });
    // Discard stderr; CLI diagnostics can include session identifiers or request content.
    child.stderr.on("data", () => {});
    child.on("error", () => { spawnFailed = true; });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (killTimer) clearTimeout(killTimer);
      if (buffer.trim()) consumeLine(buffer);
      resolve({ code, observation, timedOut, spawnFailed });
    });
    child.stdin.end(prompt);
  });
}

const started = performance.now();
const deadline = started + timeBudgetMs;
const stageResults = [];
let runStatus = "completed";
let failureStage = null;
function remainingMs() {
  return Math.max(1, deadline - performance.now());
}
function stageSessionId(result) {
  return result?.observation.rootThreadId || [...(result?.observation.threadIds || [])][0] || null;
}
const first = await observeEvents(
  ["exec", "--model", model, "--json", "--sandbox", "workspace-write"],
  `${stage("Stage 1")}\n\nUse the kotoba-coding project skill and make the requested source change.`,
  remainingMs(),
);
stageResults.push(first);
let firstThreadId = stageSessionId(first);
let second = null;
if (first.timedOut) {
  runStatus = "timed_out";
  failureStage = "codex_stage_1";
} else if (first.spawnFailed || first.code !== 0 || first.observation.failedTurns > 0 || first.observation.completedTurns === 0) {
  runStatus = firstThreadId ? "agent_incomplete" : "infrastructure_failure";
  failureStage = "codex_stage_1";
} else if (!firstThreadId) {
  runStatus = "telemetry_incomplete";
  failureStage = "codex_stage_1_session_id_missing";
} else if (performance.now() >= deadline) {
  runStatus = "timed_out";
  failureStage = "before_codex_stage_2";
} else {
  second = await observeEvents(
    ["exec", "resume", "--model", model, "--json", firstThreadId, "-"],
    `${stage("Stage 2 (resume the same agent session)")}\n\nContinue the same task and report only the requested command outcomes.`,
    remainingMs(),
  );
  stageResults.push(second);
  if (second.timedOut) {
    runStatus = "timed_out";
    failureStage = "codex_stage_2";
  } else if (second.spawnFailed || second.code !== 0 || second.observation.failedTurns > 0 || second.observation.completedTurns === 0) {
    runStatus = stageSessionId(second) ? "agent_incomplete" : "infrastructure_failure";
    failureStage = "codex_stage_2";
  }
}

const secondThreadId = stageSessionId(second);
const sameSessionResume = secondThreadId ? secondThreadId === firstThreadId : null;
const usageComplete = stageResults.length === 2 && stageResults.every((result) => result.observation.usageEvents > 0);
if (runStatus === "completed" && (!secondThreadId || !usageComplete)) {
  runStatus = "telemetry_incomplete";
  failureStage = "codex_telemetry";
}
const allThreadIds = new Set(stageResults.flatMap((result) => [...result.observation.threadIds]));
const sessionCount = allThreadIds.size || null;
const metrics = {
  schema_version: "kotoba.eval.metrics.v1",
  run_id: randomUUID(),
  agent: { name: "Codex CLI", version: codexVersion, model },
  environment: {
    source_revision: sourceRevisionResult.stdout.trim(),
    baseline_revision: workspace.baselineRevision,
    compiler_revision: compilerRevisionResult.stdout.trim(),
    task_sha256: workspace.taskSha256,
    skill_sha256: workspace.skillSha256,
    verifier_sha256: workspace.verifierSha256,
    evaluation_readme_sha256: workspace.evaluationReadmeSha256,
    host_class: `${process.platform}-${process.arch}`,
    os: `${os.type()} ${os.release()}`,
    arch: process.arch,
    node: process.version,
  },
  metrics: {
    elapsed_ms: Math.round(performance.now() - started),
    input_tokens: usageComplete ? first.observation.inputTokens + second.observation.inputTokens : null,
    output_tokens: usageComplete ? first.observation.outputTokens + second.observation.outputTokens : null,
    session_count: sessionCount,
    same_session_resume: sameSessionResume,
    turn_count: stageResults.reduce((sum, result) => sum + result.observation.turnCount, 0),
    shell_command_calls: stageResults.reduce((sum, result) => sum + result.observation.commandCalls, 0),
    api_calls: null,
    retry_count: 0,
    infrastructure_failures: stageResults.filter((result) => result.spawnFailed ||
      (!result.timedOut && result.code !== 0 && result.observation.threadIds.size === 0)).length,
    preflight_failures: Number.isSafeInteger(Number(process.env.KOTOBA_EVAL_PREFLIGHT_FAILURES)) &&
      Number(process.env.KOTOBA_EVAL_PREFLIGHT_FAILURES) >= 0
      ? Number(process.env.KOTOBA_EVAL_PREFLIGHT_FAILURES)
      : 0,
    telemetry_source: "codex-jsonl",
  },
  run_status: runStatus,
  failure_stage: failureStage,
};
fs.mkdirSync(path.dirname(path.resolve(metricsPath)), { recursive: true });
fs.writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, { mode: 0o600 });
console.log(JSON.stringify(metrics, null, 2));
if (runStatus !== "completed") process.exitCode = 1;
