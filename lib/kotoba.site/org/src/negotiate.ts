/**
 * Origin language negotiation for kotoba-lang.org.
 *
 * Order (Worker, before static cache pin):
 *   path > cookie (if used) > Accept-Language > request.cf.country > en
 *
 * Country never selects jv or su.
 */

import {
  COOKIE_NAME,
  DEFAULT_LOCALE,
  LOCALE_BY_TAG,
  localeFromCountry,
  localeFromPath,
  isLocale,
} from "./locales.ts";

export interface NegotiateInput {
  pathname: string;
  cookieHeader?: string | null;
  acceptLanguage?: string | null;
  country?: string | null;
}

export interface NegotiateResult {
  tag: string;
  source: "path" | "cookie" | "accept-language" | "country" | "default";
}

export function parseCookie(header: string | undefined | null, name = COOKIE_NAME): string | undefined {
  if (!header) return undefined;
  for (const part of header.split(";")) {
    const trimmed = part.trim();
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    if (trimmed.slice(0, eq) !== name) continue;
    const value = decodeURIComponent(trimmed.slice(eq + 1).trim());
    return value || undefined;
  }
  return undefined;
}

export function cookieHeader(tag: string): string {
  return `${COOKIE_NAME}=${encodeURIComponent(tag)}; Path=/; Max-Age=31536000; SameSite=Lax`;
}

interface LanguageRange {
  tag: string;
  q: number;
}

export function parseAcceptLanguage(header: string | undefined | null): LanguageRange[] {
  if (!header) return [];
  const ranges: LanguageRange[] = [];
  for (const part of header.split(",")) {
    const [rawTag, ...params] = part.trim().split(";");
    if (!rawTag) continue;
    let q = 1;
    for (const param of params) {
      const [key, value] = param.trim().split("=");
      if (key === "q" && value) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) q = parsed;
      }
    }
    if (q <= 0) continue;
    ranges.push({ tag: rawTag.trim(), q });
  }
  ranges.sort((a, b) => b.q - a.q);
  return ranges;
}

/**
 * Map an Accept-Language range onto a registered locale.
 * Exact tag wins, then prefix (it-IT → it, ar-MA-xxx → ar-MA).
 * zh-CN / zh-SG map to zh-Hans. jv and su may match here; they must not
 * match via country.
 */
export function matchAcceptLanguage(header: string | undefined | null): string | undefined {
  for (const range of parseAcceptLanguage(header)) {
    const lowered = range.tag.toLowerCase();
    if (lowered === "*") continue;
    if (isLocale(range.tag)) return range.tag;
    const canonical = Object.keys(LOCALE_BY_TAG).find((tag) => tag.toLowerCase() === lowered);
    if (canonical) return canonical;

    if (lowered === "zh-cn" || lowered === "zh-sg" || lowered === "zh-hans") return "zh-Hans";
    if (lowered.startsWith("zh-hans")) return "zh-Hans";

    const language = lowered.split("-")[0];
    if (language === "zh") continue;
    if (isLocale(range.tag.split("-")[0])) return range.tag.split("-")[0];

    const prefixHit = Object.keys(LOCALE_BY_TAG).find((tag) => {
      const tagLower = tag.toLowerCase();
      return tagLower === lowered || lowered.startsWith(`${tagLower}-`);
    });
    if (prefixHit) return prefixHit;
  }
  return undefined;
}

export function negotiate(input: NegotiateInput): NegotiateResult {
  const path = localeFromPath(input.pathname);
  if (path) return { tag: path, source: "path" };

  const cookie = parseCookie(input.cookieHeader);
  if (cookie && isLocale(cookie)) return { tag: cookie, source: "cookie" };

  const accepted = matchAcceptLanguage(input.acceptLanguage);
  if (accepted) return { tag: accepted, source: "accept-language" };

  const country = localeFromCountry(input.country);
  if (country) return { tag: country, source: "country" };

  return { tag: DEFAULT_LOCALE, source: "default" };
}
