/**
 * hub kotoba — kotoba-E2E registry.
 *
 * Plaintext path (repository, commitStatus): sdk.write / sdk.read — public
 * project-portal catalog metadata + public CI status facts. commitStatus FK →
 * repository via exists() (read + check).
 * E2E path (pullRequest, checkRun, webhook): sdk.encryptedWrite / sdk.encryptedRead
 * — confidential review content, CUI scanner output, and delivery config sealed
 * in the kotoba envelope (ADR-2605181100), read-cap = owner DID + explicit
 * recipients. The substrate never sees PR bodies, scanner findings, or webhook
 * targets in plaintext.
 *
 * git smart-HTTP raw-object archive custody, Clerk JWT verification + credential
 * custody (incl. webhook signing-secret), and the merge ENFORCEMENT action stay
 * etzhayyim (consumed via consent-capability) — not modeled here as collections.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  CHECK_RUN_INNER_TYPE,
  COMMIT_STATUS_COLLECTION,
  PULL_REQUEST_INNER_TYPE,
  REPOSITORY_COLLECTION,
  WEBHOOK_INNER_TYPE,
  isUint,
  isVisibility,
  repoDidFor,
  rkeyOf,
  slugOf,
  statusDidFor,
  type CheckRunBody,
  type CheckRunView,
  type CommitStatusRecord,
  type CommitStatusView,
  type CoverageInput,
  type CoverageOutput,
  type CreateStatusInput,
  type CreateStatusOutput,
  type GetPullRequestInput,
  type GetPullRequestOutput,
  type GetRepositoryInput,
  type GetRepositoryOutput,
  type ListCheckRunsInput,
  type ListCheckRunsOutput,
  type ListPullRequestsInput,
  type ListPullRequestsOutput,
  type ListRepositoriesInput,
  type ListRepositoriesOutput,
  type ListStatusesInput,
  type ListStatusesOutput,
  type ListWebhooksInput,
  type ListWebhooksOutput,
  type OpenPullRequestInput,
  type OpenPullRequestOutput,
  type PullRequestBody,
  type PullRequestView,
  type RecordCheckRunInput,
  type RecordCheckRunOutput,
  type RegisterRepositoryInput,
  type RegisterRepositoryOutput,
  type RegisterWebhookInput,
  type RegisterWebhookOutput,
  type RepositoryRecord,
  type RepositoryView,
  type WebhookBody,
  type WebhookView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Plaintext FK helper (exists via read; mock has no exists()) ─────

async function repositoryExists(e: Etzhayyim, slug: string): Promise<boolean> {
  const rkey = rkeyOf("repo", slug);
  const resp = await e
    .read<RepositoryRecord>({ collection: REPOSITORY_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: RepositoryRecord }> }));
  return Boolean(resp.records[0]?.value);
}

// ─── Repository (PLAINTEXT, public catalog) ─────────────────────────

export async function registerRepository(e: Etzhayyim, input: RegisterRepositoryInput): Promise<RegisterRepositoryOutput> {
  if (!input.owner || !input.name) return { status: "rejected", error: "missingRequiredFields" };
  const visibility = input.visibility ?? "public";
  if (!isVisibility(visibility)) return { status: "rejected", error: "invalidVisibility" };
  const slug = slugOf(input.owner, input.name);
  const rkey = rkeyOf("repo", slug);
  const existing = await e.read<RepositoryRecord>({ collection: REPOSITORY_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", repositoryUri: existing.records[0].uri, did: existing.records[0].value.did, slug };
  }
  const now = new Date().toISOString();
  const did = repoDidFor(input.owner, input.name);
  const record: RepositoryRecord = {
    did,
    owner: input.owner,
    name: input.name,
    slug,
    defaultBranch: input.defaultBranch ?? "main",
    visibility,
    description: input.description,
    createdAt: now,
  };
  const receipt = await e.write({ collection: REPOSITORY_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", repositoryUri: receipt.uri, did, slug };
}

export async function getRepository(e: Etzhayyim, input: GetRepositoryInput): Promise<GetRepositoryOutput> {
  if (!input.owner || !input.name) return { error: "missingRequiredFields" };
  const rkey = rkeyOf("repo", slugOf(input.owner, input.name));
  const resp = await e.read<RepositoryRecord>({ collection: REPOSITORY_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { repository: { ...r.value, repositoryUri: r.uri } };
}

export async function listRepositories(e: Etzhayyim, input: ListRepositoriesInput = {}): Promise<ListRepositoriesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<RepositoryRecord>({ collection: REPOSITORY_COLLECTION, cursor: input.cursor, limit });
  const items: RepositoryView[] = resp.records
    .filter((r) => (!input.owner || r.value.owner === input.owner) && (!input.visibility || r.value.visibility === input.visibility))
    .map((r) => ({ ...r.value, repositoryUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Commit status (PLAINTEXT, public CI fact, FK → repository) ──────

export async function createCommitStatus(e: Etzhayyim, input: CreateStatusInput): Promise<CreateStatusOutput> {
  if (!input.owner || !input.name || !input.sha || !input.context || !input.state) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const slug = slugOf(input.owner, input.name);
  if (!(await repositoryExists(e, slug))) return { status: "rejected", error: "repositoryNotFound" };
  const rkey = rkeyOf("status", `${slug}-${input.sha}-${input.context}`);
  const existing = await e.read<CommitStatusRecord>({ collection: COMMIT_STATUS_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", statusUri: existing.records[0].uri, did: existing.records[0].value.did };
  }
  const now = new Date().toISOString();
  const did = statusDidFor(slug, input.sha, input.context);
  const record: CommitStatusRecord = {
    did,
    slug,
    sha: input.sha,
    context: input.context,
    state: input.state,
    targetUrl: input.targetUrl,
    description: input.description,
    createdAt: now,
  };
  const receipt = await e.write({ collection: COMMIT_STATUS_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "created", statusUri: receipt.uri, did };
}

export async function listCommitStatuses(e: Etzhayyim, input: ListStatusesInput = {}): Promise<ListStatusesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const slug = input.owner && input.name ? slugOf(input.owner, input.name) : undefined;
  const resp = await e.read<CommitStatusRecord>({ collection: COMMIT_STATUS_COLLECTION, cursor: input.cursor, limit });
  const items: CommitStatusView[] = resp.records
    .filter((r) => (!slug || r.value.slug === slug) && (!input.sha || r.value.sha === input.sha))
    .map((r) => ({ ...r.value, statusUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Pull request (E2E-ENCRYPTED, confidential review content) ──────

export async function openPullRequest(e: Etzhayyim, input: OpenPullRequestInput): Promise<OpenPullRequestOutput> {
  if (!input.prId || !input.owner || !input.name || !input.title || !input.headSha || !input.baseRef || !input.authorDid) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  if (!isUint(input.number)) return { status: "rejected", error: "invalidNumber" };
  const body: PullRequestBody = {
    prId: input.prId,
    slug: slugOf(input.owner, input.name),
    number: input.number,
    title: input.title,
    body: input.body,
    headSha: input.headSha,
    baseRef: input.baseRef,
    authorDid: input.authorDid,
    state: input.state ?? "open",
    openedAt: new Date().toISOString(),
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: PULL_REQUEST_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("pr", input.prId),
  });
  return { status: "opened", uri: receipt.uri, keyId: receipt.keyId, prId: input.prId };
}

async function scanPullRequests(e: Etzhayyim, maxScan: number): Promise<PullRequestView[]> {
  const out: PullRequestView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<PullRequestBody>({ innerType: PULL_REQUEST_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listPullRequests(e: Etzhayyim, input: ListPullRequestsInput = {}): Promise<ListPullRequestsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanPullRequests(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((p) => (!input.slug || p.slug === input.slug) && (!input.state || p.state === input.state));
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getPullRequest(e: Etzhayyim, input: GetPullRequestInput): Promise<GetPullRequestOutput> {
  if (!input.prId) return { error: "invalidPrId" };
  const all = await scanPullRequests(e, DEFAULT_MAX_SCAN);
  const found = all.find((p) => p.prId === input.prId);
  if (!found) return { error: "notFound" };
  return { pullRequest: found };
}

// ─── Check run (E2E-ENCRYPTED, CUI scanner output) ──────────────────

export async function recordCheckRun(e: Etzhayyim, input: RecordCheckRunInput): Promise<RecordCheckRunOutput> {
  if (!input.checkRunId || !input.owner || !input.name || !input.sha || !input.checkName || !input.status) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const body: CheckRunBody = {
    checkRunId: input.checkRunId,
    slug: slugOf(input.owner, input.name),
    sha: input.sha,
    checkName: input.checkName,
    status: input.status,
    conclusion: input.conclusion,
    summary: input.summary,
    detailsUrl: input.detailsUrl,
    completedAt: input.status === "completed" ? new Date().toISOString() : undefined,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: CHECK_RUN_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("check", input.checkRunId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, checkRunId: input.checkRunId };
}

async function scanCheckRuns(e: Etzhayyim, maxScan: number): Promise<CheckRunView[]> {
  const out: CheckRunView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<CheckRunBody>({ innerType: CHECK_RUN_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listCheckRuns(e: Etzhayyim, input: ListCheckRunsInput = {}): Promise<ListCheckRunsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanCheckRuns(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((c) => (!input.slug || c.slug === input.slug) && (!input.sha || c.sha === input.sha));
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Webhook (E2E-ENCRYPTED, confidential delivery config) ──────────

export async function registerWebhook(e: Etzhayyim, input: RegisterWebhookInput): Promise<RegisterWebhookOutput> {
  if (!input.webhookId || !input.owner || !input.name || !input.targetUrl) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  if (!Array.isArray(input.events) || input.events.length === 0) return { status: "rejected", error: "invalidEvents" };
  const body: WebhookBody = {
    webhookId: input.webhookId,
    slug: slugOf(input.owner, input.name),
    targetUrl: input.targetUrl,
    events: input.events,
    orgDid: input.orgDid,
    active: input.active ?? true,
    registeredAt: new Date().toISOString(),
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: WEBHOOK_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("hook", input.webhookId),
  });
  return { status: "registered", uri: receipt.uri, keyId: receipt.keyId, webhookId: input.webhookId };
}

async function scanWebhooks(e: Etzhayyim, maxScan: number): Promise<WebhookView[]> {
  const out: WebhookView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<WebhookBody>({ innerType: WEBHOOK_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listWebhooks(e: Etzhayyim, input: ListWebhooksInput = {}): Promise<ListWebhooksOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanWebhooks(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((w) => !input.slug || w.slug === input.slug);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Coverage rollup (plaintext + E2E countAll) ─────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const repositoriesByVisibility: Record<string, number> = {};
  let repositoryCount = 0;
  let repoCursor: string | undefined;
  while (repositoryCount < maxScan) {
    const page = await e.read<RepositoryRecord>({ collection: REPOSITORY_COLLECTION, cursor: repoCursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      repositoriesByVisibility[r.value.visibility] = (repositoriesByVisibility[r.value.visibility] ?? 0) + 1;
      repositoryCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    repoCursor = page.cursor;
  }
  let commitStatusCount = 0;
  let statusCursor: string | undefined;
  while (commitStatusCount < maxScan) {
    const page = await e.read<CommitStatusRecord>({ collection: COMMIT_STATUS_COLLECTION, cursor: statusCursor, limit: PAGE_LIMIT });
    commitStatusCount += page.records.length;
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    statusCursor = page.cursor;
  }
  const pullRequestCount = (await scanPullRequests(e, maxScan)).length;
  const checkRunCount = (await scanCheckRuns(e, maxScan)).length;
  const webhookCount = (await scanWebhooks(e, maxScan)).length;
  return {
    repositoryCount,
    commitStatusCount,
    pullRequestCount,
    checkRunCount,
    webhookCount,
    repositoriesByVisibility,
    truncated:
      repositoryCount >= maxScan ||
      commitStatusCount >= maxScan ||
      pullRequestCount >= maxScan ||
      checkRunCount >= maxScan ||
      webhookCount >= maxScan,
  };
}
