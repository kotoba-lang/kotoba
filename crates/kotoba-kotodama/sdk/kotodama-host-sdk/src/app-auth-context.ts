import type { AppContext, HostImports } from "./types.js";

export type HeaderPair = [string, string];

export function resolveAppContext(
  appId: string,
  host: HostImports,
  headers: HeaderPair[],
): AppContext {
  let authHeader = "";
  let orgHeader = "";
  let reqIdHeader = "";
  for (const [k, v] of headers) {
    const kl = k.toLowerCase();
    if (kl === "authorization") authHeader = v;
    else if (kl === "x-etzhayyim-org-id") orgHeader = v;
    else if (kl === "x-request-id") reqIdHeader = v;
  }

  let orgId = "anon";
  let userId = "anon";

  if (authHeader) {
    const ctx = host.authnResolveContext(authHeader, orgHeader, reqIdHeader);
    if (ctx) {
      if (ctx.targetOrgId) orgId = ctx.targetOrgId;
      if (ctx.claims.userId) userId = ctx.claims.userId;
      if (orgId === "anon" && ctx.claims.orgId) orgId = ctx.claims.orgId;
    }
  }

  return {
    orgId,
    userId,
    actorId: userId !== "anon" ? userId : appId,
    convoId: "",
    appId,
    now: new Date().toISOString(),
  };
}
