#!/usr/bin/env node

import fs from "node:fs";

const [input] = process.argv.slice(2);
if (!input) {
  console.error("usage: node scripts/score-kotoba-eval.mjs RESULT.json");
  process.exit(2);
}

const result = JSON.parse(fs.readFileSync(input, "utf8"));
const fail = (message) => {
  console.error(`invalid evaluation result: ${message}`);
  process.exit(2);
};
const isNonnegativeInteger = (value) => Number.isSafeInteger(value) && value >= 0;

if (result.schema_version !== "kotoba.eval.result.v1") fail("unsupported schema_version");
if (result.suite !== "kotoba-agent-code-v1" || result.task !== "turn-loop-remaining-budget") {
  fail("suite or task does not match eval/v1");
}
if (result.run_status !== undefined &&
    !["completed", "agent_incomplete", "infrastructure_failure", "timed_out", "telemetry_incomplete"].includes(result.run_status)) {
  fail("unsupported run_status");
}
if (!result.verification || !result.metrics || !result.agent || !result.environment) {
  fail("missing verification, metrics, agent, or environment");
}
for (const key of ["name", "version", "model"]) {
  if (typeof result.agent[key] !== "string" || !result.agent[key]) fail(`agent.${key} is required`);
}
for (const key of ["source_revision", "compiler_revision", "host_class", "os", "arch"]) {
  if (typeof result.environment[key] !== "string" || !result.environment[key]) fail(`environment.${key} is required`);
}
for (const key of ["task_sha256", "skill_sha256", "verifier_sha256", "evaluation_readme_sha256"]) {
  if (result.environment[key] === undefined && ["verifier_sha256", "evaluation_readme_sha256"].includes(key)) continue;
  if (typeof result.environment[key] !== "string" || !/^[a-f0-9]{64}$/.test(result.environment[key])) {
    fail(`environment.${key} must be a SHA-256 digest`);
  }
}
if (result.environment.baseline_revision !== undefined &&
    (typeof result.environment.baseline_revision !== "string" || !/^[a-f0-9]{40}$/.test(result.environment.baseline_revision))) {
  fail("environment.baseline_revision must be a pinned Git revision");
}
const forbiddenKeys = new Set(["transcript", "prompt", "response", "session_id", "patch", "source_dump", "credentials"]);
const rejectPrivatePayload = (value) => {
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    if (forbiddenKeys.has(key.toLowerCase())) fail(`result must not contain ${key}`);
    rejectPrivatePayload(child);
  }
};
rejectPrivatePayload(result);

if (result.run_status !== undefined && result.run_status !== "completed") {
  process.stdout.write(`${JSON.stringify({
    correctness_gate: null,
    reward: null,
    status: result.run_status,
    failure_stage: result.failure_stage ?? null,
    note: "Incomplete or infrastructure-failed runs are reported but not scored.",
  }, null, 2)}\n`);
  process.exit(0);
}

const v = result.verification;
if (typeof v.syntax_pass !== "boolean" || typeof v.compile_pass !== "boolean" ||
    typeof v.no_forbidden_forms !== "boolean") fail("verification gates must be booleans");
if (!isNonnegativeInteger(v.acceptance_passed) || !Number.isSafeInteger(v.acceptance_total) ||
    v.acceptance_total < 1 || v.acceptance_passed > v.acceptance_total) {
  fail("invalid acceptance case counts");
}
if (v.verifier !== "scripts/verify-turn-loop-parity.cljk" ||
    JSON.stringify(v.targets) !== JSON.stringify(["js-browser", "wasm32-browser"]) ||
    v.acceptance_total !== 10) {
  fail("v1 requires the fixed 10-vector verifier on js-browser and wasm32-browser");
}

const m = result.metrics;
if (!isNonnegativeInteger(m.turn_count) || !isNonnegativeInteger(m.shell_command_calls) ||
    typeof m.telemetry_source !== "string" || !m.telemetry_source) {
  fail("turn_count, shell_command_calls, and telemetry_source are required");
}
for (const key of ["retry_count", "infrastructure_failures", "preflight_failures"]) {
  if (!isNonnegativeInteger(m[key])) fail(`${key} is required and must be a nonnegative integer`);
}
if (m.api_calls != null && !isNonnegativeInteger(m.api_calls)) fail("api_calls must be a nonnegative integer or null");
const gate = v.syntax_pass && v.compile_pass && v.no_forbidden_forms &&
  v.acceptance_passed === v.acceptance_total;
const missing = [];
for (const key of ["elapsed_ms", "input_tokens", "output_tokens", "session_count", "same_session_resume"]) {
  if (m[key] === null || m[key] === undefined) missing.push(key);
}
if (m.elapsed_ms != null && !isNonnegativeInteger(m.elapsed_ms)) fail("elapsed_ms must be a nonnegative integer or null");
for (const key of ["input_tokens", "output_tokens"]) {
  if (m[key] != null && !isNonnegativeInteger(m[key])) fail(`${key} must be a nonnegative integer or null`);
}
if (m.session_count != null && (!Number.isSafeInteger(m.session_count) || m.session_count < 1)) {
  fail("session_count must be a positive integer or null");
}
if (m.same_session_resume != null && typeof m.same_session_resume !== "boolean") {
  fail("same_session_resume must be a boolean or null");
}

const score = {
  correctness_gate: gate,
  reward: gate ? null : 0,
  dimensions: {
    exact_coding: gate ? 1 : 0,
    speed: null,
    token_efficiency: null,
    session_continuity: null,
  },
  status: gate ? "incomplete" : "incorrect",
  missing_metrics: missing,
};

if (gate && missing.length === 0) {
  const speed = Math.max(0, 1 - m.elapsed_ms / 300000);
  const tokens = m.input_tokens + m.output_tokens;
  const tokenEfficiency = Math.max(0, 1 - tokens / 24000);
  const continuity = m.session_count === 1 && m.same_session_resume === true ? 1 : 0;
  score.dimensions.speed = speed;
  score.dimensions.token_efficiency = tokenEfficiency;
  score.dimensions.session_continuity = continuity;
  score.reward = Math.round((60 + 20 * speed + 10 * tokenEfficiency + 10 * continuity) * 100) / 100;
  score.status = "scored";
}

process.stdout.write(`${JSON.stringify(score, null, 2)}\n`);
