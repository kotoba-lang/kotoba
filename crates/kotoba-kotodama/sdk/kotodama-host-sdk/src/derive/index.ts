/**
 * host-sdk derive module — Write-Only Derived social-post engine invoked
 * explicitly by apps after their domain write completes.
 *
 * App-facing entry point: `await sdk.derive.emit(collection, record, self)`.
 *
 * See 40-engine/kotoba/crates/kotoba-kotodama/CLAUDE.md §Direct Async RPC — apps write domain data
 * via Kysely/sdk.pds.createRecord directly; only social posts go through PDS.
 * This module lives in host-sdk so the derive engine is co-located with the
 * write path, not a post-commit hook on the PDS side (which would be bypassed).
 */

export { DeriveEmitter, type EmitResult, type DerivePds } from "./emit.js";
export { rulesForCollection, DERIVE_RULES, type DeriveRule } from "./registry.js";
export { resolveValue, resolveFacetIndices, type SelfRef, type TemplateContext } from "./template.js";
export { recordLink, getLink, clearLinks, linkCount } from "./state.js";
