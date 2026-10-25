#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { performance } from "node:perf_hooks";
import { prepareEvaluationWorkspace } from "./eval-workspace.mjs";

const workspace = prepareEvaluationWorkspace(import.meta.url);
const { suiteRoot, workspaceRoot, task } = workspace;
const cwd = workspaceRoot;
const taskPath = path.join(workspaceRoot, workspace.manifest.task_file);
const metricsPath = process.argv[2] ? path.resolve(suiteRoot, process.argv[2]) : null;
const provider = process.env.KOTOBA_EVAL_HERMES_PROVIDER || "openrouter";
const model = process.env.KOTOBA_EVAL_HERMES_MODEL || "xiaomi/mimo-v2.6-pro";
const timeBudgetMs = 300_000;

if (!metricsPath) {
  console.error("usage: node scripts/run-hermes-kotoba-eval.mjs METRICS.json");
  process.exit(2);
}

const versionResult = spawnSync("hermes", ["--version"], { encoding: "utf8" });
if (versionResult.status !== 0) throw new Error("hermes --version failed before the benchmark started");
const versionLines = versionResult.stdout.trim().split(/\r?\n/);
const version = versionLines[0]?.match(/Hermes Agent v([^ ]+)/)?.[1];
const python = versionLines.find((line) => line.startsWith("Python: "))?.slice("Python: ".length);
if (!version) throw new Error("could not identify Hermes CLI version");

const amuRoot = process.env.AMU_ROOT;
if (!amuRoot) throw new Error("set AMU_ROOT to the fixed AMU compiler checkout used for this benchmark");
const compilerPath = path.resolve(amuRoot, "bin", "kotoba");
const kbbEngine = path.resolve(amuRoot, "..", "org-babashka-nbb", "cli.js");
if (!fs.existsSync(compilerPath) || !fs.existsSync(kbbEngine)) {
  throw new Error("the fixed AMU compiler or nbb engine is missing");
}

const gitRevision = (args, options = {}) => {
  const result = spawnSync("git", args, { encoding: "utf8", ...options });
  if (result.status !== 0) throw new Error("could not identify a benchmark source revision");
  return result.stdout.trim();
};
const sourceRevision = gitRevision(["rev-parse", "HEAD"], { cwd });
const compilerRevision = gitRevision(["-C", amuRoot, "rev-parse", "HEAD"]);

function stage(name) {
  const marker = `## ${name}\n`;
  const start = task.indexOf(marker);
  if (start < 0) throw new Error(`missing ${name} in ${taskPath}`);
  return task.slice(start + marker.length).split(/\n## /, 1)[0].trim();
}

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "jun-276-hermes-eval-"));
process.once("exit", () => fs.rmSync(tempDir, { recursive: true, force: true }));
const started = performance.now();
const deadline = started + timeBudgetMs;
const stageResults = [];
let failureStage = null;
let runStatus = "completed";

function normalizeUsage(report) {
  if (!report || typeof report !== "object") return null;
  const auxiliary = report.auxiliary && typeof report.auxiliary === "object" ? report.auxiliary : {};
  const total = report.total_including_auxiliary && typeof report.total_including_auxiliary === "object"
    ? report.total_including_auxiliary
    : {};
  const input = report.input_tokens;
  const output = report.output_tokens;
  const auxiliaryInput = auxiliary.input_tokens || 0;
  const auxiliaryOutput = auxiliary.output_tokens || 0;
  return {
    input_tokens: Number.isSafeInteger(input) && Number.isSafeInteger(auxiliaryInput)
      ? input + auxiliaryInput
      : null,
    output_tokens: Number.isSafeInteger(output) && Number.isSafeInteger(auxiliaryOutput)
      ? output + auxiliaryOutput
      : null,
    api_calls: Number.isSafeInteger(total.api_calls) ? total.api_calls : report.api_calls,
    completed: report.completed === true && report.failed !== true,
    session_id: typeof report.session_id === "string" ? report.session_id : null,
  };
}

function runStage(name, prompt, resumeSessionId) {
  return new Promise((resolve) => {
    const usagePath = path.join(tempDir, `${name}.json`);
    const remainingMs = Math.max(1, deadline - performance.now());
    const runBudgetSeconds = Math.max(1, Math.floor(remainingMs / 1000));
    const args = [
      "--usage-file", usagePath,
      "chat", "--query-file", "-", "--format", "stream-json",
      "--provider", provider, "--model", model,
      "--skills", "kotoba-coding", "--toolsets", "terminal,skills",
      "--ignore-rules",
      "--max-turns", "500", "--run-budget", String(runBudgetSeconds),
    ];
    if (resumeSessionId) args.push("--resume", resumeSessionId);

    const child = spawn("hermes", args, {
      cwd,
      env: { ...process.env, KBB_HOME: amuRoot, KBB_ENGINE: kbbEngine },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let buffer = "";
    let resultEvent = null;
    let streamSessionId = null;
    let shellCommandCalls = 0;
    let turnCount = 0;
    let timedOut = false;
    let spawnFailed = false;
    let killTimer = null;

    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      killTimer = setTimeout(() => child.kill("SIGKILL"), 2_000);
    }, remainingMs);

    const consumeLine = (line) => {
      if (!line.trim()) return;
      let event;
      try { event = JSON.parse(line); } catch { return; }
      if (event.type === "system" && typeof event.session_id === "string") {
        streamSessionId = event.session_id;
      }
      if (event.type === "tool_use") {
        const tool = String(event.name || "").toLowerCase();
        if (/terminal|command|shell/.test(tool)) shellCommandCalls += 1;
      }
      if (event.type === "result") {
        resultEvent = event;
        if (typeof event.session_id === "string") streamSessionId = event.session_id;
        turnCount += 1;
      }
    };

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      buffer += chunk;
      let newline;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        consumeLine(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
      }
    });
    // Consume diagnostics without retaining stderr, which may contain session identifiers.
    child.stderr.on("data", () => {});
    child.on("error", () => { spawnFailed = true; });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (killTimer) clearTimeout(killTimer);
      if (buffer.trim()) consumeLine(buffer);
      let usage = null;
      try { usage = normalizeUsage(JSON.parse(fs.readFileSync(usagePath, "utf8"))); } catch {}
      fs.rmSync(usagePath, { force: true });
      resolve({
        code,
        name,
        resultExitCode: Number.isInteger(resultEvent?.exit_code) ? resultEvent.exit_code : null,
        sessionId: usage?.session_id || streamSessionId,
        usage,
        shellCommandCalls,
        turnCount,
        timedOut,
        spawnFailed,
      });
    });
    child.stdin.end(prompt);
  });
}

const prompt1 = `${stage("Stage 1")}\n\nUse the kotoba-coding project skill and make the requested source change.`;
const first = await runStage("stage-1", prompt1, null);
stageResults.push(first);
if (first.timedOut) {
  runStatus = "timed_out";
  failureStage = "hermes_stage_1";
} else if (first.spawnFailed || first.code !== 0 || first.resultExitCode !== 0 || first.usage?.completed !== true) {
  runStatus = first.sessionId ? "agent_incomplete" : "infrastructure_failure";
  failureStage = "hermes_stage_1";
} else if (!first.sessionId) {
  runStatus = "telemetry_incomplete";
  failureStage = "hermes_stage_1_session_id_missing";
} else {
  const remaining = deadline - performance.now();
  if (remaining <= 0) {
    runStatus = "timed_out";
    failureStage = "before_hermes_stage_2";
  } else {
    const prompt2 = `${stage("Stage 2 (resume the same agent session)")}\n\nContinue the same task and report only the requested command outcomes.`;
    const second = await runStage("stage-2", prompt2, first.sessionId);
    stageResults.push(second);
    if (second.timedOut) {
      runStatus = "timed_out";
      failureStage = "hermes_stage_2";
    } else if (second.spawnFailed || second.code !== 0 || second.resultExitCode !== 0 || second.usage?.completed !== true) {
      runStatus = second.sessionId ? "agent_incomplete" : "infrastructure_failure";
      failureStage = "hermes_stage_2";
    }
  }
}

const usageAvailable = stageResults.every((result) =>
  Number.isSafeInteger(result.usage?.input_tokens) && Number.isSafeInteger(result.usage?.output_tokens));
const sessionIds = stageResults.map((result) => result.sessionId).filter(Boolean);
const secondSessionId = stageResults[1]?.sessionId || null;
const sameSessionResume = secondSessionId === null ? null : secondSessionId === sessionIds[0];
const metrics = {
  schema_version: "kotoba.eval.metrics.v1",
  run_id: randomUUID(),
  run_status: runStatus,
  failure_stage: failureStage,
  agent: { name: "Hermes Agent CLI", version, model, provider },
  environment: {
    source_revision: sourceRevision,
    baseline_revision: workspace.baselineRevision,
    compiler_revision: compilerRevision,
    task_sha256: workspace.taskSha256,
    skill_sha256: workspace.skillSha256,
    verifier_sha256: workspace.verifierSha256,
    evaluation_readme_sha256: workspace.evaluationReadmeSha256,
    host_class: `${process.platform}-${process.arch}`,
    os: `${os.type()} ${os.release()}`,
    arch: process.arch,
    ...(python ? { python } : {}),
  },
  metrics: {
    elapsed_ms: Math.round(performance.now() - started),
    input_tokens: usageAvailable ? stageResults.reduce((sum, result) => sum + result.usage.input_tokens, 0) : null,
    output_tokens: usageAvailable ? stageResults.reduce((sum, result) => sum + result.usage.output_tokens, 0) : null,
    session_count: sessionIds.length === 0 ? null : (sameSessionResume === true ? 1 : sessionIds.length),
    same_session_resume: sameSessionResume,
    turn_count: stageResults.reduce((sum, result) => sum + result.turnCount, 0),
    shell_command_calls: stageResults.reduce((sum, result) => sum + result.shellCommandCalls, 0),
    api_calls: stageResults.every((result) => Number.isSafeInteger(result.usage?.api_calls))
      ? stageResults.reduce((sum, result) => sum + result.usage.api_calls, 0)
      : null,
    retry_count: 0,
    infrastructure_failures: stageResults.filter((result) => result.spawnFailed || !result.sessionId).length,
    preflight_failures: 0,
    telemetry_source: "hermes-usage-file+stream-json",
  },
};

fs.mkdirSync(path.dirname(path.resolve(metricsPath)), { recursive: true });
fs.writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, { mode: 0o600 });
fs.rmSync(tempDir, { recursive: true, force: true });
console.log(JSON.stringify(metrics, null, 2));
if (runStatus !== "completed") process.exitCode = 1;
