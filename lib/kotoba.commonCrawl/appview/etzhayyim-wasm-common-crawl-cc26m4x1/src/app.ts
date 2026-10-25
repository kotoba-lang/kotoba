// commoncrawl.etzhayyim.com — CF Worker XRPC facade (L3 Dispatcher, ADR-2604251830).
// Entity extraction logic lives in kotodama/primitives/common_crawl.py
// (LangServer task type: commonCrawl.entities.extract, timeout 600s).
// Hourly autonomous runs via extractEntities.bpmn R/PT1H timer-start (ADR-0056).
import { createWorkerExport, decodeJson, nsid, type HostSDK } from "@etzhayyim/kotodama-host-sdk";

const VALID_DOMAINS = ["kuruma", "media_anime", "media_gamers", "handotai"] as const;
type Domain = typeof VALID_DOMAINS[number];

// ---------------------------------------------------------------------------
// BPMN dispatcher helpers (ADR-0056, proxyToBpmn pattern)
// ---------------------------------------------------------------------------
type InternalSecret = string | { get(): Promise<string> };
type EnvLike = { DISPATCHER_URL?: string; DISPATCHER_INTERNAL_SECRET?: InternalSecret };
function envOf(sdk: unknown): EnvLike { return ((sdk as { env?: EnvLike }).env ?? {}) as EnvLike; }
function dispatcherUrl(sdk: unknown): string { return envOf(sdk).DISPATCHER_URL ?? "https://dispatcher.etzhayyim.com"; }
async function internalTrustHeader(sdk: unknown): Promise<string> {
  const binding = envOf(sdk).DISPATCHER_INTERNAL_SECRET;
  if (!binding) return "";
  try { return typeof binding === "string" ? binding : await binding.get(); } catch { return ""; }
}
async function proxyToBpmn(sdk: HostSDK, toolNsid: string, input: unknown): Promise<string> {
  const started = Date.now();
  const trust = await internalTrustHeader(sdk);
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (trust) headers["x-internal-trust"] = trust;
  const resp = await fetch(`${dispatcherUrl(sdk)}/xrpc/${toolNsid}`, {
    method: "POST", headers, body: JSON.stringify(input ?? {}),
  });
  const text = await resp.text();
  let result: unknown;
  try { result = text ? JSON.parse(text) : {}; } catch { result = { raw: text }; }
  return JSON.stringify({ ok: resp.ok, status: resp.status, nsid: toolNsid, result, latencyMs: Date.now() - started });
}

export default createWorkerExport((sdk) => {
  // Enqueue entity extraction: fire-and-forget to LangServer extractEntities.bpmn.
  // Heavy work: SELECT unextracted pages + OpenRouter LLM fan-out + DB writes.
  // Must run in L7 LangServer (600s budget), not L3 CF Worker (25s budget).
  sdk.app.command(
    nsid("com.etzhayyim.commonCrawl.extractEntities"),
    async (_ctx, body) => {
      const params = decodeJson(body, { domain: "", limit: 15 });
      const domain = String(params.domain || "").trim() as Domain;
      if (!domain || !VALID_DOMAINS.includes(domain)) {
        return JSON.stringify({ error: `unknown domain: ${domain}`, valid: [...VALID_DOMAINS] });
      }
      const limit = Math.min(Number(params.limit) || 15, 30);
      return proxyToBpmn(sdk, "com.etzhayyim.commonCrawl.extractEntities", { domain, limit });
    },
  );
  // sdk.app.scheduled removed — replaced by extractEntities.bpmn R/PT1H timer-start (ADR-0056).
});
