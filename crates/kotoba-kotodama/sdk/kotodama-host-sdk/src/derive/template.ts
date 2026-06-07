/**
 * Template resolver for kotodama.jsonld derive rules.
 *
 * Supports the minimal expression set used by the lawfirm / mangaka derive
 * rules. Greenfield — there is no mustache/handlebars dep in the PDS Worker.
 *
 * Supported constructs:
 *   {{record.foo}}                   deep getter-chain on the committed record
 *   {{record.foo.bar}}               nested
 *   {{self.uri}} / {{self.cid}}      strongRef of the newly-created record
 *   {{tagFromVolume record.volumeId}} helper call (see HELPERS)
 *   {{resolve(record.ref).workDid}}  strongRef -> author DID extraction
 *   {{derived(record.ref).strongRef}} back-reference to a previously-derived post
 *                                    (MVP: returns null, emitting rule is skipped)
 *   _from / _each                    array iteration in facet/embed structures
 *   _matchText                       facet index placeholder resolved after the
 *                                    surrounding text is interpolated
 *
 * Not supported (future):
 *   arithmetic (`{{scheduledAt - PT24H}}`), {{#each}} (handled via _from/_each),
 *   conditional blocks
 */

export interface SelfRef {
  uri: string;
  cid: string;
}

export interface TemplateContext {
  record: Record<string, unknown>;
  self: SelfRef;
  repo: string;
  /** Pre-resolved source-uri → derived post strongRef map (takes priority over resolveDerivedPost). */
  derivedPosts?: Record<string, SelfRef>;
  /** Callback for on-demand derived-post lookup (e.g. in-memory Map, graph query, Durable Object). */
  resolveDerivedPost?: (sourceUri: string) => SelfRef | null;
  /** Present during `_from`/`_each` expansion — the current iteration element. */
  item?: unknown;
}

// ── helper functions invokable via {{helperName arg}} ──

const HELPERS: Record<string, (arg: unknown) => string> = {
  /** vol01-loneliness → sip-vol1 (strip vol0? prefix, take leading digit, drop suffix). */
  tagFromVolume: (arg) => {
    if (typeof arg !== "string") return "";
    const m = arg.match(/^vol0*(\d+)/);
    return m ? `sip-vol${m[1]}` : arg;
  },
  /** charactersAppearing array → "@Tamaki @Nei " text substring for mention facet matching. */
  charactersAppearingMentions: (arg) => {
    if (!Array.isArray(arg)) return "";
    return arg
      .map((c) => (c && typeof c === "object" ? (c as { displayName?: string }).displayName : null))
      .filter(Boolean)
      .map((n) => `@${n}`)
      .join(" ") + (arg.length > 0 ? " " : "");
  },
  /** arcIds array → "#TamakiGrowth #NeiChanDebt " text substring for tag facet matching. */
  arcIdsTags: (arg) => {
    if (!Array.isArray(arg)) return "";
    return arg
      .filter((t) => typeof t === "string")
      .map((t) => `#${t}`)
      .join(" ") + (arg.length > 0 ? " " : "");
  },
};

/** Extract nested value via dotted getter chain. */
function getPath(ctx: TemplateContext, path: string): unknown {
  const segs = path.split(".");
  // deno-lint-ignore no-explicit-any
  let cur: any;
  if (segs[0] === "record") cur = ctx.record;
  else if (segs[0] === "self") cur = ctx.self;
  else if (segs[0] === "repo") return ctx.repo;
  else if (segs[0] === "item") {
    if (segs.length === 1) return ctx.item;
    cur = ctx.item;
  }
  else return undefined;
  for (let i = 1; i < segs.length; i++) {
    if (cur == null) return undefined;
    cur = cur[segs[i]];
  }
  return cur;
}

/** Resolve an at-uri to its authority (repo DID/handle). `at://did/coll/rkey` → `did`. */
function authorityFromAtUri(uri: string): string {
  if (!uri.startsWith("at://")) return uri;
  const rest = uri.slice(5);
  const slash = rest.indexOf("/");
  return slash === -1 ? rest : rest.slice(0, slash);
}

/** resolve(ref).workDid → authority of ref.uri. */
function resolveCall(ctx: TemplateContext, argExpr: string, suffix: string): string {
  // argExpr = "record.workRef"; suffix = "workDid"
  const refValue = getPath(ctx, argExpr);
  if (!refValue || typeof refValue !== "object") return "";
  const uri = (refValue as { uri?: string }).uri;
  if (!uri) return "";
  if (suffix === "workDid" || suffix === "authorDid" || suffix === "authority") {
    return authorityFromAtUri(uri);
  }
  return "";
}

/** derived(ref).strongRef → look up previously-derived post strongRef. */
function derivedCall(ctx: TemplateContext, argExpr: string, suffix: string): SelfRef | null {
  if (suffix !== "strongRef") return null;
  const refValue = getPath(ctx, argExpr);
  if (!refValue || typeof refValue !== "object") return null;
  const uri = (refValue as { uri?: string }).uri;
  if (!uri) return null;
  // Pre-resolved map wins (used by tests + future graph batch pre-fetch)
  if (ctx.derivedPosts && ctx.derivedPosts[uri]) return ctx.derivedPosts[uri];
  // Fall back to on-demand callback (in-memory Map, graph query, etc.)
  if (ctx.resolveDerivedPost) return ctx.resolveDerivedPost(uri);
  return null;
}

/** Stringify a primitive / identity-preserve structured value (for ref substitution). */
function stringifyScalar(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

/** Interpolate `{{...}}` expressions inside a string, returning scalar or structured. */
function interpolateString(tpl: string, ctx: TemplateContext): string | SelfRef | null {
  // Whole-string single-expression case — preserves non-string values (like SelfRef)
  const whole = tpl.match(/^\{\{\s*([^}]+?)\s*\}\}$/);
  if (whole) {
    const value = evalExpr(whole[1], ctx);
    if (value === null) return null;
    if (typeof value === "object") return value as SelfRef;
    return stringifyScalar(value);
  }
  return tpl.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_m, expr) => {
    const v = evalExpr(expr, ctx);
    return stringifyScalar(v);
  });
}

/** Evaluate a single `{{ expression }}` body. */
function evalExpr(expr: string, ctx: TemplateContext): unknown {
  const trimmed = expr.trim();
  // resolve(ARG).SUFFIX
  const resolveM = trimmed.match(/^resolve\(\s*([a-zA-Z0-9_.]+)\s*\)\.([a-zA-Z0-9_]+)$/);
  if (resolveM) return resolveCall(ctx, resolveM[1], resolveM[2]);
  // derived(ARG).SUFFIX
  const derivedM = trimmed.match(/^derived\(\s*([a-zA-Z0-9_.]+)\s*\)\.([a-zA-Z0-9_]+)$/);
  if (derivedM) return derivedCall(ctx, derivedM[1], derivedM[2]);
  // helperName ARG
  const helperM = trimmed.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s+(.+)$/);
  if (helperM && HELPERS[helperM[1]]) {
    const arg = getPath(ctx, helperM[2].trim());
    return HELPERS[helperM[1]](arg);
  }
  // plain path
  return getPath(ctx, trimmed);
}

// ── recursive interpolation over arbitrary structures ──

/** Walk a value and interpolate templates. Returns `null` if any required
 *  expression resolves to null (signals "skip this emission"). */
export function resolveValue(value: unknown, ctx: TemplateContext): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") return interpolateString(value, ctx);
  if (Array.isArray(value)) {
    const out: unknown[] = [];
    for (const item of value) {
      // _from/_each: iterate a context array, producing one output per item
      if (item && typeof item === "object" && "_from" in (item as object) && "_each" in (item as object)) {
        const fromExpr = (item as { _from: string })._from;
        const template = (item as { _each: unknown })._each;
        const srcValue = evalExpr(fromExpr, ctx);
        if (Array.isArray(srcValue)) {
          for (const el of srcValue) {
            const expanded = resolveValue(template, { ...ctx, item: el });
            out.push(expanded);
          }
        }
        continue;
      }
      out.push(resolveValue(item, ctx));
    }
    return out;
  }
  if (typeof value === "object") {
    const inObj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(inObj)) {
      out[k] = resolveValue(v, ctx);
    }
    return out;
  }
  return value;
}

/** Substitute `{{item.field}}` inside an already-resolved structure using the current iteration element. */
function replaceItem(value: unknown, item: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") {
    return value.replace(/\{\{\s*item\.([a-zA-Z0-9_]+)\s*\}\}/g, (_m, field) => {
      if (item && typeof item === "object") {
        const v = (item as Record<string, unknown>)[field];
        return stringifyScalar(v);
      }
      return String(item);
    }).replace(/\{\{\s*item\s*\}\}/g, () => stringifyScalar(item));
  }
  if (Array.isArray(value)) return value.map((v) => replaceItem(v, item));
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = replaceItem(v, item);
    return out;
  }
  return value;
}

// ── facet index resolution (_matchText → byteStart/byteEnd) ──

/** Resolve every `index: { _matchText: "..." }` to AT Protocol byte indices in `text`. */
export function resolveFacetIndices(
  facets: unknown,
  text: string,
): Array<{ index: { byteStart: number; byteEnd: number }; features: unknown[] }> {
  if (!Array.isArray(facets)) return [];
  const encoder = new TextEncoder();
  const bytes = encoder.encode(text);
  const out: Array<{ index: { byteStart: number; byteEnd: number }; features: unknown[] }> = [];
  for (const raw of facets) {
    if (!raw || typeof raw !== "object") continue;
    const f = raw as { index?: unknown; features?: unknown };
    let byteStart = -1;
    let byteEnd = -1;
    if (f.index && typeof f.index === "object" && "_matchText" in (f.index as object)) {
      const needle = (f.index as { _matchText: string })._matchText;
      const needleBytes = encoder.encode(needle);
      const idx = findSubsequence(bytes, needleBytes);
      if (idx < 0) continue;
      byteStart = idx;
      byteEnd = idx + needleBytes.length;
    } else if (f.index && typeof f.index === "object" && "byteStart" in (f.index as object)) {
      const i = f.index as { byteStart: number; byteEnd: number };
      byteStart = i.byteStart;
      byteEnd = i.byteEnd;
    } else {
      continue;
    }
    if (Array.isArray(f.features)) {
      out.push({ index: { byteStart, byteEnd }, features: f.features });
    }
  }
  return out;
}

function findSubsequence(hay: Uint8Array, needle: Uint8Array): number {
  if (needle.length === 0 || needle.length > hay.length) return -1;
  outer: for (let i = 0; i <= hay.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (hay[i + j] !== needle[j]) continue outer;
    }
    return i;
  }
  return -1;
}
