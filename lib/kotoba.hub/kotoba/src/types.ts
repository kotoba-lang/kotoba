/**
 * hub kotoba — self-hosted GitHub-compatible API surface, kotoba-E2E split.
 *
 * Per ADR-2606011400 (Consensys) + ADR-2605172400 (3-axis) + ADR-2605181100
 * (kotoba E2E encrypted-record envelope). Founder directive 2026-06-03: maximal
 * migration — front everything that can move; only irreducible regulated
 * execution stays etzhayyim.
 *
 * SPLIT:
 *   PUBLIC (plaintext AT records) — repository catalog metadata (owner/slug/
 *   defaultBranch/visibility/description) + public CI commitStatus facts on a
 *   SHA (context/state/targetUrl). Frontable open project portal metadata.
 *   commitStatus FK → repository via exists() (read + check).
 *
 *   CONFIDENTIAL / private-content (kotoba E2E, com.etzhayyim.encrypted.record):
 *   - pullRequest: review content (title/body/head+base SHA/author DID) — private
 *     change description, sealed; read-cap = owner DID + explicit recipients.
 *   - checkRun: CI/scanner output + summary (may carry secret-scan / security
 *     findings = CUI), sealed.
 *   - webhook: delivery config (target URL + subscribed events + org binding) —
 *     confidential integration config, sealed. The signing SECRET itself never
 *     enters a record; it stays in etzhayyim credential custody.
 *
 *   STAYS etzhayyim (consumed via consent-capability) — the irreducible regulated
 *   EXECUTION, noted not modeled as a collection:
 *     * git smart-HTTP raw object/blob archive custody (the source-code object
 *       store — physically the archive analog; cannot live in AT PDS),
 *     * Clerk JWT signature verification + credential/secret/raw-key custody
 *       (incl. webhook signing-secret),
 *     * merge ENFORCEMENT action (PUT .../merge ref-mutation) execution.
 *
 * AT-Lexicon: no float — PR numbers are integers, SHAs / URLs / timestamps are
 * strings; no money fields.
 */

// ─── Plaintext public collections ───────────────────────────────────
export const REPOSITORY_COLLECTION = "com.etzhayyim.apps.hub.repository";
export const COMMIT_STATUS_COLLECTION = "com.etzhayyim.apps.hub.commitStatus";
// ─── E2E inner-type NSIDs (body shape inside the encrypted envelope) ─
export const PULL_REQUEST_INNER_TYPE = "com.etzhayyim.apps.hub.pullRequest";
export const CHECK_RUN_INNER_TYPE = "com.etzhayyim.apps.hub.checkRun";
export const WEBHOOK_INNER_TYPE = "com.etzhayyim.apps.hub.webhook";

export const HUB_DID_PREFIX = "did:web:hub.etzhayyim.com:" as const;

// ─── Repository (PLAINTEXT, public catalog) ─────────────────────────

export interface RepositoryRecord {
  did: string;
  owner: string;
  name: string;
  slug: string;
  defaultBranch: string;
  /** "public" | "private" — plain catalog field; collection routing is fixed. */
  visibility: string;
  description?: string;
  createdAt: string;
}
export interface RepositoryView extends RepositoryRecord {
  repositoryUri: string;
}
export interface RegisterRepositoryInput {
  owner: string;
  name: string;
  defaultBranch?: string;
  visibility?: string;
  description?: string;
}
export interface RegisterRepositoryOutput {
  status: "registered" | "alreadyExists" | "rejected";
  repositoryUri?: string;
  did?: string;
  slug?: string;
  error?: string;
}
export interface GetRepositoryInput {
  owner: string;
  name: string;
}
export interface GetRepositoryOutput {
  repository?: RepositoryView;
  error?: string;
}
export interface ListRepositoriesInput {
  owner?: string;
  visibility?: string;
  limit?: number;
  cursor?: string;
}
export interface ListRepositoriesOutput {
  items: RepositoryView[];
  cursor?: string;
  total: number;
}

// ─── Commit status (PLAINTEXT, public CI fact, FK → repository) ──────

export interface CommitStatusRecord {
  did: string;
  slug: string;
  sha: string;
  context: string;
  /** "success" | "pending" | "failure" | "error". */
  state: string;
  targetUrl?: string;
  description?: string;
  createdAt: string;
}
export interface CommitStatusView extends CommitStatusRecord {
  statusUri: string;
}
export interface CreateStatusInput {
  owner: string;
  name: string;
  sha: string;
  context: string;
  state: string;
  targetUrl?: string;
  description?: string;
}
export interface CreateStatusOutput {
  status: "created" | "alreadyExists" | "rejected";
  statusUri?: string;
  did?: string;
  error?: string;
}
export interface ListStatusesInput {
  owner?: string;
  name?: string;
  sha?: string;
  limit?: number;
  cursor?: string;
}
export interface ListStatusesOutput {
  items: CommitStatusView[];
  cursor?: string;
  total: number;
}

// ─── Pull request (E2E-ENCRYPTED, confidential review content) ──────

export interface PullRequestBody {
  prId: string;
  slug: string;
  /** integer PR number. */
  number: number;
  title: string;
  body?: string;
  headSha: string;
  baseRef: string;
  authorDid: string;
  state: string;
  openedAt: string;
}
export interface PullRequestView extends PullRequestBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface OpenPullRequestInput {
  prId: string;
  owner: string;
  name: string;
  number: number;
  title: string;
  body?: string;
  headSha: string;
  baseRef: string;
  authorDid: string;
  state?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface OpenPullRequestOutput {
  status: "opened" | "rejected";
  uri?: string;
  keyId?: string;
  prId?: string;
  error?: string;
}
export interface ListPullRequestsInput {
  slug?: string;
  state?: string;
  limit?: number;
  cursor?: string;
}
export interface ListPullRequestsOutput {
  items: PullRequestView[];
  cursor?: string;
  total: number;
}
export interface GetPullRequestInput {
  prId: string;
}
export interface GetPullRequestOutput {
  pullRequest?: PullRequestView;
  error?: string;
}

// ─── Check run (E2E-ENCRYPTED, CUI scanner output) ──────────────────

export interface CheckRunBody {
  checkRunId: string;
  slug: string;
  sha: string;
  checkName: string;
  /** "queued" | "in_progress" | "completed". */
  status: string;
  /** "success" | "failure" | "neutral" | "cancelled" | "timed_out". */
  conclusion?: string;
  summary?: string;
  detailsUrl?: string;
  completedAt?: string;
}
export interface CheckRunView extends CheckRunBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordCheckRunInput {
  checkRunId: string;
  owner: string;
  name: string;
  sha: string;
  checkName: string;
  status: string;
  conclusion?: string;
  summary?: string;
  detailsUrl?: string;
  recipients?: string[];
}
export interface RecordCheckRunOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  checkRunId?: string;
  error?: string;
}
export interface ListCheckRunsInput {
  slug?: string;
  sha?: string;
  limit?: number;
  cursor?: string;
}
export interface ListCheckRunsOutput {
  items: CheckRunView[];
  cursor?: string;
  total: number;
}

// ─── Webhook (E2E-ENCRYPTED, confidential delivery config) ──────────

export interface WebhookBody {
  webhookId: string;
  slug: string;
  targetUrl: string;
  events: string[];
  orgDid?: string;
  active: boolean;
  registeredAt: string;
}
export interface WebhookView extends WebhookBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RegisterWebhookInput {
  webhookId: string;
  owner: string;
  name: string;
  targetUrl: string;
  events: string[];
  orgDid?: string;
  active?: boolean;
  recipients?: string[];
}
export interface RegisterWebhookOutput {
  status: "registered" | "rejected";
  uri?: string;
  keyId?: string;
  webhookId?: string;
  error?: string;
}
export interface ListWebhooksInput {
  slug?: string;
  limit?: number;
  cursor?: string;
}
export interface ListWebhooksOutput {
  items: WebhookView[];
  cursor?: string;
  total: number;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  repositoryCount?: number;
  commitStatusCount?: number;
  pullRequestCount?: number;
  checkRunCount?: number;
  webhookCount?: number;
  repositoriesByVisibility?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isVisibility(v: unknown): v is string {
  return v === "public" || v === "private";
}
export function slugOf(owner: string, name: string): string {
  return `${owner.toLowerCase()}/${name.toLowerCase()}`;
}
export function repoDidFor(owner: string, name: string): string {
  return `${HUB_DID_PREFIX}repo:${owner.toLowerCase()}:${name.toLowerCase()}`;
}
export function statusDidFor(slug: string, sha: string, context: string): string {
  return `${HUB_DID_PREFIX}status:${sha.toLowerCase()}:${context.toLowerCase()}`;
}
export function rkeyOf(prefix: string, id: string): string {
  return `${prefix}-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
