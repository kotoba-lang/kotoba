/**
 * dns kotoba — record types.
 *
 * Per ADR-2605203000 Option B (PDS XRPC). Domain transfer workflow —
 * Squarespace → Cloudflare with 3-signer ClassA approvals.
 *
 * Records:
 *   TransferRequest    — initiating record (transferId = rkey = projectConvoId)
 *   TransferStep       — progress record per workflow step
 *                        (steps: disableAutoRenew/unlock/authCode/dnsExport/cfTransfer)
 *                        Sensitive `authCode` is signal:v1: encrypted.
 *   TransferOutcome    — terminal record; triggers zone DID creation on success
 *
 * Identity hierarchy:
 *   did:web:dns.etzhayyim.com                         — controller
 *   did:web:dns.etzhayyim.com:zone:{domain_slug}      — Zone (post-transfer)
 *   did:web:dns.etzhayyim.com:transfer:{transferId}   — TransferRequest
 */

export const DNS_DID_PREFIX = "did:web:dns.etzhayyim.com:" as const;

export type FromRegistrar = "squarespace";
export type ToRegistrar = "cloudflare";

export type TransferStatus =
  | "requested"
  | "approved"
  | "in-progress"
  | "completed"
  | "failed"
  | "rolled-back";

export type StepName =
  | "disableAutoRenew"
  | "unlock"
  | "authCode"
  | "dnsExport"
  | "cfTransfer";

export type StepStatus = "started" | "succeeded" | "failed" | "skipped";

export type OutcomeResult = "success" | "failure" | "aborted";

// ─── TransferRequest tier ───────────────────────────────────────────

export interface TransferRequestRecord {
  did: string;
  transferId: string;
  domain: string;
  fromRegistrar: FromRegistrar;
  toRegistrar: ToRegistrar;
  requesterDid: string;
  cfRegistrarDid?: string;
  sqExporterDid?: string;
  projectConvoId: string;
  status: TransferStatus;
  /** ClassA 3-signer approval records (DIDs). */
  approvals: string[];
  requestedAt: string;
  createdAt: string;
}

export interface TransferRequestView extends TransferRequestRecord {
  transferRequestUri: string;
}

export interface CreateTransferRequestInput {
  transferId: string;
  domain: string;
  requesterDid: string;
  cfRegistrarDid?: string;
  sqExporterDid?: string;
  projectConvoId: string;
  approvals?: string[];
}

export interface CreateTransferRequestOutput {
  status: "registered" | "alreadyExists" | "rejected";
  transferRequestUri?: string;
  did?: string;
  transferId?: string;
  error?: string;
}

export interface GetTransferRequestInput {
  transferId?: string;
}

export interface GetTransferRequestOutput {
  transferRequest?: TransferRequestView;
  error?: string;
}

// ─── TransferStep tier ──────────────────────────────────────────────

export interface TransferStepRecord {
  transferRequestUri: string;
  transferId: string;
  step: StepName;
  status: StepStatus;
  actorDid?: string;
  /** signal:v1:{ciphertext} — EPP/auth code. NEVER plaintext. */
  authCodeEncrypted?: string;
  /** B2 blob URI for exported BIND zone file (step 4 only). */
  bindZoneFileUri?: string;
  cfTransferId?: string;
  errorMessage?: string;
  occurredAt: string;
  createdAt: string;
}

export interface TransferStepView extends TransferStepRecord {
  transferStepUri: string;
}

export interface PutTransferStepInput {
  transferId: string;
  step: StepName;
  status: StepStatus;
  actorDid?: string;
  authCodeEncrypted?: string;
  bindZoneFileUri?: string;
  cfTransferId?: string;
  errorMessage?: string;
}

export interface PutTransferStepOutput {
  status: "registered" | "alreadyExists" | "rejected" | "requestNotFound";
  transferStepUri?: string;
  transferId?: string;
  step?: StepName;
  error?: string;
}

export interface ListTransferStepsInput {
  transferId?: string;
  limit?: number;
  cursor?: string;
}

export interface ListTransferStepsOutput {
  items: TransferStepView[];
  cursor?: string;
  total: number;
}

// ─── TransferOutcome tier ───────────────────────────────────────────

export interface TransferOutcomeRecord {
  transferRequestUri: string;
  transferId: string;
  domain: string;
  result: OutcomeResult;
  zoneDid?: string;
  cloudflareZoneId?: string;
  failureReason?: string;
  rollbackSteps?: string[];
  completedAt: string;
  createdAt: string;
}

export interface TransferOutcomeView extends TransferOutcomeRecord {
  transferOutcomeUri: string;
}

export interface PutTransferOutcomeInput {
  transferId: string;
  result: OutcomeResult;
  cloudflareZoneId?: string;
  failureReason?: string;
  rollbackSteps?: string[];
}

export interface PutTransferOutcomeOutput {
  status:
    | "registered"
    | "alreadyExists"
    | "rejected"
    | "requestNotFound";
  transferOutcomeUri?: string;
  transferId?: string;
  result?: OutcomeResult;
  zoneDid?: string;
  error?: string;
}

// ─── Orchestration: transferFromSquarespace ─────────────────────────

export interface TransferFromSquarespaceInput {
  transferId: string;
  domain: string;
  requesterDid: string;
  projectConvoId: string;
  approvals: string[];
  cfRegistrarDid?: string;
  sqExporterDid?: string;
}

export interface TransferFromSquarespaceOutput {
  status:
    | "started"
    | "alreadyExists"
    | "rejected"
    | "needsApprovals";
  transferRequestUri?: string;
  transferId?: string;
  error?: string;
}

// ─── Slug helpers ───────────────────────────────────────────────────

export function idSlug(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]/g, "-");
}

export function domainSlug(domain: string): string {
  return domain.toLowerCase().replace(/[^a-z0-9]/g, "-");
}

export function transferRequestDid(transferId: string): string {
  return `${DNS_DID_PREFIX}transfer:${idSlug(transferId)}`;
}

export function transferRequestRkey(transferId: string): string {
  return `transfer-${idSlug(transferId)}`;
}

export function transferStepRkey(transferId: string, step: StepName): string {
  return `step-${idSlug(transferId)}-${step}`;
}

export function transferOutcomeRkey(transferId: string): string {
  return `outcome-${idSlug(transferId)}`;
}

export function zoneDid(domain: string): string {
  return `${DNS_DID_PREFIX}zone:${domainSlug(domain)}`;
}
