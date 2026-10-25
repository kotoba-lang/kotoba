// @etzhayyim/xrpc — Unified XRPC client for W Protocol / AT Protocol.
//
// Single Source of Truth for NSID utilities, transport, auth, and error handling.
// Consumers: kotodama-host-sdk (`xrpc-client.ts`, `app.ts`, `app-router.ts`),
// PDS worker (`helpers.ts`, `core.ts`, `auth.ts`, `register.ts`).
//
// Pruned 2026-04-23: proxy.ts / SessionAuth / PublicAuth / mintInternalAuthJWT /
// BrowserTransport / SSRTransport / okResponse / errResponse / nullOnError /
// withSessionRefresh — all had zero external consumers. Browser XRPC goes
// through `@atproto/api` via the wproto facade.

export {
  collectionToLabel,
  expandCollection,
  witToCollection,
  nsidToMethod,
  appNamespace,
  defaultAppCollection,
  wLexiconCollection,
  resolveFlatDispatchMethod,
} from "./nsid.js";
export { resolveAutoCrudConvention } from "./app-convention.js";
export type { AutoCrudConvention, AutoCrudConventionInput, AutoCrudCommandNames } from "./app-convention.js";
export { isWellFormedNsid, resolveXrpcMethod } from "./dispatch.js";
export { withWLexicon, registerCommand, registerQuery } from "./command-dsl.js";
export type { CommandDslEntry, QueryDslEntry, CommandOption } from "./command-dsl.js";
export { BindingTransport } from "./transport.js";
export type { Fetcher, XrpcCallOpts } from "./transport.js";
export { ServiceAuth } from "./auth.js";
export type { AuthResolver, ServiceAuthSigner } from "./auth.js";
export { parseResponse, throwOnError } from "./error.js";
export type { WRPCError, XrpcResponse } from "./error.js";
export { generateTid, toBase64, fnv1a32, cl } from "./encode.js";
