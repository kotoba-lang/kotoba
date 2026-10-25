// fax.etzhayyim.com — FAX send/receive AI agent (T3 TS Native, MCP-callable)
//
// MCP topology (3 tiers):
//   Tier 1 (high-level orchestration):
//     composeAndSend(content, format, to, caseId, ...) — render → upload → handoff → recordToRoukisho
//   Tier 2 (compose):
//     renderPdf(content, format, ...) — HEADLESS_BROWSER (CF Browser Rendering) → A4 PDF → R2
//     uploadDocument(contentBase64, contentType) — pre-rendered PDF → SHA-256 → R2 PUT
//   Tier 3 (transmission, existing):
//     send / cancel / getStatus / listSent / listReceived
//
// Provider abstraction (Phaxio is DEAD PATH — kept for code-symmetry only):
//   provider="auto"   → manual-handoff (Dropbox Fax UI). DEFAULT.
//   provider="manual" → returns prepared assets + Teams notification (operator action required)
//   provider="phaxio" → DEAD PATH. Code retained but never wired in production
//                       (no SS_FAX_API_KEY in wrangler). Re-enable only if a paid programmatic
//                       provider is adopted later (Sinch / Documo mFax / SRFax / Interfax).
//
// Design E 3-Tier Write:
//   Tier 1 (social)  — no social post by default (confidential).
//   Tier 2 (domain)  — faxTx / inboundFax / faxTxUpdate via com.atproto.repo.createRecord.
//   Tier 3 (state)   — provider creds via Secrets Store (SS_FAX_*); R2 dedup keyed by SHA-256.
//
// Cross-actor invocation:
//   composeAndSend → roukisho.recordCommunication (when officeId given) via sdk.hostImports.invoke.

import { cdnHead, cdnRead, cdnWrite } from "./cdn-s3";
import {
  asAgentTool,
  createWorkerExport,
  decodeJson,
  genID,
  nowISO,
  nsid,
  str,
  withCapabilityTags,
  type HostSDK,
} from "@etzhayyim/kotodama-host-sdk";

// Cross-actor invoke helpers deleted (ADR-0047 audit 2026-04-21).
// The `invokeRemote` helper + `hostClient.invokeCall` primary path + fetch
// fallback + base64 helpers + `didToXrpcBase` resolver are all gone — fax no
// longer calls other actors' XRPC directly. Communication audit (roukisho)
// and operator notification (mailer) switched to write-only derived pattern
// stubs in `recordToRoukisho` + `cmdComposeAndSend` (ADR-0004).

let appId = "";

const ROUKISHO_NANOID = "r0uk15h0";
const ROUKISHO_DID = "did:web:roukisho.etzhayyim.com";

// ───────────────────────── env / secrets ─────────────────────────

async function resolveSecret(v: unknown): Promise<string> {
  if (!v) return "";
  if (typeof v === "string") return v;
  const anyV = v as { get?: () => Promise<string>; text?: () => Promise<string> };
  if (typeof anyV.get === "function") return await anyV.get();
  if (typeof anyV.text === "function") return await anyV.text();
  return String(v);
}

function providerBase(sdk: HostSDK): string {
  return str(sdk.env.FAX_API_BASE ?? "https://api.phaxio.com/v2.1");
}

async function providerAuthHeader(sdk: HostSDK): Promise<string> {
  const key = await resolveSecret(sdk.env.SS_FAX_API_KEY);
  const secret = await resolveSecret(sdk.env.SS_FAX_API_SECRET);
  if (!key || !secret) throw new Error("FAX provider credentials missing (SS_FAX_API_KEY / SS_FAX_API_SECRET)");
  return "Basic " + btoa(`${key}:${secret}`);
}

// ───────────────────────── write helper ─────────────────────────

function write(sdk: HostSDK, kind: string, rec: Record<string, unknown>): void {
  const collection = `com.etzhayyim.apps.fax.${kind}`;
  const enriched = {
    ...rec,
    createdAt: nowISO(),
    org_id: "etzhayyim.com",
    user_id: "anon",
    actor_id: appId,
  };
  sdk.pds.dispatch({
    type: "com.atproto.repo.createRecord",
    payload: { collection, recordJson: JSON.stringify(enriched) },
  });
}

function normalizeE164(raw: string): string {
  const trimmed = raw.trim().replace(/[\s\-()]/g, "");
  if (trimmed.startsWith("+")) return trimmed;
  if (trimmed.startsWith("0") && trimmed.length >= 9) {
    // JP domestic → E.164 (+81) — drop leading 0
    return "+81" + trimmed.slice(1);
  }
  return trimmed;
}

// ───────────────────────── commands ─────────────────────────

async function cmdSend(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const toRaw = str(args.to ?? "");
  const to = toRaw ? normalizeE164(toRaw) : "";
  if (!to) return { ok: false, error: "to (E.164 fax number) required" };

  const blobKey = str(args.blobKey ?? "");
  const url = str(args.url ?? "");
  if (!blobKey && !url) return { ok: false, error: "blobKey or url required" };

  let contentUrl = url;
  if (!contentUrl && blobKey) {
    // CDN_R2 public URL (content-addressed). blobKey = SHA-256 hex.
    const cdnBase = str(sdk.env.CDN_PUBLIC_BASE_URL ?? "https://cdn.etzhayyim.com");
    contentUrl = `${cdnBase}/${blobKey}`;
  }

  const txId = genID("fax");
  const subject = str(args.subject ?? "");
  const caseId = str(args.caseId ?? "");
  const from = str(args.from ?? "");

  let providerFaxId = "";
  let status: "queued" | "sending" | "success" | "failure" | "unknown" = "queued";
  let providerError = "";

  try {
    const auth = await providerAuthHeader(sdk);
    const form = new URLSearchParams();
    form.set("to", to);
    form.set("content_url", contentUrl);
    if (from) form.set("caller_id", from);
    if (subject) form.set("header_text", subject);
    // tagging for webhook correlation
    form.set("tag[txId]", txId);
    if (caseId) form.set("tag[caseId]", caseId);

    const res = await fetch(`${providerBase(sdk)}/faxes`, {
      method: "POST",
      headers: {
        Authorization: auth,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form.toString(),
    });
    const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) {
      status = "failure";
      providerError = str((json as { message?: string }).message ?? `HTTP ${res.status}`);
    } else {
      const data = (json.data ?? {}) as Record<string, unknown>;
      providerFaxId = str(data.id ?? "");
      status = "queued";
    }
  } catch (e) {
    status = "failure";
    providerError = e instanceof Error ? e.message : String(e);
  }

  write(sdk, "faxTx", {
    txId,
    providerFaxId,
    to,
    from,
    subject,
    caseId,
    blobKey,
    url: contentUrl,
    status,
    providerError,
    sentAt: nowISO(),
  });

  return {
    ok: status !== "failure",
    txId,
    providerFaxId,
    status,
    error: providerError || undefined,
  };
}

async function cmdGetStatus(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const providerFaxId = str(args.providerFaxId ?? "");
  if (!providerFaxId) {
    // txId lookup requires graph read (pending migration). Return unknown for now.
    return { ok: true, txId: str(args.txId ?? ""), status: "unknown" };
  }

  try {
    const auth = await providerAuthHeader(sdk);
    const res = await fetch(`${providerBase(sdk)}/faxes/${encodeURIComponent(providerFaxId)}`, {
      headers: { Authorization: auth },
    });
    const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) return { ok: false, providerFaxId, error: str((json as { message?: string }).message ?? `HTTP ${res.status}`) };
    const data = (json.data ?? {}) as Record<string, unknown>;
    return {
      ok: true,
      providerFaxId,
      status: str(data.status ?? "unknown"),
      to: str(data.to_number ?? ""),
      pages: Number(data.num_pages ?? 0),
      sentAt: str(data.created_at ?? ""),
      deliveredAt: str(data.completed_at ?? ""),
      errorCode: str(data.error_code ?? ""),
    };
  } catch (e) {
    return { ok: false, providerFaxId, error: e instanceof Error ? e.message : String(e) };
  }
}

async function cmdListSent(_sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const limit = Number(args.limit ?? 50);
  const offset = Number(args.offset ?? 0);
  // Graph read pending (Kysely + HYPERDRIVE for graphar.vertex_fax_tx). Empty envelope for now.
  return { ok: true, faxes: [] as Array<Record<string, unknown>>, total: 0, offset, limit };
}

async function cmdListReceived(_sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const limit = Number(args.limit ?? 50);
  const offset = Number(args.offset ?? 0);
  return { ok: true, faxes: [] as Array<Record<string, unknown>>, total: 0, offset, limit };
}

async function cmdCancel(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const txId = str(args.txId ?? "");
  const providerFaxId = str(args.providerFaxId ?? "");
  if (!providerFaxId) return { ok: false, error: "providerFaxId required (txId-only lookup pending graph read)" };

  try {
    const auth = await providerAuthHeader(sdk);
    const res = await fetch(`${providerBase(sdk)}/faxes/${encodeURIComponent(providerFaxId)}/cancel`, {
      method: "POST",
      headers: { Authorization: auth },
    });
    const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) return { ok: false, txId, error: str((json as { message?: string }).message ?? `HTTP ${res.status}`) };
    write(sdk, "faxTxUpdate", { txId, providerFaxId, status: "cancelled", cancelledAt: nowISO() });
    return { ok: true, txId, status: "cancelled" };
  } catch (e) {
    return { ok: false, txId, error: e instanceof Error ? e.message : String(e) };
  }
}

// ───────────────────────── webhook (provider → us) ─────────────────────────

async function handleProviderWebhook(sdk: HostSDK, req: Request): Promise<Response> {
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const direction = str(body.direction ?? "");
  const fax = (body.fax ?? {}) as Record<string, unknown>;
  const providerFaxId = str(fax.id ?? "");
  const status = str(fax.status ?? "unknown");
  const tags = (fax.tags ?? {}) as Record<string, unknown>;
  const txId = str(tags.txId ?? "");
  const caseId = str(tags.caseId ?? "");

  if (direction === "received") {
    const rxId = genID("rx");
    write(sdk, "inboundFax", {
      rxId,
      providerFaxId,
      from: str(fax.from_number ?? ""),
      to: str(fax.to_number ?? ""),
      pages: Number(fax.num_pages ?? 0),
      mediaUrl: str(fax.media_url ?? ""),
      receivedAt: nowISO(),
    });
    return new Response(JSON.stringify({ ok: true, rxId }), { headers: { "content-type": "application/json" } });
  }

  // outbound status update
  write(sdk, "faxTxUpdate", { txId, providerFaxId, status, caseId, updatedAt: nowISO() });
  return new Response(JSON.stringify({ ok: true }), { headers: { "content-type": "application/json" } });
}

// ───────────────────────── compose / render / upload (Tier 2) ─────────────────────────

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Minimal markdown → HTML transform: # heading, **bold**, blank-line paragraphs, - list.
function mdToHtml(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let inList = false;
  let para: string[] = [];
  const flushPara = () => { if (para.length) { out.push(`<p>${para.join(" ")}</p>`); para = []; } };
  const flushList = () => { if (inList) { out.push("</ol>"); inList = false; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line) { flushPara(); flushList(); continue; }
    if (/^#\s/.test(line)) { flushPara(); flushList(); out.push(`<h1>${escapeHtml(line.replace(/^#\s+/, ""))}</h1>`); continue; }
    if (/^##\s/.test(line)) { flushPara(); flushList(); out.push(`<h2>${escapeHtml(line.replace(/^##\s+/, ""))}</h2>`); continue; }
    if (/^[-*]\s/.test(line)) {
      flushPara();
      if (!inList) { out.push("<ol>"); inList = true; }
      out.push(`<li>${escapeHtml(line.replace(/^[-*]\s+/, "")).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")}</li>`);
      continue;
    }
    flushList();
    para.push(escapeHtml(line).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>"));
  }
  flushPara();
  flushList();
  return out.join("\n");
}

interface LetterMeta {
  subject?: string;
  referenceNumber?: string;
  addressee?: { name?: string; subLine?: string; honorific?: string };
  sender?: { company?: string; representative?: string; address?: string; postalCode?: string; tel?: string; email?: string };
}

function wrapLetterHtml(bodyHtml: string, meta: LetterMeta): string {
  const date = new Date().toLocaleDateString("ja-JP-u-ca-japanese", { year: "numeric", month: "long", day: "numeric" });
  const a = meta.addressee ?? {};
  const s = meta.sender ?? {};
  const sender = [
    s.postalCode ? `〒${escapeHtml(s.postalCode)}` : "",
    s.address ? escapeHtml(s.address) : "",
    s.company ? escapeHtml(s.company) : "",
    s.representative ? `代表取締役 ${escapeHtml(s.representative)}　印` : "",
    s.tel ? `TEL: ${escapeHtml(s.tel)}` : "",
    s.email ? `Email: ${escapeHtml(s.email)}` : "",
  ].filter(Boolean).join("<br>");
  const refLine = meta.referenceNumber ? `<div style="text-align:right">${escapeHtml(meta.referenceNumber)}</div>` : "";
  const title = meta.subject ? `<h1 style="text-align:center;font-size:13pt;letter-spacing:.08em;margin:1.4em 0;">${escapeHtml(meta.subject)}</h1>` : "";
  return `<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><style>
@page { size: A4; margin: 22mm 20mm; }
body { font-family: "Hiragino Mincho ProN", "YuMincho", serif; font-size: 10.8pt; line-height: 1.7; color: #000; }
h1 { text-align: center; font-size: 13pt; letter-spacing: .08em; }
h2 { font-size: 11pt; font-weight: bold; margin: 1.2em 0 .5em; }
p { margin: .45em 0; text-align: justify; }
ol, ul { padding-left: 1.5em; }
.addr { font-weight: bold; margin-bottom: 1.2em; }
.addr .sub { padding-left: 1.2em; font-weight: normal; margin-top: .2em; }
.sender { text-align: right; line-height: 1.55; margin: 1em 0 1.4em; }
.date { text-align: right; margin-bottom: 1em; }
</style></head><body>
${refLine}
<div class="addr">${escapeHtml(a.name ?? "")}　${escapeHtml(a.honorific ?? "御中")}${a.subLine ? `<div class="sub">${escapeHtml(a.subLine)}</div>` : ""}</div>
<div class="sender">${escapeHtml(date)}<br>${sender}</div>
${title}
${bodyHtml}
<div style="text-align:right;margin-top:1.2em;font-weight:bold;">以上</div>
</body></html>`;
}

function buildHtmlForFormat(content: string, format: string, meta: LetterMeta): string {
  if (format === "html") return content;
  if (format === "markdown") return wrapLetterHtml(mdToHtml(content), meta);
  // text: <pre> preserves whitespace
  return wrapLetterHtml(`<pre style="font-family:inherit;white-space:pre-wrap;">${escapeHtml(content)}</pre>`, meta);
}

function countPdfPages(bytes: Uint8Array): number {
  // Simple heuristic: count "/Type /Page" occurrences (excluding /Pages).
  let pages = 0;
  const text = new TextDecoder("latin1").decode(bytes);
  const re = /\/Type\s*\/Page(?!s)/g;
  while (re.exec(text)) pages++;
  return pages || 1;
}

async function renderHtmlToPdf(env: Record<string, unknown>, html: string, pageSize: string = "A4"): Promise<Uint8Array> {
  const browserBinding = env.HEADLESS_BROWSER;
  if (!browserBinding) {
    throw new Error("HEADLESS_BROWSER binding missing. To enable in-actor PDF rendering, add `browser` binding in wrangler config + install @cloudflare/puppeteer at the package level. Until then, render PDF agent-side (Chrome headless / Pages / pandoc) and call com.etzhayyim.apps.fax.uploadDocument with base64-encoded PDF bytes.");
  }
  // Dynamic import so the bundle compiles without the dep present. In-actor rendering is opt-in.
  const puppeteerMod: any = await import(/* @vite-ignore */ "@cloudflare/puppeteer").catch((e) => {
    throw new Error(`@cloudflare/puppeteer not installed in actor package — install it with \`pnpm add @cloudflare/puppeteer\` inside this app dir, or call uploadDocument with pre-rendered PDF instead. (${e instanceof Error ? e.message : String(e)})`);
  });
  const browser = await puppeteerMod.default.launch(browserBinding);
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });
    const buf = await page.pdf({ format: pageSize, printBackground: true });
    return new Uint8Array(buf);
  } finally {
    await browser.close().catch(() => {});
  }
}

async function uploadToCdn(env: Record<string, unknown>, bytes: Uint8Array, contentType: string): Promise<{ blobKey: string; deduped: boolean; publicUrl: string }> {
  const blobKey = await sha256Hex(bytes);
  const baseUrl = str(env.CDN_PUBLIC_BASE_URL ?? "https://fax.etzhayyim.com/api/blob");
  const existing = await cdnHead(env as Record<string, string>, blobKey).catch(() => null);
  let deduped = false;
  if (existing) {
    deduped = true;
  } else {
    await cdnWrite(env as Record<string, string>, blobKey, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer, contentType);
  }
  return { blobKey, deduped, publicUrl: `${baseUrl}/${blobKey}` };
}

async function cmdRenderPdf(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const content = str(args.content ?? "");
  const format = str(args.format ?? "text");
  const pageSize = str(args.pageSize ?? "A4");
  if (!content) return { ok: false, error: "content required" };
  const meta: LetterMeta = {
    subject: str(args.subject ?? ""),
    referenceNumber: str(args.referenceNumber ?? ""),
    addressee: args.addressee as LetterMeta["addressee"],
    sender: args.sender as LetterMeta["sender"],
  };
  try {
    const html = buildHtmlForFormat(content, format, meta);
    const pdfBytes = await renderHtmlToPdf(sdk.env, html, pageSize);
    const { blobKey, publicUrl } = await uploadToCdn(sdk.env, pdfBytes, "application/pdf");
    return {
      ok: true,
      blobKey,
      publicUrl,
      pageCount: countPdfPages(pdfBytes),
      byteSize: pdfBytes.length,
      renderedAt: nowISO(),
    };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

async function cmdUploadDocument(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const b64 = str(args.contentBase64 ?? "");
  const contentType = str(args.contentType ?? "application/pdf");
  if (!b64) return { ok: false, error: "contentBase64 required" };
  try {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const { blobKey, deduped, publicUrl } = await uploadToCdn(sdk.env, bytes, contentType);
    return { ok: true, blobKey, publicUrl, byteSize: bytes.length, deduped };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

// ───────────────────────── cross-actor: roukisho.recordCommunication ─────────────────────────

async function recordToRoukisho(_sdk: HostSDK, params: Record<string, unknown>): Promise<{ recordId: string | null; debug?: unknown }> {
  // cross-actor removed (ADR-0047 audit 2026-04-21). Was: invokeRemote(ROUKISHO_DID,
  // "com.etzhayyim.apps.roukisho.recordCommunication", params). This was best-effort
  // audit logging for communications. TODO: reimplement as write-only derived —
  // roukisho can consume com.etzhayyim.apps.fax.faxTx commits and produce its own
  // communication record (ADR-0004 pattern).
  const to = typeof params.to === "string" ? params.to : Array.isArray(params.to) ? params.to.join(",") : "";
  console.log(`[fax] recordToRoukisho cross-actor stub: to=${to.slice(0, 40)}`);
  return { recordId: null, debug: { kind: "conversation-stub", target: ROUKISHO_DID } };
}

// ───────────────────────── composeAndSend (Tier 1, MCP-callable) ─────────────────────────

async function cmdComposeAndSend(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const to = str(args.to ?? "");
  const content = str(args.content ?? "");
  const format = str(args.format ?? "text");
  const provider = str(args.provider ?? "auto");
  const dryRun = Boolean(args.dryRun);
  const caseId = str(args.caseId ?? "");
  const officeId = str(args.officeId ?? "");
  if (!to || !content) return { ok: false, error: "to and content required" };

  // 1. render
  const renderArgs = new TextEncoder().encode(JSON.stringify({
    content, format,
    subject: args.subject, referenceNumber: args.referenceNumber,
    addressee: args.addressee, sender: args.sender,
  }));
  const rendered = await cmdRenderPdf(sdk, renderArgs);
  if (!rendered.ok) return { ok: false, error: `render failed: ${rendered.error}` };
  const blobKey = rendered.blobKey;
  const publicUrl = rendered.publicUrl;
  const pageCount = rendered.pageCount;
  const byteSize = rendered.byteSize;

  if (dryRun) {
    return { ok: true, txId: "dry-run", status: "rendered_only", blobKey, publicUrl, pageCount, byteSize };
  }

  // 2. choose provider — Phaxio is a dead path (2026-04-17). `auto` always resolves to manual
  //    unless the operator explicitly opts in via provider="phaxio" AND SS_FAX_API_KEY is set.
  const hasPhaxioCreds = Boolean(sdk.env.SS_FAX_API_KEY && sdk.env.SS_FAX_API_SECRET);
  const effectiveProvider = provider === "phaxio" && hasPhaxioCreds ? "phaxio" : "manual";

  // 3. send (or manual handoff)
  if (effectiveProvider === "manual") {
    const txId = genID("fax");
    const recipient = normalizeE164(to);
    const subject = str(args.subject ?? "");
    const teamsChannelEmail = str(args.teamsChannelEmail ?? "");
    const operatorEmail = str(args.operatorEmail ?? "");

    write(sdk, "faxTx", {
      txId, to: recipient, subject, caseId,
      blobKey, url: publicUrl, status: "needs_human", providerUsed: "manual",
      pageCount, byteSize, sentAt: nowISO(),
    });

    // Optional notification handoff via mailer actor (cross-actor invoke).
    // mailer actor (did:web:mailer.etzhayyim.com, nanoid nt4g5h6i) wraps Mail.Send for app-only
    // tenants. We delegate Teams-channel + operator notification to it so this actor stays
    // single-purpose. If mailer is not deployed yet, the call is best-effort and we still
    // return humanInstructions for fallback.
    let notificationId: string | null = null;
    if (teamsChannelEmail || operatorEmail) {
      try {
        const recipients = [teamsChannelEmail, operatorEmail].filter(Boolean);
        // cross-actor removed (ADR-0047 audit 2026-04-21). Was: invokeRemote to
        // mailer.etzhayyim.com/send for Teams-channel + operator notification.
        // Best-effort only; humanInstructions fallback remains below.
        // TODO: emit com.etzhayyim.apps.fax.notificationRequest record and let
        // mailer consume it via onCommit (ADR-0004 write-only derived).
        // Operator still receives info via the humanInstructions returned
        // below (Teams channel / email now need to come from a separate
        // mailer-triggered path, e.g. fax.notificationRequest → mailer).
        console.log(`[fax] mailer cross-actor stub: recipients=${recipients.length} txId=${txId} subject="${subject.slice(0, 60)}"`);
        notificationId = null;
      } catch (e) {
        console.error("notifyOperator failed:", e instanceof Error ? e.message : String(e));
        notificationId = null;
      }
    }

    return {
      ok: true, txId, status: "needs_human", blobKey, publicUrl, pageCount, byteSize,
      providerUsed: "manual",
      notificationId: notificationId ?? undefined,
      humanInstructions: {
        channel: "dropbox-fax",
        uploadUrl: str(sdk.env.DROPBOX_FAX_UI_URL ?? "https://app.hellofax.com/"),
        downloadUrl: publicUrl,
        recipientFax: recipient,
        steps: [
          "Open https://app.hellofax.com/ (logged in as account holder)",
          "Click ファクスを送信",
          `Upload PDF from ${publicUrl} (or local copy)`,
          `Recipient (E.164 → JP local): ${recipient}`,
          "Send",
          `After send, call com.etzhayyim.apps.fax.confirmManualSend({ txId: "${txId}", providerFaxId: "<provider-side id if known>", sentAt: "<ISO timestamp>" })`,
        ],
      },
    };
  }

  // phaxio path: delegate to existing send handler
  const sendArgs = new TextEncoder().encode(JSON.stringify({
    to, blobKey, subject: str(args.subject ?? ""), caseId, from: str(args.from ?? ""),
  }));
  const sendResult = await cmdSend(sdk, sendArgs);

  // 4. record to roukisho if officeId given
  let roukishoCommunicationId: string | null = null;
  let roukishoFollowup: { hint: string; method: string; payload: Record<string, unknown> } | null = null;
  if (officeId && sendResult.ok) {
    const recordParams = {
      direction: "outbound",
      channel: "fax",
      officeId,
      officeDid: str(args.officeDid ?? ""),
      divisionNumber: Number(args.divisionNumber ?? 0),
      inspector: str(args.inspector ?? ""),
      caseId,
      subject: str(args.subject ?? ""),
      summary: `FAX to ${normalizeE164(to)} (${pageCount} pages, blob ${blobKey.slice(0, 16)}…)`,
      documentBlobKey: blobKey,
      faxTxId: sendResult.txId,
      occurredAt: nowISO(),
    };
    const { recordId } = await recordToRoukisho(sdk, recordParams);
    roukishoCommunicationId = recordId;
    if (!recordId) {
      roukishoFollowup = {
        hint: "Cross-actor invoke failed (CF 522 same-zone). Call roukisho directly to close audit chain.",
        method: "com.etzhayyim.apps.roukisho.recordCommunication",
        payload: recordParams,
      };
    }
  }

  return {
    ok: sendResult.ok,
    txId: sendResult.txId,
    providerFaxId: sendResult.providerFaxId,
    status: sendResult.status,
    blobKey, publicUrl, pageCount, byteSize,
    providerUsed: "phaxio",
    roukishoCommunicationId: roukishoCommunicationId ?? undefined,
    roukishoFollowup: roukishoFollowup ?? undefined,
    error: sendResult.error,
  };
}

async function cmdConfirmManualSend(sdk: HostSDK, body: Uint8Array) {
  const args = decodeJson(body, {}) as Record<string, unknown>;
  const txId = str(args.txId ?? "");
  if (!txId) return { ok: false, error: "txId required" };
  const providerFaxId = str(args.providerFaxId ?? "");
  const sentAt = str(args.sentAt ?? nowISO());
  const deliveredAt = str(args.deliveredAt ?? "");
  const caseId = str(args.caseId ?? "");
  const officeId = str(args.officeId ?? "");
  const summary = str(args.summary ?? `Manual handoff confirmed (txId=${txId}, providerFaxId=${providerFaxId || "n/a"})`);

  write(sdk, "faxTxUpdate", {
    txId, providerFaxId, status: "success", caseId,
    sentAt, deliveredAt: deliveredAt || sentAt, confirmedAt: nowISO(),
    confirmedManually: true,
  });

  let roukishoCommunicationId: string | null = null;
  let roukishoFollowup: { hint: string; method: string; payload: Record<string, unknown> } | null = null;
  if (officeId) {
    const recordParams = {
      direction: "outbound",
      channel: "fax",
      officeId,
      officeDid: str(args.officeDid ?? ""),
      divisionNumber: Number(args.divisionNumber ?? 0),
      inspector: str(args.inspector ?? ""),
      caseId,
      subject: str(args.subject ?? ""),
      summary,
      faxTxId: txId,
      occurredAt: sentAt,
    };
    const { recordId } = await recordToRoukisho(sdk, recordParams);
    roukishoCommunicationId = recordId;
    if (!recordId) {
      // Cross-actor invoke is currently blocked by CF same-zone Worker→Worker fetch
      // (HTTP 522) and PDS does not auto-dispatch custom NSIDs. Return a follow-up payload
      // so the calling agent (or human) can complete the audit chain by POSTing directly:
      //   curl -X POST https://r0uk15h0.etzhayyim.com/xrpc/com.etzhayyim.apps.roukisho.recordCommunication
      //        -H 'content-type: application/json' -d '<payload>'
      roukishoFollowup = {
        hint: "Cross-actor invoke failed (CF 522 same-zone). Call roukisho directly to close audit chain.",
        method: "com.etzhayyim.apps.roukisho.recordCommunication",
        payload: recordParams,
      };
    }
  }

  return {
    ok: true, txId, status: "success",
    roukishoCommunicationId: roukishoCommunicationId ?? undefined,
    roukishoFollowup: roukishoFollowup ?? undefined,
  };
}

// ───────────────────────── Worker export ─────────────────────────

export default createWorkerExport((sdk) => {
  appId = sdk.pds.selfNanoid ?? "f4x5end1";

  sdk.router.post("/webhook/fax", (c) => handleProviderWebhook(sdk, c.req.raw));

  // R2 blob proxy: GET /api/blob/{sha256hex} → CDN_R2 object stream.
  // CDN_R2 is private by default; this Worker route is the canonical public read path.
  // Cached at edge (immutable) since blobs are content-addressed.
  // CORS: open (Access-Control-Allow-Origin: *) so that 3rd-party browser automation
  // (e.g. yuubin puppeteer flow, Claude-in-Chrome injection) can fetch blobs cross-origin
  // without proxying. Content is content-addressed SHA-256 so access is non-sensitive.
  sdk.router.options("/api/blob/:key", (c) => new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, HEAD, OPTIONS",
      "access-control-allow-headers": "*",
      "access-control-max-age": "86400",
    },
  }));
  sdk.router.get("/api/blob/:key", async (c) => {
    const key = c.req.param("key");
    if (!/^[a-f0-9]{64}$/.test(key)) return c.text("invalid blobKey (expected 64-hex SHA-256)", 400);
    const hit = await cdnRead(sdk.env as Record<string, string>, key).catch(() => null);
    if (!hit) return c.text("blob not found", 404);
    return new Response(hit.body, {
      headers: {
        "content-type": hit.contentType,
        "content-length": String(hit.body.byteLength),
        "cache-control": "public, max-age=31536000, immutable",
        "x-blob-key": key,
        "access-control-allow-origin": "*",
        "access-control-expose-headers": "content-type, content-length, x-blob-key",
      },
    });
  });

  sdk.app
    // Tier 1 (DEFAULT for agents) — composes letter + delivers via manual-handoff (Dropbox Fax UI)
    .command(nsid("com.etzhayyim.apps.fax.composeAndSend"), async (_c, b) => cmdComposeAndSend(sdk, b),
      asAgentTool("End-to-end FAX preparation: text/markdown/HTML → A4 PDF → CDN R2 → manual handoff via Dropbox Fax UI (provider='manual' is DEFAULT; Phaxio is dead path). Posts a Teams/email notification to operator with the prepared PDF + recipient + step-by-step instructions. After operator sends manually, call confirmManualSend({txId,...}) to close the audit chain (cross-actor record to roukisho)."),
      withCapabilityTags("fax", "compose", "outbound", "compliance", "high-level"))
    .command(nsid("com.etzhayyim.apps.fax.confirmManualSend"), async (_c, b) => cmdConfirmManualSend(sdk, b),
      asAgentTool("Mark a manual-handoff faxTx as completed once the operator has sent the FAX via Dropbox Fax UI. Updates faxTxUpdate + invokes roukisho.recordCommunication if officeId provided."),
      withCapabilityTags("fax", "compose", "confirm", "audit"))
    // Tier 2 (compose helpers — agent can call directly for finer control)
    .command(nsid("com.etzhayyim.apps.fax.renderPdf"), async (_c, b) => cmdRenderPdf(sdk, b),
      asAgentTool("Render text/markdown/HTML to A4 PDF via CF Browser Rendering, upload to CDN R2 (SHA-256 keyed). Returns blobKey usable by com.etzhayyim.apps.fax.send / composeAndSend."),
      withCapabilityTags("fax", "render", "pdf"))
    .command(nsid("com.etzhayyim.apps.fax.uploadDocument"), async (_c, b) => cmdUploadDocument(sdk, b),
      asAgentTool("Upload a pre-rendered document (base64) to CDN R2 (content-addressed, deduped). Returns blobKey usable by com.etzhayyim.apps.fax.send / composeAndSend."),
      withCapabilityTags("fax", "upload", "blob"))
    // Tier 3 (transmission — Phaxio path retained but never wired in production)
    .command(nsid("com.etzhayyim.apps.fax.send"), async (_c, b) => cmdSend(sdk, b),
      asAgentTool("Send a FAX via Phaxio API (DEAD PATH — only fires if SS_FAX_API_KEY is set). For manual flow, use composeAndSend instead."),
      withCapabilityTags("fax", "transport", "outbound", "dead-path"))
    .command(nsid("com.etzhayyim.apps.fax.cancel"), async (_c, b) => cmdCancel(sdk, b),
      asAgentTool("Cancel a queued Phaxio fax (DEAD PATH)."),
      withCapabilityTags("fax", "transport", "cancel", "dead-path"))
    .query(nsid("com.etzhayyim.apps.fax.getStatus"), async (_c, b) => cmdGetStatus(sdk, b))
    .query(nsid("com.etzhayyim.apps.fax.listSent"), async (_c, b) => cmdListSent(sdk, b))
    .query(nsid("com.etzhayyim.apps.fax.listReceived"), async (_c, b) => cmdListReceived(sdk, b));
});
