/**
 * ops kotoba — kotoba-E2E registry.
 *
 * Plaintext path (processRun): sdk.write / sdk.read — public operational
 * telemetry, with an exists()-style FK check against the E2E automation.
 * E2E path (automation): sdk.encryptedWrite / sdk.encryptedRead — confidential
 * business config (revenue/credits targets, dispatch target) sealed in the
 * kotoba envelope (ADR-2605181100), read-cap = owner DID. The substrate never
 * sees the automation definition in plaintext.
 *
 * Scheduler firing, LLM inference, fiat/credits settlement, and secret custody
 * stay etzhayyim (consent-capability) — only the data records migrate here.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  AUTOMATION_INNER_TYPE,
  AUTOMATION_STATUSES,
  PROCESS_RUN_COLLECTION,
  PROCESS_RUN_STATUSES,
  automationRkey,
  isDecimalString,
  isPct,
  isUint,
  opsDidFor,
  runRkey,
  type AutomationBody,
  type AutomationStatus,
  type AutomationView,
  type CoverageInput,
  type CoverageOutput,
  type CreateAutomationInput,
  type CreateAutomationOutput,
  type CreateProcessRunInput,
  type CreateProcessRunOutput,
  type GetAutomationInput,
  type GetAutomationOutput,
  type GetProcessRunInput,
  type GetProcessRunOutput,
  type ListAutomationsInput,
  type ListAutomationsOutput,
  type ListProcessRunsInput,
  type ListProcessRunsOutput,
  type ProcessRunRecord,
  type ProcessRunStatus,
  type ProcessRunView,
  type UpdateAutomationInput,
  type UpdateAutomationOutput,
  type UpdateProcessRunInput,
  type UpdateProcessRunOutput,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Automation E2E scan helpers (shared) ───────────────────────────

async function scanAutomations(e: Etzhayyim, maxScan: number): Promise<AutomationView[]> {
  const out: AutomationView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<AutomationBody>({ innerType: AUTOMATION_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, envelopeCreatedAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

/** FK exists-check: does an automation with this id live in the owner's E2E view? */
async function automationExists(e: Etzhayyim, automationId: string): Promise<boolean> {
  const all = await scanAutomations(e, DEFAULT_MAX_SCAN);
  return all.some((a) => a.automationId === automationId);
}

// ─── Process run (PLAINTEXT) ────────────────────────────────────────

export async function createProcessRun(e: Etzhayyim, input: CreateProcessRunInput): Promise<CreateProcessRunOutput> {
  if (!input.runId || !input.processName) return { status: "rejected", error: "missingRequiredFields" };
  const status: ProcessRunStatus = input.status ?? "queued";
  if (!PROCESS_RUN_STATUSES.includes(status)) return { status: "rejected", error: "invalidStatus" };
  const stepCount = input.stepCount ?? 0;
  const errorCount = input.errorCount ?? 0;
  const completionPct = input.completionPct ?? 0;
  const durationMs = input.durationMs ?? 0;
  if (!isUint(stepCount) || !isUint(errorCount) || !isUint(durationMs)) return { status: "rejected", error: "invalidCount" };
  if (!isPct(completionPct)) return { status: "rejected", error: "invalidCompletionPct" };
  // FK: if an automationId is supplied it must resolve to an existing E2E automation.
  if (input.automationId && !(await automationExists(e, input.automationId))) {
    return { status: "rejected", error: "unknownAutomation" };
  }
  const rkey = runRkey(input.runId);
  const existing = await e.read<ProcessRunRecord>({ collection: PROCESS_RUN_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", runUri: existing.records[0].uri, did: existing.records[0].value.did, runId: input.runId };
  }
  const now = new Date().toISOString();
  const did = opsDidFor("run", input.runId);
  const record: ProcessRunRecord = {
    did,
    runId: input.runId,
    processName: input.processName,
    ...(input.automationId ? { automationId: input.automationId } : {}),
    status,
    stepCount,
    errorCount,
    completionPct,
    durationMs,
    startedAt: input.startedAt ?? now,
    createdAt: now,
  };
  const receipt = await e.write({ collection: PROCESS_RUN_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "created", runUri: receipt.uri, did, runId: input.runId };
}

export async function updateProcessRun(e: Etzhayyim, input: UpdateProcessRunInput): Promise<UpdateProcessRunOutput> {
  if (!input.runId) return { status: "rejected", error: "missingRunId" };
  if (input.status !== undefined && !PROCESS_RUN_STATUSES.includes(input.status)) return { status: "rejected", error: "invalidStatus" };
  if (input.stepCount !== undefined && !isUint(input.stepCount)) return { status: "rejected", error: "invalidStepCount" };
  if (input.errorCount !== undefined && !isUint(input.errorCount)) return { status: "rejected", error: "invalidErrorCount" };
  if (input.durationMs !== undefined && !isUint(input.durationMs)) return { status: "rejected", error: "invalidDurationMs" };
  if (input.completionPct !== undefined && !isPct(input.completionPct)) return { status: "rejected", error: "invalidCompletionPct" };
  const rkey = runRkey(input.runId);
  const existing = await e.read<ProcessRunRecord>({ collection: PROCESS_RUN_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const cur = existing.records[0]?.value;
  if (!cur) return { status: "notFound", runId: input.runId };
  const next: ProcessRunRecord = {
    ...cur,
    status: input.status ?? cur.status,
    stepCount: input.stepCount ?? cur.stepCount,
    errorCount: input.errorCount ?? cur.errorCount,
    completionPct: input.completionPct ?? cur.completionPct,
    durationMs: input.durationMs ?? cur.durationMs,
  };
  const receipt = await e.write({ collection: PROCESS_RUN_COLLECTION, record: next as unknown as Record<string, unknown>, rkey });
  return { status: "updated", runUri: receipt.uri, runId: input.runId };
}

export async function listProcessRuns(e: Etzhayyim, input: ListProcessRunsInput = {}): Promise<ListProcessRunsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ProcessRunRecord>({ collection: PROCESS_RUN_COLLECTION, cursor: input.cursor, limit });
  const items: ProcessRunView[] = resp.records
    .filter((r) => !input.processName || r.value.processName === input.processName)
    .filter((r) => !input.status || r.value.status === input.status)
    .map((r) => ({ ...r.value, runUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function getProcessRun(e: Etzhayyim, input: GetProcessRunInput): Promise<GetProcessRunOutput> {
  if (!input.runId) return { error: "invalidRunId" };
  const resp = await e.read<ProcessRunRecord>({ collection: PROCESS_RUN_COLLECTION, rkey: runRkey(input.runId) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { run: { ...r.value, runUri: r.uri } };
}

// ─── Automation (E2E-ENCRYPTED, confidential) ───────────────────────

function validateAutomationDecimals(input: { revenueTargetUsd?: string; creditsBudget?: string }): string | undefined {
  if (input.revenueTargetUsd !== undefined && !isDecimalString(input.revenueTargetUsd)) return "invalidRevenueTargetUsd";
  if (input.creditsBudget !== undefined && !isDecimalString(input.creditsBudget)) return "invalidCreditsBudget";
  return undefined;
}

export async function createAutomation(e: Etzhayyim, input: CreateAutomationInput): Promise<CreateAutomationOutput> {
  if (!input.automationId || !input.name || !input.schedule || !input.dispatchTarget) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const status: AutomationStatus = input.status ?? "active";
  if (!AUTOMATION_STATUSES.includes(status)) return { status: "rejected", error: "invalidStatus" };
  const decErr = validateAutomationDecimals(input);
  if (decErr) return { status: "rejected", error: decErr };
  const body: AutomationBody = {
    automationId: input.automationId,
    name: input.name,
    schedule: input.schedule,
    dispatchTarget: input.dispatchTarget,
    status,
    revenueTargetUsd: input.revenueTargetUsd ?? "0.00",
    creditsBudget: input.creditsBudget ?? "0.000",
    createdAt: input.createdAt ?? new Date().toISOString(),
  };
  // Read-cap = owner DID (sender, auto-wrapped) + any explicit recipients.
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: AUTOMATION_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: automationRkey(input.automationId),
  });
  return { status: "created", uri: receipt.uri, keyId: receipt.keyId, automationId: input.automationId };
}

export async function updateAutomation(e: Etzhayyim, input: UpdateAutomationInput): Promise<UpdateAutomationOutput> {
  if (!input.automationId) return { status: "rejected", error: "missingAutomationId" };
  if (input.status !== undefined && !AUTOMATION_STATUSES.includes(input.status)) return { status: "rejected", error: "invalidStatus" };
  const decErr = validateAutomationDecimals(input);
  if (decErr) return { status: "rejected", error: decErr };
  const all = await scanAutomations(e, DEFAULT_MAX_SCAN);
  const cur = all.find((a) => a.automationId === input.automationId);
  if (!cur) return { status: "notFound", automationId: input.automationId };
  const body: AutomationBody = {
    automationId: cur.automationId,
    name: input.name ?? cur.name,
    schedule: input.schedule ?? cur.schedule,
    dispatchTarget: input.dispatchTarget ?? cur.dispatchTarget,
    status: input.status ?? cur.status,
    revenueTargetUsd: input.revenueTargetUsd ?? cur.revenueTargetUsd,
    creditsBudget: input.creditsBudget ?? cur.creditsBudget,
    createdAt: cur.createdAt,
  };
  // Re-seal at the same rkey (envelope is immutable; overwrite by rkey).
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: AUTOMATION_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: automationRkey(input.automationId),
  });
  return { status: "updated", uri: receipt.uri, keyId: receipt.keyId, automationId: input.automationId };
}

export async function listAutomations(e: Etzhayyim, input: ListAutomationsInput = {}): Promise<ListAutomationsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanAutomations(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((a) => !input.status || a.status === input.status);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getAutomation(e: Etzhayyim, input: GetAutomationInput): Promise<GetAutomationOutput> {
  if (!input.automationId) return { error: "invalidAutomationId" };
  const all = await scanAutomations(e, DEFAULT_MAX_SCAN);
  const found = all.find((a) => a.automationId === input.automationId);
  if (!found) return { error: "notFound" };
  return { automation: found };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const runsByStatus: Record<string, number> = {};
  let processRunCount = 0;
  let cursor: string | undefined;
  while (processRunCount < maxScan) {
    const page = await e.read<ProcessRunRecord>({ collection: PROCESS_RUN_COLLECTION, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      runsByStatus[r.value.status] = (runsByStatus[r.value.status] ?? 0) + 1;
      processRunCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const automationCount = (await scanAutomations(e, maxScan)).length;
  return {
    processRunCount,
    automationCount,
    runsByStatus,
    truncated: processRunCount >= maxScan || automationCount >= maxScan,
  };
}
