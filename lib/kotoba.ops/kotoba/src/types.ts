/**
 * ops kotoba — Operations Automation Platform (kotoba-E2E split).
 *
 * Per ADR-2606011400 (Consensys product-front / infra-back) + ADR-2605172400
 * (3-axis) + ADR-2605181100 (kotoba E2E encrypted-record envelope). Founder
 * directive 2026-06-03: PII / CUI / confidential business data migrate to
 * etzhayyim when made safe via kotoba E2E.
 *
 * SOURCE OF TRUTH: the ops app surface is 8 methods over 2 collections
 * (`processRun`, `automation`) — see
 * 60-apps/etzhayyim-project-ops/appview/ops-mcp-component/src/app.ts +
 * kotodama.jsonld subscribeRepos. PROJECT.jsonld scopes ops to "credits/revenue
 * tracking + campaign ROI", so the automation definition is confidential.
 *
 * SPLIT:
 *   PUBLIC (plaintext AT records) — processRun: operational process-execution
 *   metadata (process name, status, step/error counts, durations). APQC process
 *   monitoring telemetry, no PII / no secrets. Frontable open operational data.
 *   Carries an FK to automation (validated via exists-scan, not a join).
 *
 *   CONFIDENTIAL (kotoba E2E, com.etzhayyim.encrypted.record) — automation:
 *   the automation definition carries business-sensitive config — revenue /
 *   credits targets (decimal strings), internal dispatch targets, schedule
 *   parameters. Sealed via sdk.encryptedWrite (read-cap = owner DID + explicit
 *   recipients) so it lives on-substrate encrypted, never etzhayyim-resident.
 *
 *   STAYS etzhayyim (consumed via consent-capability) — scheduler EXECUTION (cron
 *   firing / dispatch), LLM inference for agent replies, fiat/credits settlement
 *   EXECUTION, secret/credential custody. The regulated *acts*, not the data
 *   records (which migrate: plaintext if public, E2E if confidential).
 *
 * AT-Lexicon: no float. Counts/durations are integers; success-rate /
 * completion-percent are integer 0-100; money/credits are decimal STRINGS.
 */

// Plaintext public collection.
export const PROCESS_RUN_COLLECTION = "com.etzhayyim.apps.ops.processRun";
// E2E inner-type NSID (body shape inside the encrypted envelope).
export const AUTOMATION_INNER_TYPE = "com.etzhayyim.apps.ops.automation";

export const OPS_DID_PREFIX = "did:web:ops.etzhayyim.com:" as const;

export type ProcessRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

// ─── Process run (PLAINTEXT, public operational metadata) ────────────

export interface ProcessRunRecord {
  did: string;
  runId: string;
  processName: string;
  /** Optional FK to an E2E automation (its automationId). */
  automationId?: string;
  status: ProcessRunStatus;
  /** integer ≥ 0. */
  stepCount: number;
  /** integer ≥ 0. */
  errorCount: number;
  /** integer 0-100. */
  completionPct: number;
  /** integer ms ≥ 0. */
  durationMs: number;
  startedAt: string;
  createdAt: string;
}
export interface ProcessRunView extends ProcessRunRecord {
  runUri: string;
}
export interface CreateProcessRunInput {
  runId: string;
  processName: string;
  automationId?: string;
  status?: ProcessRunStatus;
  stepCount?: number;
  errorCount?: number;
  completionPct?: number;
  durationMs?: number;
  startedAt?: string;
}
export interface CreateProcessRunOutput {
  status: "created" | "alreadyExists" | "rejected";
  runUri?: string;
  did?: string;
  runId?: string;
  error?: string;
}
export interface UpdateProcessRunInput {
  runId: string;
  status?: ProcessRunStatus;
  stepCount?: number;
  errorCount?: number;
  completionPct?: number;
  durationMs?: number;
}
export interface UpdateProcessRunOutput {
  status: "updated" | "notFound" | "rejected";
  runUri?: string;
  runId?: string;
  error?: string;
}
export interface ListProcessRunsInput {
  processName?: string;
  status?: ProcessRunStatus;
  limit?: number;
  cursor?: string;
}
export interface ListProcessRunsOutput {
  items: ProcessRunView[];
  cursor?: string;
  total: number;
}
export interface GetProcessRunInput {
  runId: string;
}
export interface GetProcessRunOutput {
  run?: ProcessRunView;
  error?: string;
}

// ─── Automation (E2E-ENCRYPTED, confidential business config) ────────

export type AutomationStatus = "active" | "paused" | "archived";

export interface AutomationBody {
  automationId: string;
  name: string;
  /** cron-like trigger spec; opaque string. */
  schedule: string;
  /** internal dispatch target (XRPC NSID / pod route); confidential. */
  dispatchTarget: string;
  status: AutomationStatus;
  /** monthly revenue target, decimal STRING (no float). e.g. "12500.00". */
  revenueTargetUsd: string;
  /** credits/GCC budget cap, decimal STRING. e.g. "5000.000". */
  creditsBudget: string;
  createdAt: string;
}
export interface AutomationView extends AutomationBody {
  uri: string;
  sender: string;
  envelopeCreatedAt: string;
}
export interface CreateAutomationInput {
  automationId: string;
  name: string;
  schedule: string;
  dispatchTarget: string;
  status?: AutomationStatus;
  revenueTargetUsd?: string;
  creditsBudget?: string;
  createdAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface CreateAutomationOutput {
  status: "created" | "rejected";
  uri?: string;
  keyId?: string;
  automationId?: string;
  error?: string;
}
export interface UpdateAutomationInput {
  automationId: string;
  name?: string;
  schedule?: string;
  dispatchTarget?: string;
  status?: AutomationStatus;
  revenueTargetUsd?: string;
  creditsBudget?: string;
  /** Re-seal recipients (owner always included). */
  recipients?: string[];
}
export interface UpdateAutomationOutput {
  status: "updated" | "notFound" | "rejected";
  uri?: string;
  keyId?: string;
  automationId?: string;
  error?: string;
}
export interface ListAutomationsInput {
  status?: AutomationStatus;
  limit?: number;
  cursor?: string;
}
export interface ListAutomationsOutput {
  items: AutomationView[];
  cursor?: string;
  total: number;
}
export interface GetAutomationInput {
  automationId: string;
}
export interface GetAutomationOutput {
  automation?: AutomationView;
  error?: string;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  processRunCount?: number;
  automationCount?: number;
  runsByStatus?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export const PROCESS_RUN_STATUSES: ProcessRunStatus[] = ["queued", "running", "succeeded", "failed", "cancelled"];
export const AUTOMATION_STATUSES: AutomationStatus[] = ["active", "paused", "archived"];

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isPct(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 100;
}
/** Money/credits are decimal STRINGS (AT-Lexicon has no float). */
export function isDecimalString(s: unknown): s is string {
  return typeof s === "string" && /^\d+(\.\d+)?$/.test(s);
}
export function opsDidFor(kind: string, id: string): string {
  return `${OPS_DID_PREFIX}${kind}:${id.toLowerCase()}`;
}
export function runRkey(id: string): string {
  return `run-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function automationRkey(id: string): string {
  return `auto-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
