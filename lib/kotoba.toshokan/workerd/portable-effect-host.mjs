const FORMAT = "kotoba.portable-effect/v1";
const NDL_ENDPOINT = "https://ndlsearch.ndl.go.jp/api/sru?";

function deny(reason, id = null) {
  return Object.freeze({
    format: "kotoba.portable-effect-result/v1",
    id,
    ok: false,
    denied: reason
  });
}

function exactObject(value, keys) {
  return value !== null
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.keys(value).every(key => keys.has(key));
}

function admittedNdlRequest(effect, policy) {
  if (!exactObject(effect, new Set(["format", "id", "call", "effects", "ability", "input"])))
    return "portable-effect-invalid";
  if (effect.format !== FORMAT || typeof effect.id !== "string" || effect.id.length === 0
      || effect.id.length > 128 || effect.call !== "toshokan/fetch"
      || !Array.isArray(effect.effects) || !effect.effects.includes("host/http"))
    return "portable-effect-invalid";

  const ability = effect.ability;
  if (!exactObject(ability, new Set([
    "kind", "resource", "target", "operation", "limits", "auditId"
  ]))) return "component-ability-invalid";
  if (ability.kind !== "host/http" || ability.auditId !== effect.id)
    return "component-policy-denied";
  if (!exactObject(ability.limits, new Set(["maxBytes", "maxItems", "deadlineMs"]))
      || !Number.isSafeInteger(ability.limits.maxBytes)
      || !Number.isSafeInteger(ability.limits.maxItems)
      || !Number.isSafeInteger(ability.limits.deadlineMs))
    return "component-limit-denied";

  if (!policy
      || policy.ndlScopeAdmitted(
        ability.resource, ability.target, ability.operation
      ) !== 1n) return "component-policy-denied";
  if (policy.ndlLimitsAdmitted(
    BigInt(ability.limits.maxBytes),
    BigInt(ability.limits.maxItems),
    BigInt(ability.limits.deadlineMs)
  ) !== 1n) return "component-limit-denied";

  const input = effect.input;
  if (!exactObject(input, new Set(["method", "url", "headers"]))
      || input.method !== "GET" || typeof input.url !== "string"
      || !input.url.startsWith(NDL_ENDPOINT)) return "provider-scope";
  if (!exactObject(input.headers, new Set(["User-Agent"]))
      || typeof input.headers["User-Agent"] !== "string"
      || input.headers["User-Agent"].length === 0
      || input.headers["User-Agent"].length > 256) return "provider-scope";
  return null;
}

async function boundedText(response, maxBytes) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes)
    throw Object.assign(new Error("response-too-large"), { kotobaDenied: "response-too-large" });
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > maxBytes)
    throw Object.assign(new Error("response-too-large"), { kotobaDenied: "response-too-large" });
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

export async function dispatchPortableEffect(effect, {
  fetchImpl = fetch,
  now = () => new Date().toISOString(),
  policy
} = {}) {
  const denied = admittedNdlRequest(effect, policy);
  if (denied) return deny(denied, effect?.id ?? null);

  const receiptBase = {
    format: "kotoba.ability-receipt/v1",
    id: effect.id,
    call: effect.call,
    ability: effect.ability,
    at: now()
  };
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), effect.ability.limits.deadlineMs);
    let response;
    try {
      response = await fetchImpl(effect.input.url, {
        method: "GET",
        headers: effect.input.headers,
        // Cloudflare Workers intentionally does not implement redirect:"error".
        // "manual" preserves the same fail-closed property: every 3xx reaches
        // the !ok branch below and is never followed to another authority.
        redirect: "manual",
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeout);
    }
    if (!response.ok)
      throw Object.assign(new Error("upstream-http-error"), { kotobaDenied: "upstream-http-error" });
    const body = await boundedText(response, effect.ability.limits.maxBytes);
    return Object.freeze({
      format: "kotoba.portable-effect-result/v1",
      id: effect.id,
      ok: true,
      value: body,
      receipt: Object.freeze({ ...receiptBase, outcome: "ok" })
    });
  } catch (error) {
    const reason = error?.kotobaDenied
      ?? (error?.name === "AbortError" ? "deadline-exceeded" : "provider-error");
    const diagnostic = Object.freeze({
      name: typeof error?.name === "string" ? error.name.slice(0, 64) : "Error",
      message: typeof error?.message === "string" ? error.message.slice(0, 256) : "provider failed"
    });
    console.error(JSON.stringify({ event: "toshokan.provider-error", reason, diagnostic }));
    return Object.freeze({
      ...deny(reason, effect.id),
      diagnostic,
      receipt: Object.freeze({ ...receiptBase, outcome: "denied", denied: reason })
    });
  }
}

export function createWorkerdHandler(options = {}) {
  return {
    async fetch(request) {
      if (request.method !== "POST") return new Response("method not allowed", { status: 405 });
      let effect;
      try {
        effect = await request.json();
      } catch {
        return Response.json(deny("portable-effect-invalid"), { status: 400 });
      }
      const result = await dispatchPortableEffect(effect, options);
      return Response.json(result, { status: result.ok ? 200 : 403 });
    },

    async scheduled(_controller, env, ctx) {
      if (!env?.TOSHOKAN_NDL_EFFECT)
        throw new Error("TOSHOKAN_NDL_EFFECT binding is required");
      ctx.waitUntil(
        dispatchPortableEffect(JSON.parse(env.TOSHOKAN_NDL_EFFECT), options)
          .then(result => console.log(JSON.stringify({
            event: "toshokan.portable-effect",
            result
          })))
      );
    }
  };
}

export const workerdProfile = Object.freeze({
  format: "kotoba.workerd-host/v1",
  effectFormat: FORMAT,
  policy: "src/toshokan/portable_effect.kotoba",
  capabilities: Object.freeze(["host/http"])
});
