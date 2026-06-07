/**
 * DeriveEmitter — host-sdk primitive for Write-Only Derived social posts.
 *
 * Architectural rationale: apps write domain data directly via Kysely+Hyperdrive
 * (or via sdk.pds.createRecord for records that must live in the PDS Repo).
 * Only social posts (app.bsky.feed.post) are emitted to PDS. The derive engine
 * previously lived as a PDS commit hook (core.ts:1414) but that path is bypassed
 * by apps that write directly; the correct placement is the app-facing host-sdk,
 * invoked explicitly via `await sdk.derive.emit(collection, record, self)` AFTER
 * the app's own write completes.
 *
 * Usage (mangaka cmdAddChapter):
 *   const ref = await sdk.pds.createRecord("com.etzhayyim.apps.mangaka.chapter", record, id);
 *   await sdk.derive.emit("com.etzhayyim.apps.mangaka.chapter", record, ref);
 *
 * The caller provides `self = { uri, cid }` because rules reference the
 * newly-created record's strongRef in `{{self.uri}}` / `{{self.cid}}` templates
 * (recordWithMedia embed). sdk.pds.createRecord returns exactly this shape.
 */

import type { DeriveRule } from "./registry.js";
import { rulesForCollection } from "./registry.js";
import { resolveValue, resolveFacetIndices, type TemplateContext, type SelfRef } from "./template.js";
import { recordLink, getLink } from "./state.js";

/** Minimal PDS surface needed — matches XrpcClient.post() + XrpcClient.createRecord() + .repo. */
export interface DerivePds {
  readonly repo: string;
  post(text: string, opts?: { repo?: string; facets?: unknown[]; embed?: unknown }): Promise<{ uri: string; cid: string }>;
  createRecord<T>(collection: string, record: T, rkey?: string): Promise<{ uri: string; cid: string }>;
}

export interface EmitResult {
  matched: number;
  emitted: Array<{ ruleId: string; postUri: string; postCid: string }>;
  skipped: Array<{ ruleId: string; reason: string }>;
  errors: Array<{ ruleId: string; message: string }>;
}

/** Recursively strip embed.images[] entries whose blob ref.$link is empty/missing.
 *  If embed.recordWithMedia.media ends up empty, downgrade to embed.record only.
 *  If embed.images[] ends up empty and no other content, return undefined. */
function stripEmptyBlobImages(embed: unknown): unknown {
  if (!embed || typeof embed !== "object") return embed;
  const e = embed as Record<string, unknown>;
  if (e.$type === "app.bsky.embed.images" && Array.isArray(e.images)) {
    const kept = e.images.filter((img) => {
      const link = (img as { image?: { ref?: { $link?: string } } })?.image?.ref?.$link;
      return typeof link === "string" && link.length > 0;
    });
    if (kept.length === 0) return undefined;
    return { ...e, images: kept };
  }
  if (e.$type === "app.bsky.embed.recordWithMedia") {
    const media = stripEmptyBlobImages(e.media);
    if (!media) {
      // downgrade to plain record embed (no media)
      return e.record ?? undefined;
    }
    return { ...e, media };
  }
  return embed;
}

function whereMatches(where: Record<string, unknown> | undefined, record: Record<string, unknown>): boolean {
  if (!where) return true;
  for (const [key, expected] of Object.entries(where)) {
    const cleanKey = key.startsWith("record.") ? key.slice(7) : key;
    // deno-lint-ignore no-explicit-any
    let cur: any = record;
    for (const seg of cleanKey.split(".")) {
      if (cur == null) { cur = undefined; break; }
      cur = cur[seg];
    }
    if (cur !== expected) return false;
  }
  return true;
}

export class DeriveEmitter {
  constructor(private readonly pds: DerivePds) {}

  /** Emit all derived social posts for a committed domain record. */
  async emit(
    collection: string,
    record: Record<string, unknown>,
    self: SelfRef,
  ): Promise<EmitResult> {
    const rules = rulesForCollection(collection);
    const result: EmitResult = { matched: rules.length, emitted: [], skipped: [], errors: [] };
    if (rules.length === 0) return result;

    for (const rule of rules) {
      if (rule.on.action !== "create") {
        result.skipped.push({ ruleId: rule.id, reason: `action=${rule.on.action} not supported (MVP: create only)` });
        continue;
      }
      if (!whereMatches(rule.on.where, record)) {
        result.skipped.push({ ruleId: rule.id, reason: "where clause did not match" });
        continue;
      }
      try {
        const emitted = await this.applyRule(rule, record, self);
        if (emitted) result.emitted.push({ ruleId: rule.id, postUri: emitted.uri, postCid: emitted.cid });
        else result.skipped.push({ ruleId: rule.id, reason: "rule emit returned null (e.g. derived() unresolvable)" });
      } catch (e) {
        const msg = e instanceof Error
          ? `${e.message}${e.stack ? ` @ ${e.stack.split("\n")[1]?.trim() ?? ""}` : ""}`
          : (typeof e === "string" ? e : (() => { try { return JSON.stringify(e); } catch { return Object.prototype.toString.call(e); } })());
        result.errors.push({ ruleId: rule.id, message: msg.slice(0, 500) });
      }
    }
    return result;
  }

  private async applyRule(rule: DeriveRule, record: Record<string, unknown>, self: SelfRef): Promise<SelfRef | null> {
    const ctx: TemplateContext = {
      record,
      self,
      repo: this.pds.repo,
      derivedPosts: {},
      resolveDerivedPost: (sourceUri) => getLink(sourceUri),
    };

    // 1. Author DID — fall through to this.pds.repo (the app's own primary DID) if template fails
    const didResolved = resolveValue(rule.emit.did, ctx);
    const authorDid = typeof didResolved === "string" && didResolved.length > 0 ? didResolved : this.pds.repo;

    // 2. Text
    const textResolved = resolveValue(rule.emit.text, ctx);
    const text = typeof textResolved === "string" ? textResolved : "";

    // 3. Facets — iterate _from/_each, then resolve _matchText byte indices against the final text
    const facetsExpanded = rule.emit.facets ? resolveValue(rule.emit.facets, ctx) : [];
    const facets = resolveFacetIndices(facetsExpanded, text);

    // 4. Embed — resolve templates, then clean out images with empty blob refs.
    // If coverCid/compositedImageCid wasn't supplied, {{record.foo}} resolves to ""
    // and PDS rejects the post with "missing ref.$link". Drop such images gracefully.
    let embed = rule.emit.embed ? resolveValue(rule.emit.embed, ctx) : undefined;
    embed = stripEmptyBlobImages(embed);

    // 5. Reply — short-circuit emit if derived() was required but unresolved
    let reply: unknown;
    if (rule.emit.reply) {
      const replyResolved = resolveValue(rule.emit.reply, ctx) as { root?: unknown; parent?: unknown } | null;
      if (!replyResolved || replyResolved.root == null || replyResolved.parent == null) {
        return null;
      }
      reply = replyResolved;
    }

    // 6. Call sdk.pds — prefer .post() for simple app.bsky.feed.post, otherwise createRecord.
    //    Wrap in Promise.race with 12s hard timeout to defend against CF Worker
    //    "code had hung" 1101 detector on cold-isolate PDS_SERVICE binding calls.
    const doEmit = rule.emit.type === "app.bsky.feed.post"
      ? this.pds.post(text, {
          repo: authorDid !== this.pds.repo ? authorDid : undefined,
          facets: facets.length > 0 ? facets : undefined,
          embed,
        }).then((r) => ({ uri: r.uri, cid: r.cid }))
      : this.pds.createRecord(rule.emit.type, {
          $type: rule.emit.type,
          text,
          facets: facets.length > 0 ? facets : undefined,
          embed,
          reply,
          createdAt: new Date().toISOString(),
        }).then((r) => ({ uri: r.uri, cid: r.cid }));
    const emitted: SelfRef = await Promise.race([
      doEmit,
      new Promise<SelfRef>((_, reject) => setTimeout(() => reject(new Error("pds.post timed out after 12s (derive)")), 12_000)),
    ]);

    // 7. Side effect: record link so later rules' {{derived(ref).strongRef}} resolves
    if (rule.emit._meta?.sideEffect === "linkBackPostUri") {
      recordLink(self.uri, emitted);
    }

    return emitted;
  }
}
