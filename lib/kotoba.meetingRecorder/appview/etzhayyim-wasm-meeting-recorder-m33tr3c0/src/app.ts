/**
 * meeting-recorder.etzhayyim.com — Multi-provider meeting recorder control-plane Worker.
 *
 * 6 XRPC procedures + 3 records (com.etzhayyim.apps.meetingRecorder.*):
 *   joinMeeting / leaveMeeting / getSession / listSessions / getTranscript /
 *   getMinutes
 *   + recordingChunk + transcriptSegment + meetingMinutes (records)
 *
 * Architecture (ADR-0050):
 *   - This Worker is the control-plane: XRPC handler + MCP facade (ADR-0042) +
 *     consent JWT verification + graph read.
 *   - Media-plane lives on Vultr VKE LAX (container `meeting-recorder-unix`).
 *     Dispatch is gRPC-over-HTTP through Cloudflare Tunnel hostname
 *     RECORDER_CTRL_ENDPOINT (configured in wrangler.jsonc).
 *   - Writes go direct to Hyperdrive → RisingWave (ADR-0036); the container
 *     also writes recordingChunk / transcriptSegment AT records via PDS.
 *   - PII Tier 3 (ADR-0018): participant display_name + transcript text are
 *     `signal:v1:` field-encrypted; this Worker never decrypts.
 */

import { AsyncLocalStorage } from "node:async_hooks";
import {
  createWorkerExport,
  createKyselyDb,
  nowISO,
  asAgentTool,
  withCapabilityTags,
  nsid,
  parseLexiconInput,
  sql,
  type HostSDK,
} from "@etzhayyim/kotodama-host-sdk";
import { verifySignature, parseDidKey, formatDidKey } from "@atproto/crypto";

const APP_NANOID = "m33tr3c0";
const RECORDER_DID = "did:web:meeting-recorder.etzhayyim.com";

// ── Request-scoped auth ────────────────────────────────────────────────────

interface ReqCtx {
  bearer: string | null;
  accountDid: string | null;
}
const reqAls = new AsyncLocalStorage<ReqCtx>();
const getReqCtx = (): ReqCtx => reqAls.getStore() ?? { bearer: null, accountDid: null };

let _cfEnv: Record<string, unknown> | null = null;
const getVar = (k: string, fallback = ""): string =>
  (_cfEnv?.[k] as string | undefined) ?? fallback;

// ── Consent token validation ───────────────────────────────────────────────

interface ConsentClaims {
  iss: string;
  sub: string;
  aud: string;
  lxm: string;
  meetingRef?: string;
  audio?: boolean;
  video?: boolean;
  transcribe?: boolean;
  purpose?: string;
  exp: number;
  iat?: number;
}

/**
 * Validate consentToken claims (aud / lxm / sub / iss / exp / exp-bound).
 * Structural only — signature verification lives in `verifyConsentSignature`.
 */
function validateConsentClaims(token: string, expectedLxm: string): ConsentClaims {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed JWT");
  let claims: ConsentClaims;
  try {
    const pad = (s: string) => s + "=".repeat((4 - s.length % 4) % 4);
    const json = atob(pad(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    claims = JSON.parse(json) as ConsentClaims;
  } catch {
    throw new Error("JWT payload not decodable");
  }

  if (claims.aud !== RECORDER_DID) throw new Error(`aud mismatch: got ${claims.aud}`);
  if (claims.lxm !== expectedLxm) throw new Error(`lxm mismatch: got ${claims.lxm}`);
  if (!claims.iss || !claims.sub) throw new Error("iss/sub required");
  if (claims.iss !== claims.sub) throw new Error("iss must equal sub (self-delegated)");
  const now = Math.floor(Date.now() / 1000);
  if (!claims.exp || claims.exp <= now) throw new Error("consent expired");
  const maxExp = parseInt(getVar("CONSENT_MAX_EXPIRY_SECONDS", "600"), 10);
  if (claims.exp - now > maxExp) throw new Error(`exp too far in future (> ${maxExp}s)`);
  return claims;
}

// ── ES256 consent signature verification ─────────────────────────────────

interface DidDocument {
  id: string;
  verificationMethod?: Array<{
    id: string;
    type: string;
    controller: string;
    publicKeyJwk?: { kty: string; crv: string; x: string; y: string };
    publicKeyMultibase?: string;
  }>;
}

function b64urlToBytes(s: string): Uint8Array {
  const pad = (x: string) => x + "=".repeat((4 - x.length % 4) % 4);
  const bin = atob(pad(s.replace(/-/g, "+").replace(/_/g, "/")));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function resolveDid(did: string): Promise<DidDocument> {
  const cfCache = { cf: { cacheTtl: 300, cacheEverything: true } } as RequestInit;

  if (did.startsWith("did:web:")) {
    const segs = did.slice("did:web:".length).split(":").map(decodeURIComponent);
    const host = segs[0];
    const path = segs.length > 1 ? "/" + segs.slice(1).join("/") + "/did.json" : "/.well-known/did.json";
    const url = `https://${host}${path}`;
    const res = await fetch(url, cfCache);
    if (!res.ok) throw new Error(`did.json fetch ${url}: ${res.status}`);
    return await res.json<DidDocument>();
  }

  if (did.startsWith("did:etzhayyim:")) {
    // ADR-0029 — did.etzhayyim.com is the canonical resolver.
    // Path convention follows W3C DID Resolution v0.3 but the did string is
    // NOT encodeURIComponent'd (colons preserved) to match the resolver's
    // actual routing (identifiers is routed by exact prefix match).
    const base = getVar("DID_etzhayyim_RESOLVER", "https://did.etzhayyim.com");
    const url = `${base}/1.0/identifiers/${did}`;
    const res = await fetch(url, cfCache);
    if (!res.ok) throw new Error(`did:etzhayyim resolve ${url}: ${res.status}`);
    const body = await res.json<{ didDocument?: DidDocument } & DidDocument>();
    return (body.didDocument ?? (body as DidDocument));
  }

  if (did.startsWith("did:plc:")) {
    // plc.directory accepts the raw did string as the path; encoding breaks it.
    // Override via DID_PLC_RESOLVER if self-hosted (ADR-0014; currently deferred).
    const base = getVar("DID_PLC_RESOLVER", "https://plc.directory");
    const url = `${base}/${did}`;
    const res = await fetch(url, cfCache);
    if (!res.ok) throw new Error(`did:plc resolve ${url}: ${res.status}`);
    return await res.json<DidDocument>();
  }

  throw new Error(`unsupported DID method: ${did}`);
}

/**
 * Extract the signing-capable verificationMethod from a DID Document and
 * synthesize a `did:key:z...` that @atproto/crypto can verify against.
 *
 * Accepts both publicKeyMultibase (atproto native, secp256k1 / P-256 compressed
 * multicodec-prefixed) and publicKeyJwk (P-256). JWK falls back to manual
 * conversion via formatDidKey since @atproto/crypto expects multikey.
 */
function extractDidKey(doc: DidDocument): string {
  // Prefer multibase (atproto native, did:plc / did:etzhayyim / modern did:web).
  const mbVm = doc.verificationMethod?.find((m) => m.publicKeyMultibase?.startsWith("z"));
  if (mbVm?.publicKeyMultibase) return `did:key:${mbVm.publicKeyMultibase}`;

  // Fallback: P-256 publicKeyJwk (common on hand-rolled did:web docs).
  // Convert {x,y} → uncompressed EC point (65 bytes: 0x04 || x || y) →
  // formatDidKey which compresses + multicodec-prefixes + base58btc-encodes.
  const jwkVm = doc.verificationMethod?.find((m) => m.publicKeyJwk?.crv === "P-256");
  if (jwkVm?.publicKeyJwk) {
    const { x, y } = jwkVm.publicKeyJwk;
    const xB = b64urlToBytes(x);
    const yB = b64urlToBytes(y);
    if (xB.length !== 32 || yB.length !== 32) {
      throw new Error(`P-256 JWK x/y must be 32 bytes each (got x=${xB.length}, y=${yB.length})`);
    }
    const uncompressed = new Uint8Array(65);
    uncompressed[0] = 0x04;
    uncompressed.set(xB, 1);
    uncompressed.set(yB, 33);
    return formatDidKey("ES256", uncompressed);
  }

  const found = doc.verificationMethod?.map((m) =>
    m.publicKeyMultibase ? "multibase(non-z)" : m.publicKeyJwk?.crv ?? "?",
  ).join(",") ?? "none";
  throw new Error(`did doc has no supported verificationMethod (found: ${found})`);
}

/**
 * Verify the ES256/ES256K signature on consentToken using the signer DID.
 * Handles did:web / did:plc / did:etzhayyim via resolveDid + @atproto/crypto's
 * verifySignature (secp256k1 via noble-curves, P-256 via WebCrypto).
 *
 * JWT header alg MUST declare ES256 or ES256K; alg=none and RS* downgrade are
 * rejected. JWT alg MUST match the DID key's jwtAlg to prevent substitution.
 */
async function verifyConsentSignature(token: string, signerDid: string): Promise<void> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed JWT");

  let header: { alg?: string };
  try { header = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[0]))); }
  catch { throw new Error("JWT header not decodable"); }
  const alg = header.alg ?? "";
  if (alg !== "ES256" && alg !== "ES256K") {
    throw new Error(`alg must be ES256 or ES256K, got ${alg}`);
  }

  const doc = await resolveDid(signerDid);
  const didKey = extractDidKey(doc);
  const parsed = parseDidKey(didKey);
  if (parsed.jwtAlg !== alg) {
    throw new Error(`JWT alg=${alg} ≠ DID key alg=${parsed.jwtAlg}`);
  }

  const signingInput = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  const sig = b64urlToBytes(parts[2]);
  const ok = await verifySignature(didKey, signingInput, sig);
  if (!ok) throw new Error("signature verification failed");
}

// ── PDS bearer minting (called by Vultr container via /_internal route) ────

/**
 * Mint a short-lived ES256 Service Auth JWT (aud=PDS DID, iss=RECORDER_DID)
 * via AUTH_SERVICE binding. The container's signing key itself stays in
 * AUTH_SERVICE KEK-envelope custody — the container never holds priv keys.
 */
async function mintPdsBearer(lxm: string, ttlSeconds = 600): Promise<{ token: string; expiresAt: number }> {
  const authSvc = _cfEnv?.AUTH_SERVICE as { fetch(r: Request): Promise<Response> } | undefined;
  if (!authSvc) throw new Error("AUTH_SERVICE binding missing");

  const pdsDid = getVar("PDS_DID", "did:web:atproto.etzhayyim.com");
  const res = await authSvc.fetch(new Request("https://authn.etzhayyim.com/xrpc/com.atproto.server.getServiceAuth", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ iss: RECORDER_DID, aud: pdsDid, lxm }),
  }));
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`getServiceAuth failed: ${res.status} ${text}`);
  }
  const { token } = await res.json<{ token: string }>();
  return { token, expiresAt: Math.floor(Date.now() / 1000) + ttlSeconds };
}

/**
 * HMAC-SHA256 validate `x-recorder-auth: {hex(hmac)}` on an internal request.
 * Secret comes from RECORDER_TUNNEL_SECRET (shared via etzhayyim Vault with the
 * Vultr container).
 */
async function verifyInternalHmac(req: Request, body: string): Promise<boolean> {
  const secret = getVar("RECORDER_TUNNEL_SECRET");
  if (!secret) return false;
  const provided = req.headers.get("x-recorder-auth") ?? "";
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expected = Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
  // constant-time compare
  if (expected.length !== provided.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ provided.charCodeAt(i);
  return diff === 0;
}

/** Handle POST /_internal/mint-pds-bearer — called by Vultr container. */
async function handleMintPdsBearer(req: Request): Promise<Response> {
  const body = await req.text();
  if (!await verifyInternalHmac(req, body)) {
    return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });
  }
  try {
    const { lxm, ttlSeconds } = JSON.parse(body) as { lxm: string; ttlSeconds?: number };
    if (!lxm || !lxm.startsWith("com.atproto.")) {
      return new Response(JSON.stringify({ error: "lxm must be com.atproto.*" }), { status: 400 });
    }
    const out = await mintPdsBearer(lxm, ttlSeconds ?? 600);
    return new Response(JSON.stringify(out), { headers: { "content-type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: (e as Error).message }), { status: 500 });
  }
}

// ── gRPC dispatch to Vultr media-plane ─────────────────────────────────────
//
// Uses HTTP+JSON envelope tunneled through Cloudflare Tunnel to the
// meeting-recorder-unix pod. The container's control-plane server accepts
// the same JSON shape for both gRPC and REST callers (grpc-gateway style).

async function dispatchMediaPlane<TReq, TRes>(
  method: "Join" | "Leave" | "Health",
  body: TReq,
): Promise<TRes> {
  const endpoint = getVar("RECORDER_CTRL_ENDPOINT");
  if (!endpoint) throw new Error("RECORDER_CTRL_ENDPOINT not configured");

  const res = await fetch(`${endpoint}/v1/${method.toLowerCase()}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-recorder-caller": RECORDER_DID,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`media-plane ${method} failed: ${res.status} ${text}`);
  }
  return await res.json<TRes>();
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function sessionDidFor(provider: string, externalMeetingId: string): string {
  const safe = externalMeetingId.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 48);
  return `${RECORDER_DID}:session:${provider}:${safe}`;
}

function genSessionId(): string {
  const buf = new Uint8Array(12);
  crypto.getRandomValues(buf);
  let s = "";
  for (const b of buf) s += b.toString(16).padStart(2, "0");
  return `ses_${s}`;
}

function resolveExternalMeetingId(
  provider: string,
  joinTarget: Record<string, unknown>,
): string {
  if (provider === "teams") {
    const url = String(joinTarget.joinUrl ?? "");
    const m = url.match(/19%3ameeting_([^%@/]+)/i) ?? url.match(/meetup-join\/([^/?]+)/i);
    return m?.[1] ?? url.slice(0, 48);
  }
  if (provider === "meet") {
    return String(joinTarget.meetingCode ?? joinTarget.meetingUrl ?? "");
  }
  if (provider === "zoom") {
    return String(joinTarget.meetingId ?? "");
  }
  return "";
}

// ── Command: joinMeeting ───────────────────────────────────────────────────

interface JoinMeetingInput {
  provider: "teams" | "meet" | "zoom";
  joinTarget: Record<string, unknown>;
  onBehalfOfDid: string;
  consentToken: string;
  recordAudio?: boolean;
  recordVideo?: boolean;
  transcribe?: boolean;
  chunkSeconds?: number;
  displayName?: string;
}

async function cmdJoinMeeting(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.joinMeeting", body) as JoinMeetingInput;

  if (!["teams", "meet", "zoom"].includes(input.provider)) {
    return { status: "failed", error: "invalid provider" };
  }
  if (!input.onBehalfOfDid || !input.consentToken) {
    return { status: "failed", error: "onBehalfOfDid + consentToken required" };
  }

  // 1a. Session binding: caller's authenticated accountDid MUST match
  //     onBehalfOfDid. Prevents a logged-in user A from recording on behalf
  //     of another user B even with a valid consent JWT for B.
  const ctx = getReqCtx();
  if (!ctx.accountDid) {
    return { status: "failed", error: "session required (Authorization: Bearer <session JWT>)" };
  }
  if (ctx.accountDid !== input.onBehalfOfDid) {
    return { status: "failed", error: "caller session did ≠ onBehalfOfDid" };
  }

  // 1. Validate consent claims (structural) + verify ES256 signature.
  let claims: ConsentClaims;
  try {
    claims = validateConsentClaims(input.consentToken, "com.etzhayyim.apps.meetingRecorder.joinMeeting");
  } catch (e) {
    return { status: "failed", error: `consent rejected: ${(e as Error).message}` };
  }
  if (claims.sub !== input.onBehalfOfDid) {
    return { status: "failed", error: "consent sub ≠ onBehalfOfDid" };
  }
  try {
    await verifyConsentSignature(input.consentToken, claims.iss);
  } catch (e) {
    return { status: "failed", error: `consent signature invalid: ${(e as Error).message}` };
  }

  // 2. Mint session identity.
  const externalMeetingId = resolveExternalMeetingId(input.provider, input.joinTarget);
  const sessionId = genSessionId();
  const sessionDid = sessionDidFor(input.provider, externalMeetingId);
  const startedAt = nowISO();

  // 3. Record session in graph (Worker-direct Hyperdrive, ADR-0036).
  const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
  const consentJwtHash = await sha256Hex(input.consentToken);

  await db.insertInto("vertex_meetingrecorder_session").values({
    vertex_id: `${sessionDid}#session`,
    session_id: sessionId,
    session_did: sessionDid,
    provider: input.provider,
    external_meeting_id: externalMeetingId,
    on_behalf_of_did: input.onBehalfOfDid,
    consent_jwt_hash: consentJwtHash,
    status: "joining",
    record_audio: input.recordAudio ?? true,
    record_video: input.recordVideo ?? true,
    transcribe: input.transcribe ?? true,
    chunk_seconds: input.chunkSeconds ?? parseInt(getVar("RECORDER_CHUNK_SECONDS_DEFAULT", "60"), 10),
    display_name: input.displayName ?? `etzhayyim Recorder (${input.onBehalfOfDid.slice(-8)})`,
    started_at: startedAt,
  } as never).execute();

  // 4. Dispatch to Vultr media-plane. Include the mint endpoint + shared
  //    secret so the container can refresh PDS bearers over the session
  //    lifetime without holding the recorder's signing key.
  const mintBearerUrl = `${new URL(_cfEnv!.RECORDER_SELF_URL as string ?? "https://meeting-recorder.etzhayyim.com").origin}/_internal/mint-pds-bearer`;
  const tunnelSecret = getVar("RECORDER_TUNNEL_SECRET");
  if (!tunnelSecret) {
    return { sessionId, sessionDid, provider: input.provider, status: "failed",
             error: "RECORDER_TUNNEL_SECRET not configured" };
  }

  try {
    await dispatchMediaPlane<unknown, { status: string }>("Join", {
      sessionId,
      sessionDid,
      provider: input.provider,
      joinTarget: input.joinTarget,
      onBehalfOfDid: input.onBehalfOfDid,
      recordAudio: input.recordAudio ?? true,
      recordVideo: input.recordVideo ?? true,
      transcribe: input.transcribe ?? true,
      chunkSeconds: input.chunkSeconds ?? 60,
      displayName: input.displayName,
      pdsBearerMint: {
        url: mintBearerUrl,
        secret: tunnelSecret,
      },
    });
  } catch (e) {
    await db.updateTable("vertex_meetingrecorder_session")
      .set({ status: "failed", error: (e as Error).message, ended_at: nowISO() } as never)
      .where("session_id", "=", sessionId)
      .execute();
    return { sessionId, sessionDid, provider: input.provider, status: "failed", error: (e as Error).message };
  }

  return {
    sessionDid,
    sessionId,
    provider: input.provider,
    status: "joining",
    startedAt,
  };
}

// ── Command: leaveMeeting ──────────────────────────────────────────────────

async function cmdLeaveMeeting(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.leaveMeeting", body) as {
    sessionId: string; reason?: string; purgeChunks?: boolean;
  };
  const { sessionId, reason = "user_requested", purgeChunks = false } = input;
  if (!sessionId) return { status: "failed", error: "sessionId required" };

  try {
    const res = await dispatchMediaPlane<unknown, { chunksWritten: number; durationMs: number }>(
      "Leave", { sessionId, reason, purgeChunks });

    const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
    const endedAt = nowISO();
    await db.updateTable("vertex_meetingrecorder_session")
      .set({ status: "left", ended_at: endedAt, duration_ms: res.durationMs, leave_reason: reason } as never)
      .where("session_id", "=", sessionId)
      .execute();

    return { sessionId, status: "left", endedAt, chunksWritten: res.chunksWritten, durationMs: res.durationMs };
  } catch (e) {
    return { sessionId, status: "failed", error: (e as Error).message };
  }
}

// ── Query: getSession ──────────────────────────────────────────────────────

async function cmdGetSession(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.getSession", body) as {
    sessionId: string; includeChunks?: boolean; includeParticipants?: boolean;
  };
  const { sessionId, includeChunks = false, includeParticipants = false } = input;
  if (!sessionId) return { error: "sessionId required" };

  const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
  const row = await db.selectFrom("vertex_meetingrecorder_session")
    .selectAll()
    .where("session_id", "=", sessionId)
    .executeTakeFirst() as Record<string, unknown> | undefined;
  if (!row) return { error: "not found" };

  // Access control: caller must match on_behalf_of_did or be explicitly granted.
  const ctx = getReqCtx();
  if (ctx.accountDid && row.on_behalf_of_did !== ctx.accountDid) {
    // TODO: consult consent graph for delegated grants.
    return { error: "forbidden" };
  }

  const out: Record<string, unknown> = {
    sessionId,
    sessionDid: row.session_did,
    provider: row.provider,
    onBehalfOfDid: row.on_behalf_of_did,
    externalMeetingId: row.external_meeting_id,
    status: row.status,
    startedAt: row.started_at,
    endedAt: row.ended_at,
    durationMs: row.duration_ms,
  };

  if (includeChunks) {
    out.chunks = await db.selectFrom("vertex_meetingrecorder_chunk")
      .select(["seq", "kind", "b2_key as b2Key", "sha256", "started_at as startedAt", "duration_ms as durationMs"])
      .where("session_did", "=", String(row.session_did))
      .orderBy("seq", "asc")
      .execute();
  }
  if (includeParticipants) {
    out.participants = await db.selectFrom("vertex_meetingrecorder_participant")
      .select(["participant_did as participantDid", "provider_id_hash as providerIdHash",
               "display_name_cipher as displayNameCipher", "joined_at as joinedAt", "left_at as leftAt"])
      .where("session_did", "=", String(row.session_did))
      .execute();
  }
  return out;
}

// ── Query: listSessions ────────────────────────────────────────────────────

async function cmdListSessions(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.listSessions", body) as {
    onBehalfOfDid: string; provider?: string; status?: string;
    since?: string; until?: string; limit?: number;
  };
  const { onBehalfOfDid, provider, status, since, until, limit = 50 } = input;
  if (!onBehalfOfDid) return { sessions: [] };

  const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
  let q = db.selectFrom("vertex_meetingrecorder_session")
    .select(["session_id as sessionId", "session_did as sessionDid", "provider",
             "status", "started_at as startedAt", "ended_at as endedAt",
             "duration_ms as durationMs"])
    .where("on_behalf_of_did", "=", onBehalfOfDid);

  if (provider) q = q.where("provider", "=", provider);
  if (status) q = q.where("status", "=", status);
  if (since) q = q.where("started_at", ">=", since);
  if (until) q = q.where("started_at", "<=", until);

  const sessions = await q.orderBy("started_at", "desc").limit(Math.min(limit, 200)).execute();
  return { sessions, limit, offset: 0 };
}

// ── Query: getTranscript ───────────────────────────────────────────────────

async function cmdGetTranscript(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.getTranscript", body) as {
    sessionId: string; since?: string; limit?: number;
  };
  const { sessionId, since, limit = 200 } = input;
  if (!sessionId) return { sessionId: "", segments: [] };

  const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
  const sessionRow = await db.selectFrom("vertex_meetingrecorder_session")
    .select(["session_did"])
    .where("session_id", "=", sessionId)
    .executeTakeFirst() as { session_did?: string } | undefined;
  if (!sessionRow?.session_did) return { sessionId, segments: [] };

  let q = db.selectFrom("vertex_meetingrecorder_transcript_seg")
    .select(["seq", "started_at_ms as startedAtMs", "ended_at_ms as endedAtMs",
             "speaker_hash as speakerHash", "lang", "confidence", "text_cipher as textCipher"])
    .where("session_did", "=", sessionRow.session_did);
  if (since) q = q.where("created_at", ">=", since);

  const segments = await q.orderBy("seq", "asc").limit(Math.min(limit, 1000)).execute();
  return { sessionId, segments, limit };
}

// ── Query: getMinutes ──────────────────────────────────────────────────────

async function cmdGetMinutes(sdk: HostSDK, body: Uint8Array) {
  const input = parseLexiconInput("com.etzhayyim.apps.meetingRecorder.getMinutes", body) as {
    sessionId: string;
  };
  const { sessionId } = input;
  if (!sessionId) return { error: "sessionId required" };

  const db = createKyselyDb(_cfEnv!.HYPERDRIVE as never);
  const sessionRow = await db.selectFrom("vertex_meetingrecorder_session")
    .select(["session_did", "on_behalf_of_did"])
    .where("session_id", "=", sessionId)
    .executeTakeFirst() as { session_did?: string; on_behalf_of_did?: string } | undefined;
  if (!sessionRow?.session_did) return { sessionId, error: "not found" };

  // Access control: caller must match on_behalf_of_did (same rule as getSession).
  const ctx = getReqCtx();
  if (ctx.accountDid && sessionRow.on_behalf_of_did !== ctx.accountDid) {
    return { sessionId, error: "forbidden" };
  }

  const row = await db.selectFrom("vertex_meetingrecorder_minutes")
    .select(["session_did as sessionDid", "provider", "lang",
             "summary_cipher as summaryCipher", "decisions_cipher as decisionsCipher",
             "action_items_cipher as actionItemsCipher", "topics_cipher as topicsCipher",
             "participant_hashes as participantHashes", "generator", "model",
             "source_segment_count as sourceSegmentCount", "generated_at as generatedAt"])
    .where("session_did", "=", sessionRow.session_did)
    .orderBy("generated_at", "desc")
    .executeTakeFirst() as Record<string, unknown> | undefined;
  if (!row) return { sessionId, error: "not found" };

  return { sessionId, ...row };
}

// ── sha256 helper ──────────────────────────────────────────────────────────

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ── Worker export ──────────────────────────────────────────────────────────

const _workerInner = createWorkerExport((sdk) => {
  sdk.app
    .command(nsid("com.etzhayyim.apps.meetingRecorder.joinMeeting"),
      (_ctx, body) => cmdJoinMeeting(sdk, body),
      asAgentTool("Dispatch the recorder bot to join a Teams / Meet / Zoom meeting. Requires a consentToken (ES256 JWT, lxm=com.etzhayyim.apps.meetingRecorder.joinMeeting) signed by the on-behalf-of user."),
      withCapabilityTags("record", "write", "consent-gated", "adr-0050"))
    .command(nsid("com.etzhayyim.apps.meetingRecorder.leaveMeeting"),
      (_ctx, body) => cmdLeaveMeeting(sdk, body),
      asAgentTool("Instruct the bot to leave a meeting, flush chunks to B2, and finalize the session."),
      withCapabilityTags("record", "write"))
    .command(nsid("com.etzhayyim.apps.meetingRecorder.getSession"),
      (_ctx, body) => cmdGetSession(sdk, body),
      asAgentTool("Fetch session metadata. Caller must be onBehalfOfDid."),
      withCapabilityTags("record", "query"))
    .command(nsid("com.etzhayyim.apps.meetingRecorder.listSessions"),
      (_ctx, body) => cmdListSessions(sdk, body),
      asAgentTool("List recorder sessions for an on-behalf-of DID."),
      withCapabilityTags("record", "query"))
    .command(nsid("com.etzhayyim.apps.meetingRecorder.getTranscript"),
      (_ctx, body) => cmdGetTranscript(sdk, body),
      asAgentTool("Fetch transcript segments (signal:v1: encrypted). Caller decrypts client-side."),
      withCapabilityTags("record", "query", "e2e-encrypted"))
    .command(nsid("com.etzhayyim.apps.meetingRecorder.getMinutes"),
      (_ctx, body) => cmdGetMinutes(sdk, body),
      asAgentTool("Fetch generated meeting minutes 議事録 for a session (signal:v1: encrypted content; same session key as the transcript). Caller must be onBehalfOfDid and decrypts client-side."),
      withCapabilityTags("record", "query", "e2e-encrypted"));
});

/** Capture Bearer + accountDid per request before delegating to host-sdk. */
export default {
  async fetch(req: Request, env: Record<string, unknown>, ctx: ExecutionContext): Promise<Response> {
    _cfEnv = env;

    // Container ↔ Worker internal route: PDS bearer minting (HMAC-auth).
    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/_internal/mint-pds-bearer") {
      return handleMintPdsBearer(req);
    }

    const bearer = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? null;
    const accountDid = accountDidFromBearer(bearer);
    return reqAls.run({ bearer, accountDid }, () => _workerInner.fetch(req, env, ctx));
  },
};

function accountDidFromBearer(bearer: string | null): string | null {
  if (!bearer) return null;
  const parts = bearer.split(".");
  if (parts.length !== 3) return null;
  try {
    const pad = (s: string) => s + "=".repeat((4 - s.length % 4) % 4);
    const json = atob(pad(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    const payload = JSON.parse(json) as { accountDid?: string; did?: string; sub?: string };
    return payload.accountDid ?? payload.did ?? payload.sub ?? null;
  } catch {
    return null;
  }
}
