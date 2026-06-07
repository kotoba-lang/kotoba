/**
 * Cross-request state for derive side-effects within a single Worker instance.
 *
 * MVP implementation: an in-process Map keyed by source AT URI, populated when
 * a rule emits with `_meta.sideEffect: "linkBackPostUri"`, read by subsequent
 * derive dispatches that evaluate `{{derived(record.chapterRef).strongRef}}`.
 *
 * Known limitations (accepted for MVP):
 *   - State is scoped to one Worker isolate; a page commit handled on a
 *     different colo/instance than its chapter commit will miss the link
 *     and the page-published-social rule will skip (identical to the
 *     current not-implemented state — no regression).
 *   - No persistence across deploys or isolate evictions.
 *
 * Upgrade path: replace the Map with either
 *   (a) a graph-backed lookup (`SELECT post_uri, post_cid FROM graphar.vertex_internal_derived_link WHERE source_uri = ? LIMIT 1`), populated via `comAtprotoRepoCreateRecord(env, repo, "com.etzhayyim.internal.derivedLink", …)` with deterministic rkey, or
 *   (b) a Durable Object keyed by source URI for strong consistency across all isolates.
 *
 * The `recordLink` / `getLink` API is stable — consumers do not depend on
 * Map semantics, so migration is a drop-in replacement in this file only.
 */

import type { SelfRef } from "./template.js";

const CAP = 10_000;

/** sourceUri (e.g. at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.chapter/<rkey>) → derived post strongRef */
const derivedLinks = new Map<string, SelfRef>();

/** Insertion-order eviction when over CAP (simple LRU-ish bound). */
export function recordLink(sourceUri: string, ref: SelfRef): void {
  if (derivedLinks.size >= CAP) {
    const firstKey = derivedLinks.keys().next().value as string | undefined;
    if (firstKey !== undefined) derivedLinks.delete(firstKey);
  }
  derivedLinks.set(sourceUri, ref);
}

export function getLink(sourceUri: string): SelfRef | null {
  return derivedLinks.get(sourceUri) ?? null;
}

export function clearLinks(): void {
  derivedLinks.clear();
}

export function linkCount(): number {
  return derivedLinks.size;
}
