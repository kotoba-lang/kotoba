import { isValidNsid } from "@atproto/syntax";
import { resolveFlatDispatchMethod } from "./nsid.js";

// Exported so the HTTP entry point (app-router.ts) can distinguish malformed
// NSIDs (4xx InvalidRequest) from unknown-but-well-formed NSIDs (404).
export function isWellFormedNsid(input: string): boolean {
  return input.includes(".") && isValidNsid(input);
}

export function resolveXrpcMethod<T>(
  nsid: string,
  methodMap: Map<string, T>,
): T | undefined {
  const direct = methodMap.get(nsid);
  if (direct) return direct;
  if (nsid.includes(".")) return undefined;
  const resolved = resolveFlatDispatchMethod(nsid, methodMap.keys());
  if (!resolved) return undefined;
  return methodMap.get(resolved);
}
