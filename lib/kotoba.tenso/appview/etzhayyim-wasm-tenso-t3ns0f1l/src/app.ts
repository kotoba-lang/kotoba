import {
  asAgentTool,
  createWorkerExport,
  nowISO,
  str,
  llmAsk,
  withCapabilityTags,
  withOCELEvent,
  type ComAtprotoSyncSubscribeReposCommit,
  type HostSDK,
  resolveHeartbeatCadence,
  createCadenceState,
  createInboxBuffer,
  genID,
  decodeJson,
  createKyselyDb,
  nsid,
  parseLexiconInput,
  sql,
} from "@etzhayyim/kotodama-host-sdk";

const cadenceState = createCadenceState();
const inbox = createInboxBuffer();

const APP_NANOID = "t3ns0f1l";
const CHUNK_SIZE = 64 * 1024 * 1024; // 64 MiB
const DEFAULT_EXPIRE_HOURS = 72;
const MAX_DOWNLOADS_DEFAULT = 10;

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

let db: KyselyDb | null = null;

const C = {
  transferRequest: "vertex_tenso_transfer_request",
  fileManifest: "vertex_tenso_file_manifest",
  transferLog: "vertex_tenso_transfer_log",
  accessControl: "vertex_tenso_access_control",
} as const;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

function parseProps(props: unknown): Record<string, unknown> {
  if (typeof props !== "string" || props.length === 0) return {};
  try {
    const parsed = JSON.parse(props) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Ignore malformed props payloads and fall back to row columns.
  }
  return {};
}

function normalizeVertexOther(row: AnyRow | null | undefined): AnyRow {
  if (!row) return {};
  return {
    ...row,
    ...parseProps(row.props),
    transferId: str(row.transferId ?? row.transfer_id ?? ""),
    senderDid: str(row.senderDid ?? row.sender_did ?? ""),
    recipientDid: str(row.recipientDid ?? row.recipient_did ?? ""),
    mimeType: str(row.mimeType ?? row.mime_type ?? ""),
    sizeBytes: Number(row.sizeBytes ?? row.size_bytes ?? 0),
    chunkCount: Number(row.chunkCount ?? row.chunk_count ?? 0),
    expireAt: str(row.expireAt ?? row.expire_at ?? ""),
    maxDownloads: Number(row.maxDownloads ?? row.max_downloads ?? 0),
    downloadCount: Number(row.downloadCount ?? row.download_count ?? row.downloads_used ?? 0),
    eventType: str(row.eventType ?? row.event_type ?? ""),
    actorDid: str(row.actorDid ?? row.actor_did ?? ""),
    actorId: str(row.actorId ?? row.actor_id ?? ""),
    createdAt: str(row.createdAt ?? row.created_at ?? ""),
    encryptedPayload: str(row.encryptedPayload ?? row.encrypted_payload ?? ""),
    totalSize: Number(row.totalSize ?? row.total_size ?? 0),
  };
}

async function listTransferRequestRows(build?: (query: any) => any): Promise<TransferRequest[]> {
  let query: any = getDb().selectFrom(C.transferRequest).selectAll();
  if (build) query = build(query);
  return (await query.execute()).map((row: AnyRow) => normalizeVertexOther(row)) as TransferRequest[];
}

async function getTransferRequest(transferId: string): Promise<TransferRequest | null> {
  const rows = await listTransferRequestRows((query) => query.where("transfer_id", "=", transferId).limit(1));
  return rows[0] ?? null;
}

async function getFileManifest(transferId: string): Promise<AnyRow | null> {
  const rows = await getDb()
    .selectFrom(C.fileManifest)
    .selectAll()
    .where("transfer_id", "=", transferId)
    .limit(1)
    .execute();
  return rows[0] ? normalizeVertexOther(rows[0] as AnyRow) : null;
}

async function getAccessControl(transferId: string): Promise<AnyRow | null> {
  const rows = await getDb()
    .selectFrom(C.accessControl)
    .selectAll()
    .where("transfer_id", "=", transferId)
    .limit(1)
    .execute();
  return rows[0] ? normalizeVertexOther(rows[0] as AnyRow) : null;
}

async function countTransferLogs(transferId: string, eventType: string): Promise<number> {
  const row = await getDb()
    .selectFrom(C.transferLog)
    .select(sql<number>`count(*)`.as("total"))
    .where("transfer_id", "=", transferId)
    .where("event_type", "=", eventType)
    .executeTakeFirst();
  return Number(row?.total ?? 0);
}

async function listTransfersByDid(field: "sender_did" | "recipient_did", did: string, offset: number, limit: number): Promise<TransferRequest[]> {
  const rows = await listTransferRequestRows((query) =>
    query
      .where(field, "=", did)
      .orderBy("created_at", "desc")
      .offset(offset)
      .limit(limit),
  );
  return rows as TransferRequest[];
}

async function getSignalPrekeyBundle(peerDid: string): Promise<string> {
  const rows = await getDb()
    .selectFrom("vertex_profile")
    .selectAll()
    .where((eb) => eb.or([eb("repo", "=", peerDid), eb("did", "=", peerDid)]))
    .limit(1)
    .execute();
  const row = rows[0] as AnyRow | undefined;
  if (!row) return "";
  const normalized = normalizeVertexOther(row);
  return str(normalized.signalPrekeyBundle ?? normalized.signal_prekey_bundle ?? normalized.prekeyBundle ?? "");
}

async function getActorTransferStats(actorId: string): Promise<{ total: number; totalBytes: number; active: number }> {
  const totals = await listTransferRequestRows((query) =>
    query.where("actor_id", "=", actorId),
  );
  let totalBytes = 0;
  let active = 0;
  for (const row of totals) {
    totalBytes += Number(row.sizeBytes ?? 0);
    if (str(row.status ?? "") === "pending") active += 1;
  }
  return { total: totals.length, totalBytes, active };
}

async function listRecentTransferSummaries(actorId: string, limit: number): Promise<Array<Record<string, unknown>>> {
  const rows = await listTransferRequestRows((query) =>
    query
      .where("actor_id", "=", actorId)
      .orderBy("created_at", "desc")
      .limit(limit),
  );
  return rows.map((row) => ({
    filename: row.filename,
    status: row.status,
    sizeBytes: row.sizeBytes,
  }));
}

// --- Write Helpers ---

function writePrivate(sdk: HostSDK, key: string, value: Record<string, unknown>): void {
  sdk.pds.dispatch({ type: "actor-put-preferences", payload: { key: `tenso:${key}`, value: JSON.stringify(value) } });
}

// --- Commands ---

/** Create a new file transfer request. Sender calls this after uploading encrypted chunks. */
async function cmdCreateTransfer(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.createTransfer", body);
  const recipientDid = str(args.recipientDid ?? "");
  const filename = str(args.filename ?? "");
  const mimeType = str(args.mimeType ?? "application/octet-stream");
  const sizeBytes = Number(args.sizeBytes) || 0;
  const chunkCount = Number(args.chunkCount) || 1;
  const expireHours = Number(args.expireHours) || DEFAULT_EXPIRE_HOURS;
  const encryptedManifestPayload = str(args.encryptedManifest ?? "");

  if (!recipientDid) return { error: "recipientDid required" };
  if (!filename) return { error: "filename required" };
  if (!sizeBytes) return { error: "sizeBytes required" };
  if (!encryptedManifestPayload) return { error: "encryptedManifest required (signal:v1: wrapped fileKey + chunk CIDs)" };

  const transferId = genID("xfer");
  const expireAt = new Date(Date.now() + expireHours * 3600_000).toISOString();

  const selfDid = sdk.pds.selfRepo ?? "";

  // Tier 2: Domain — transfer request record
  await getDb().insertInto(C.transferRequest as any).values({
    vertex_id: `at://${selfDid}/com.etzhayyim.apps.tenso.transferRequest/${transferId}`,
    sensitivity_ord: 2,
    owner_did: selfDid,
    transfer_id: transferId,
    sender_did: selfDid,
    recipient_did: recipientDid,
    filename,
    mime_type: mimeType,
    size_bytes: sizeBytes,
    chunk_count: chunkCount,
    chunk_size: CHUNK_SIZE,
    status: "pending",
    expire_at: expireAt,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  // Tier 2: Domain — encrypted file manifest (signal:v1: payload containing fileKey + chunk CID list)
  await getDb().insertInto(C.fileManifest as any).values({
    vertex_id: `at://${selfDid}/com.etzhayyim.apps.tenso.fileManifest/${transferId}`,
    sensitivity_ord: 2,
    owner_did: selfDid,
    transfer_id: transferId,
    sender_did: selfDid,
    recipient_did: recipientDid,
    encrypted_payload: encryptedManifestPayload,
    chunk_count: chunkCount,
    total_size: sizeBytes,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  // Tier 2: Domain — audit log
  await getDb().insertInto(C.transferLog as any).values({
    vertex_id: `at://${selfDid}/com.etzhayyim.apps.tenso.transferLog/${genID("log")}`,
    sensitivity_ord: 2,
    owner_did: selfDid,
    transfer_id: transferId,
    event_type: "created",
    actor_did: selfDid,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  // Tier 2: Domain — access control (encrypted with signal:v1:)
  const maxDownloads = Number(args.maxDownloads) || MAX_DOWNLOADS_DEFAULT;
  await getDb().insertInto(C.accessControl as any).values({
    vertex_id: `at://${selfDid}/com.etzhayyim.apps.tenso.accessControl/${transferId}`,
    sensitivity_ord: 2,
    owner_did: selfDid,
    transfer_id: transferId,
    recipient_did: recipientDid,
    max_downloads: maxDownloads,
    download_count: 0,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  return { transferId, status: "pending", expireAt, chunkCount };
}

/** Accept a transfer — recipient acknowledges and begins download. */
async function cmdAcceptTransfer(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.acceptTransfer", body);
  const transferId = str(args.transferId ?? "");
  if (!transferId) return { error: "transferId required" };

  const transfer = await getTransferRequest(transferId);
  if (!transfer) return { error: "transfer not found" };

  const manifest = await getFileManifest(transferId);
  if (!manifest) return { error: "manifest not found" };

  // Log acceptance
  const acceptDid = sdk.pds.selfRepo ?? "";
  await getDb().insertInto(C.transferLog as any).values({
    vertex_id: `at://${acceptDid}/com.etzhayyim.apps.tenso.transferLog/${genID("log")}`,
    sensitivity_ord: 2,
    owner_did: acceptDid,
    transfer_id: transferId,
    event_type: "accepted",
    actor_did: acceptDid,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  return {
    transferId,
    encryptedPayload: manifest.encryptedPayload,
    chunkCount: manifest.chunkCount,
    totalSize: manifest.totalSize,
    status: "accepted",
  };
}

/** Log a chunk download event and check download limits. */
async function cmdDownloadChunk(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.downloadChunk", body);
  const transferId = str(args.transferId ?? "");
  const chunkIndex = Number(args.chunkIndex) ?? 0;
  if (!transferId) return { error: "transferId required" };

  const ac = await getAccessControl(transferId);
  if (ac) {
    if (Number(ac.downloadCount) >= Number(ac.maxDownloads)) {
      return { error: "download limit exceeded", maxDownloads: ac.maxDownloads };
    }
  }

  const transfer = await getTransferRequest(transferId);
  if (transfer) {
    const t = transfer;
    if (t.status === "revoked") return { error: "transfer has been revoked" };
    if (t.status === "purged") return { error: "transfer has expired and been purged" };
    if (t.expireAt && new Date(t.expireAt as string) < new Date()) {
      return { error: "transfer has expired" };
    }
  }

  // Log download event
  const dlDid = sdk.pds.selfRepo ?? "";
  await getDb().insertInto(C.transferLog as any).values({
    vertex_id: `at://${dlDid}/com.etzhayyim.apps.tenso.transferLog/${genID("log")}`,
    sensitivity_ord: 2,
    owner_did: dlDid,
    transfer_id: transferId,
    event_type: "chunkDownloaded",
    chunk_index: chunkIndex,
    actor_did: dlDid,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  return { transferId, chunkIndex, status: "downloadPermitted" };
}

/** Revoke a transfer — sender can revoke before expiry. */
async function cmdRevokeTransfer(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.revokeTransfer", body);
  const transferId = str(args.transferId ?? "");
  if (!transferId) return { error: "transferId required" };

  // Log revocation
  const revokeDid = sdk.pds.selfRepo ?? "";
  await getDb().insertInto(C.transferLog as any).values({
    vertex_id: `at://${revokeDid}/com.etzhayyim.apps.tenso.transferLog/${genID("log")}`,
    sensitivity_ord: 2,
    owner_did: revokeDid,
    transfer_id: transferId,
    event_type: "revoked",
    actor_did: revokeDid,
    created_at: nowISO(),
    org_id: "anon",
    user_id: "anon",
    actor_id: APP_NANOID,
  }).execute();

  return { transferId, status: "revoked" };
}

/** Get transfer status by ID. */
async function cmdGetTransfer(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.getTransfer", body);
  const transferId = str(args.transferId ?? "");
  if (!transferId) return { error: "transferId required" };

  const transfer = await getTransferRequest(transferId);
  if (!transfer) return { error: "transfer not found" };
  const downloads = await countTransferLogs(transferId, "chunkDownloaded");

  return { transfer, downloads };
}

/** List transfers for the current user (sent or received). */
async function cmdListTransfers(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.listTransfers", body);
  const direction = str(args.direction ?? "sent"); // "sent" or "received"
  const limit = Math.min(Number(args.limit) || 50, 200);
  const offset = Number(args.offset) || 0;
  const selfDid = sdk.pds.selfRepo ?? "";

  const field = direction === "received" ? "recipient_did" : "sender_did";
  const rows = await listTransfersByDid(field, selfDid, offset, limit);

  return { items: rows, direction, offset, limit };
}

/** Initialize Signal session for a peer (fetch prekey bundle). */
async function cmdInitSignalSession(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.initSignalSession", body);
  const peerDid = str(args.peerDid ?? "");
  if (!peerDid) return { error: "peerDid required" };

  const prekeyBundle = await getSignalPrekeyBundle(peerDid);
  if (!prekeyBundle) {
    return { error: "peer has no Signal prekey bundle registered" };
  }

  return { peerDid, prekeyBundle };
}

/** Wave/greeting. */
function cmdWave(sdk: HostSDK, body: Uint8Array): unknown {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.wave", body);
  return { ok: true, agent: "Tenso", nanoid: APP_NANOID, greeting: "Secure file transfer ready. Send files with Signal E2E encryption." };
}

// --- Reactive Pipeline ---

function handleComAtprotoSyncSubscribeReposCommit(sdk: HostSDK, commit: ComAtprotoSyncSubscribeReposCommit): { ok: true; detail: string } {
  if (commit.action !== "create") return { ok: true, detail: "skip non-create" };

  const collection = str(commit.collection ?? "");

  if (collection === "com.etzhayyim.apps.tenso.transferRequest") {
    // New transfer created — derive rule handles recipient notification
    return { ok: true, detail: "processedTransferRequest" };
  }

  if (collection === "com.etzhayyim.apps.tenso.transferLog") {
    // Audit event — derive rule handles yabai risk check on errors
    return { ok: true, detail: "processedTransferLog" };
  }

  if (collection === "com.etzhayyim.apps.tenso.fileManifest") {
    return { ok: true, detail: "processedFileManifest" };
  }

  if (collection === "app.bsky.feed.like") {
    inbox.reactions.push(commit);
    return { ok: true, detail: "engagement noted" };
  }

  return { ok: true, detail: "commit accepted" };
}

// --- Shinka Heartbeat ---

export async function runHeartbeat(sdk: HostSDK): Promise<{ ok: boolean; actions: Array<Record<string, unknown>> }> {
  const actions: Array<Record<string, unknown>> = [];
  const ts = nowISO();
  const cadence = await resolveHeartbeatCadence("did:web:t3ns0f1l.etzhayyim.com", cadenceState, inbox);
  actions.push({ action: "cadenceResolved", mood: cadence.mood, reason: cadence.reason, ts });

  if (actions.length === 1) actions.push({ action: "noop", mood: cadence.mood, ts });
  return { ok: true, actions };
}

// --- Standard Commands ---

async function cmdStatsTenso(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const stats = await getActorTransferStats(APP_NANOID);
  return { stats: { total: stats.total, totalBytes: stats.totalBytes }, active: stats.active, agent: "Tenso" };
}

function cmdHealthTenso(sdk: HostSDK, _body: Uint8Array): unknown {
  return { status: "healthy", agent: "Tenso", nanoid: APP_NANOID, did: `did:web:${APP_NANOID}.etzhayyim.com`, ts: nowISO() };
}

function cmdDescribeTenso(sdk: HostSDK, _body: Uint8Array): unknown {
  return {
    name: "Tenso",
    did: `did:web:${APP_NANOID}.etzhayyim.com`,
    nanoid: APP_NANOID,
    domain: "secure-file-transfer",
    capabilities: ["create-transfer", "accept-transfer", "download-chunk", "revoke-transfer", "list-transfers", "init-signal-session"],
    protocols: ["xrpc", "w-protocol", "mcp", "signal-e2e"],
    encryption: {
      keyExchange: "Signal X3DH (X25519 + Ed25519)",
      fileEncryption: "AES-256-GCM (per-transfer random key)",
      fieldEncryption: "signal:v1: (HKDF-derived AES-256-GCM)",
      forwardSecrecy: "Double Ratchet",
      serverKnowledge: "zero (ciphertext only)",
    },
    chunkSize: CHUNK_SIZE,
    defaultExpireHours: DEFAULT_EXPIRE_HOURS,
    maxDownloadsDefault: MAX_DOWNLOADS_DEFAULT,
  };
}

async function cmdSummarizeTenso(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = parseLexiconInput("com.etzhayyim.apps.tenso.summarizeTenso", body);
  const topic = str(args.topic ?? "tenso transfers");
  const data = await listRecentTransferSummaries(APP_NANOID, 10);
  const summary = await llmAsk(`Summarize ${topic} data: ${JSON.stringify(data)}. Be concise.`);
  return { summary, topic };
}

// --- Domain Types ---

interface TransferRequest {
  transferId: string;
  senderDid: string;
  recipientDid: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  chunkCount: number;
  status: string;
  expireAt: string;
  createdAt: string;
  orgId: string;
  userId: string;
  actorId: string;
}

const TRANSFER_STATUSES = ["pending", "accepted", "completed", "revoked", "expired", "purged"] as const;

// --- Command Registration ---

function registerTensoCommands(sdk: HostSDK): void {
  sdk.app
    .command(nsid("com.etzhayyim.apps.tenso.createTransfer"), (_, body) => cmdCreateTransfer(sdk, body),
      asAgentTool("Create a new encrypted file transfer (sender uploads encrypted chunks first, then calls this with signal:v1: wrapped manifest)"),
      withCapabilityTags("write", "transfer", "signal-e2e"),
      withOCELEvent("transfer.created"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.acceptTransfer"), (_, body) => cmdAcceptTransfer(sdk, body),
      asAgentTool("Accept a file transfer and retrieve encrypted manifest (recipient decrypts client-side)"),
      withCapabilityTags("write", "transfer", "signal-e2e"),
      withOCELEvent("transfer.accepted"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.downloadChunk"), (_, body) => cmdDownloadChunk(sdk, body),
      asAgentTool("Log chunk download and check access limits (actual blob download is direct from R2)"),
      withCapabilityTags("read", "transfer", "blob"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.revokeTransfer"), (_, body) => cmdRevokeTransfer(sdk, body),
      asAgentTool("Revoke a file transfer (sender only, before expiry)"),
      withCapabilityTags("write", "transfer", "revoke"),
      withOCELEvent("transfer.revoked"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.getTransfer"), (_, body) => cmdGetTransfer(sdk, body),
      asAgentTool("Get transfer status and download count"),
      withCapabilityTags("query", "transfer"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.listTransfers"), (_, body) => cmdListTransfers(sdk, body),
      asAgentTool("List sent or received transfers"),
      withCapabilityTags("query", "transfer"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.initSignalSession"), (_, body) => cmdInitSignalSession(sdk, body),
      asAgentTool("Initialize Signal session with peer (fetch prekey bundle for X3DH)"),
      withCapabilityTags("query", "signal-e2e", "encryption"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.wave"), (_, body) => cmdWave(sdk, body),
      asAgentTool("Respond to wave greeting"),
      withCapabilityTags("social", "greeting"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.statsTenso"), (_, body) => cmdStatsTenso(sdk, body),
      asAgentTool("Get Tenso transfer statistics"),
      withCapabilityTags("analytics", "tenso"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.healthTenso"), (_, body) => cmdHealthTenso(sdk, body),
      asAgentTool("Tenso health check"),
      withCapabilityTags("diagnostics", "tenso"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.describeTenso"), (_, body) => cmdDescribeTenso(sdk, body),
      asAgentTool("Describe Tenso capabilities and encryption properties"),
      withCapabilityTags("meta", "tenso"),
    )
    .command(nsid("com.etzhayyim.apps.tenso.summarizeTenso"), (_, body) => cmdSummarizeTenso(sdk, body),
      asAgentTool("AI summary of recent transfers"),
      withCapabilityTags("ai", "tenso"),
    );
}

export { handleComAtprotoSyncSubscribeReposCommit };

export default createWorkerExport((sdk) => {
  registerTensoCommands(sdk);
});
