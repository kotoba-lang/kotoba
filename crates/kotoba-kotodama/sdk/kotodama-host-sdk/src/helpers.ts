// helpers.ts — Shared utility functions.

export function toSnake(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c >= "A" && c <= "Z") {
      if (i > 0) out += "_";
      out += c.toLowerCase();
    } else {
      out += c;
    }
  }
  return out;
}

export function toKebab(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c >= "A" && c <= "Z") {
      if (i > 0) out += "-";
      out += c.toLowerCase();
    } else {
      out += c;
    }
  }
  return out;
}

/** snakeCase/kebab-case → PascalCase: "generateArticle" → "GenerateArticle" */
export function toPascal(s: string): string {
  return s.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join("");
}

export function humanizeIdentifier(s: string): string {
  return toSnake(s.replaceAll("-", "_")).replaceAll("_", " ");
}

export function inferCommandVerb(name: string): string {
  return toSnake(name.replaceAll("-", "_")).split("_").find((part) => part.length > 0) || "";
}

export function normalizeTag(s: string): string {
  const trimmed = s.trim();
  if (!trimmed) return "";
  return toSnake(trimmed.replaceAll("-", "_").replaceAll(" ", "_"))
    .split("_")
    .filter((part) => part.length > 0)
    .join("-");
}

export function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}

export function firstNonEmpty(...values: string[]): string {
  for (const value of values) {
    if (value.trim()) return value;
  }
  return "";
}

export function parseUrl(url: string): { path: string; query: string } {
  const qIdx = url.indexOf("?");
  if (qIdx === -1) return { path: url, query: "" };
  return { path: url.substring(0, qIdx), query: url.substring(qIdx + 1) };
}

export function respondJson(
  status: number,
  payload: unknown,
): { status: number; headers: [string, string][]; body: Uint8Array } {
  return {
    status,
    headers: [["content-type", "application/json"]],
    body: new TextEncoder().encode(JSON.stringify(payload)),
  };
}

// --- Common app utilities (shared across 400+ TS native apps) ---

const _enc = new TextEncoder();
const _dec = new TextDecoder();

/** Decode Uint8Array JSON payload with fallback. */
export function decodeJson<T>(payload: Uint8Array, fallback: T): T {
  if (!payload || payload.length === 0) return fallback;
  try { return JSON.parse(_dec.decode(payload)) as T; } catch { return fallback; }
}

/** Encode value to Uint8Array JSON. */
export function encodeJson(value: unknown): Uint8Array {
  return _enc.encode(JSON.stringify(value));
}

/** Safe string coercion — null/undefined → "". */
export function str(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return String(value);
}

/** Current ISO timestamp. */
export function nowISO(): string {
  return new Date().toISOString();
}

/** Strip HTML tags, scripts, styles → plain text. */
export function stripHTML(html: string): string {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#\d+;/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Truncate string to maxLen. */
export function truncateText(s: string, maxLen: number): string {
  return s.length <= maxLen ? s : s.slice(0, maxLen);
}

/** Monotonic ID generator — `{prefix}-{timestamp}-{counter}`. Thread-safe per isolate. */
let _genIDCounter = 0;
export function genID(prefix: string): string {
  return `${prefix}-${Date.now()}-${++_genIDCounter}`;
}

/** Default RLS columns for anonymous/system writes. */
export function rlsDefaults(actorId: string): { orgId: string; userId: string; actorId: string } {
  return { orgId: "anon", userId: "anon", actorId };
}

/** Safe number coercion — null/undefined/NaN → 0. Companion to str(). */
export function num(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

/** Extract first row from SQL query result, or null if empty. */
export function firstRow(rows: Record<string, unknown>[]): Record<string, unknown> | null {
  return rows.length > 0 ? rows[0] : null;
}

/**
 * Parse yata query result JSON (columns/rows format) into flat records.
 * Handles valueB64 (base64 AT record JSON) decoding automatically.
 */
export function parseYataRows(resultJson: string): Record<string, unknown>[] {
  try {
    const p = JSON.parse(resultJson) as { columns?: string[]; rows?: unknown[][] };
    if (!Array.isArray(p?.rows)) return [];
    const cols = p.columns ?? [];
    return p.rows.map((row: unknown[]) => {
      if (!Array.isArray(row)) return row as Record<string, unknown>;
      if (row.length === 1 && typeof row[0] === "object" && row[0] !== null) {
        const node = row[0] as Record<string, unknown>;
        if (typeof node.valueB64 === "string") {
          try {
            const decoded = JSON.parse(atob(node.valueB64 as string));
            return { ...node, ...decoded };
          } catch (e) { console.warn("valueB64 decode failed:", e); }
        }
        return node;
      }
      const obj: Record<string, unknown> = {};
      for (let i = 0; i < cols.length; i++) obj[cols[i]] = row[i];
      return obj;
    });
  } catch (e) { console.warn("parseYataRows failed:", e); }
  return [];
}
