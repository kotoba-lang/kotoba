/**
 * dns kotoba — transfer workflow (slice 1, 7/7 canonical complete).
 *
 *   createTransferRequest    — initiate transfer (rkey=transfer-{transferId})
 *                              Requires 3 ClassA approvals to advance past requested
 *   getTransferRequest       — rkey-direct read
 *   transferFromSquarespace  — orchestration wrapper (creates request + advances
 *                              status to approved or returns needsApprovals)
 *   putTransferStep          — emit a workflow step
 *                              (rkey=step-{transferId}-{step}, idempotent per step)
 *                              Sensitive authCode MUST be signal:v1 encrypted.
 *   listTransferSteps        — cursor over steps for one transferId
 *   putTransferOutcome       — terminal write
 *                              (rkey=outcome-{transferId})
 *                              On success: auto-derive zoneDid from domain
 *
 * Map to vendor lexicons:
 *   transferRequest (record)         → createTransferRequest write
 *   getTransferRequest (query)        → getTransferRequest
 *   transferFromSquarespace (proc)    → transferFromSquarespace
 *   transferStep (record)             → putTransferStep
 *   putTransferStep (proc)            → (same as above; lexicon alias)
 *   transferOutcome (record)          → putTransferOutcome
 *   putTransferOutcome (proc)         → (same as above; lexicon alias)
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  transferOutcomeRkey,
  transferRequestDid,
  transferRequestRkey,
  transferStepRkey,
  zoneDid,
  type CreateTransferRequestInput,
  type CreateTransferRequestOutput,
  type GetTransferRequestInput,
  type GetTransferRequestOutput,
  type ListTransferStepsInput,
  type ListTransferStepsOutput,
  type PutTransferOutcomeInput,
  type PutTransferOutcomeOutput,
  type PutTransferStepInput,
  type PutTransferStepOutput,
  type TransferFromSquarespaceInput,
  type TransferFromSquarespaceOutput,
  type TransferOutcomeRecord,
  type TransferRequestRecord,
  type TransferRequestView,
  type TransferStepRecord,
  type TransferStepView,
} from "./types.js";

const REQUEST_COLLECTION = "com.etzhayyim.dns.transferRequest";
const STEP_COLLECTION = "com.etzhayyim.dns.transferStep";
const OUTCOME_COLLECTION = "com.etzhayyim.dns.transferOutcome";

const REQUIRED_APPROVALS = 3;

async function loadRequest(
  e: Etzhayyim,
  transferId: string
): Promise<{ record: TransferRequestRecord; uri: string } | undefined> {
  const resp = await e
    .read<TransferRequestRecord>({
      collection: REQUEST_COLLECTION,
      rkey: transferRequestRkey(transferId),
    })
    .catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return undefined;
  return { record: r.value, uri: r.uri };
}

export async function createTransferRequest(
  e: Etzhayyim,
  input: CreateTransferRequestInput
): Promise<CreateTransferRequestOutput> {
  if (
    !input.transferId ||
    !input.domain ||
    !input.requesterDid ||
    !input.projectConvoId
  ) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const rkey = transferRequestRkey(input.transferId);
  const existing = await loadRequest(e, input.transferId);
  if (existing) {
    return {
      status: "alreadyExists",
      transferRequestUri: existing.uri,
      did: existing.record.did,
      transferId: input.transferId,
    };
  }
  const approvals = input.approvals ?? [];
  const initialStatus =
    approvals.length >= REQUIRED_APPROVALS ? "approved" : "requested";
  const did = transferRequestDid(input.transferId);
  const now = new Date().toISOString();
  const record: TransferRequestRecord = {
    did,
    transferId: input.transferId,
    domain: input.domain.toLowerCase(),
    fromRegistrar: "squarespace",
    toRegistrar: "cloudflare",
    requesterDid: input.requesterDid,
    cfRegistrarDid: input.cfRegistrarDid,
    sqExporterDid: input.sqExporterDid,
    projectConvoId: input.projectConvoId,
    status: initialStatus,
    approvals,
    requestedAt: now,
    createdAt: now,
  };
  const receipt = await e.write({
    collection: REQUEST_COLLECTION,
    record: record as unknown as Record<string, unknown>,
    rkey,
  });
  return {
    status: "registered",
    transferRequestUri: receipt.uri,
    did,
    transferId: input.transferId,
  };
}

export async function getTransferRequest(
  e: Etzhayyim,
  input: GetTransferRequestInput
): Promise<GetTransferRequestOutput> {
  if (!input.transferId) return { error: "missingTransferId" };
  const loaded = await loadRequest(e, input.transferId);
  if (!loaded) return { error: "notFound" };
  const view: TransferRequestView = {
    ...loaded.record,
    transferRequestUri: loaded.uri,
  };
  return { transferRequest: view };
}

export async function transferFromSquarespace(
  e: Etzhayyim,
  input: TransferFromSquarespaceInput
): Promise<TransferFromSquarespaceOutput> {
  if (input.approvals.length < REQUIRED_APPROVALS) {
    return {
      status: "needsApprovals",
      error: `requires ${REQUIRED_APPROVALS} approvals, got ${input.approvals.length}`,
    };
  }
  const create = await createTransferRequest(e, {
    transferId: input.transferId,
    domain: input.domain,
    requesterDid: input.requesterDid,
    cfRegistrarDid: input.cfRegistrarDid,
    sqExporterDid: input.sqExporterDid,
    projectConvoId: input.projectConvoId,
    approvals: input.approvals,
  });
  if (create.status === "rejected") {
    return { status: "rejected", error: create.error };
  }
  return {
    status: create.status === "alreadyExists" ? "alreadyExists" : "started",
    transferRequestUri: create.transferRequestUri,
    transferId: input.transferId,
  };
}

export async function putTransferStep(
  e: Etzhayyim,
  input: PutTransferStepInput
): Promise<PutTransferStepOutput> {
  if (!input.transferId || !input.step || !input.status) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  // Confirm parent request exists.
  const parent = await loadRequest(e, input.transferId);
  if (!parent) return { status: "requestNotFound" };

  // Validate signal:v1 encryption for authCode step (vault zero-knowledge
  // invariant per root AGENTS.md).
  if (input.step === "authCode" && input.authCodeEncrypted) {
    if (!input.authCodeEncrypted.startsWith("signal:v1:")) {
      return { status: "rejected", error: "authCodeNotEncrypted" };
    }
  }

  const rkey = transferStepRkey(input.transferId, input.step);
  const existing = await e
    .read<TransferStepRecord>({ collection: STEP_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return {
      status: "alreadyExists",
      transferStepUri: existing.records[0].uri,
      transferId: input.transferId,
      step: input.step,
    };
  }
  const now = new Date().toISOString();
  const record: TransferStepRecord = {
    transferRequestUri: parent.uri,
    transferId: input.transferId,
    step: input.step,
    status: input.status,
    actorDid: input.actorDid,
    authCodeEncrypted: input.authCodeEncrypted,
    bindZoneFileUri: input.bindZoneFileUri,
    cfTransferId: input.cfTransferId,
    errorMessage: input.errorMessage,
    occurredAt: now,
    createdAt: now,
  };
  const receipt = await e.write({
    collection: STEP_COLLECTION,
    record: record as unknown as Record<string, unknown>,
    rkey,
  });
  return {
    status: "registered",
    transferStepUri: receipt.uri,
    transferId: input.transferId,
    step: input.step,
  };
}

export async function listTransferSteps(
  e: Etzhayyim,
  input: ListTransferStepsInput
): Promise<ListTransferStepsOutput> {
  if (!input.transferId) return { items: [], total: 0 };
  const limit = Math.min(input.limit ?? 50, 100);
  const resp = await e.read<TransferStepRecord>({
    collection: STEP_COLLECTION,
    cursor: input.cursor,
    limit,
  });
  const items: TransferStepView[] = resp.records
    .filter((r) => r.value.transferId === input.transferId)
    .map((r) => ({ ...r.value, transferStepUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function putTransferOutcome(
  e: Etzhayyim,
  input: PutTransferOutcomeInput
): Promise<PutTransferOutcomeOutput> {
  if (!input.transferId || !input.result) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const parent = await loadRequest(e, input.transferId);
  if (!parent) return { status: "requestNotFound" };

  const rkey = transferOutcomeRkey(input.transferId);
  const existing = await e
    .read<TransferOutcomeRecord>({ collection: OUTCOME_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return {
      status: "alreadyExists",
      transferOutcomeUri: existing.records[0].uri,
      transferId: input.transferId,
      result: existing.records[0].value.result,
      zoneDid: existing.records[0].value.zoneDid,
    };
  }
  const now = new Date().toISOString();
  const derivedZoneDid =
    input.result === "success" ? zoneDid(parent.record.domain) : undefined;
  const record: TransferOutcomeRecord = {
    transferRequestUri: parent.uri,
    transferId: input.transferId,
    domain: parent.record.domain,
    result: input.result,
    zoneDid: derivedZoneDid,
    cloudflareZoneId: input.cloudflareZoneId,
    failureReason: input.failureReason,
    rollbackSteps: input.rollbackSteps,
    completedAt: now,
    createdAt: now,
  };
  const receipt = await e.write({
    collection: OUTCOME_COLLECTION,
    record: record as unknown as Record<string, unknown>,
    rkey,
  });

  // Auto-transition parent status.
  const mergedParent: TransferRequestRecord = {
    ...parent.record,
    status:
      input.result === "success"
        ? "completed"
        : input.result === "failure"
          ? "failed"
          : "rolled-back",
  };
  await e
    .write({
      collection: REQUEST_COLLECTION,
      record: mergedParent as unknown as Record<string, unknown>,
      rkey: transferRequestRkey(input.transferId),
    })
    .catch(() => undefined);

  return {
    status: "registered",
    transferOutcomeUri: receipt.uri,
    transferId: input.transferId,
    result: input.result,
    zoneDid: derivedZoneDid,
  };
}
