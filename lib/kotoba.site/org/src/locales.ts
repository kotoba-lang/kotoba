/**
 * kotoba-lang.org locale registry.
 *
 * ADR-2609091700 shipped en, zh-Hans, hi, es, ar, fr, bn, pt, id, ur, ru,
 * de, ja, ko, pcm, arz, mr. This registry keeps those tags and adds jv, su,
 * he, it, plus ar-MA (Darija) as a regional Arabic sibling of ar / arz.
 *
 * Country negotiation never selects jv or su. Those tags are path, cookie,
 * or Accept-Language only.
 */

export const COOKIE_NAME = "kotoba_lang";
export const DEFAULT_LOCALE = "en";
export const SITE_ORIGIN = "https://kotoba-lang.org";

export type LocaleDir = "ltr" | "rtl";

export interface Locale {
  tag: string;
  name: string;
  label: string;
  dir: LocaleDir;
  /** ISO 3166-1 alpha-2 countries that may select this tag. */
  countries: readonly string[];
  /** When true, request.cf.country must never resolve to this tag. */
  neverCountry: boolean;
}

function locale(
  tag: string,
  name: string,
  label: string,
  opts: { dir?: LocaleDir; countries?: readonly string[]; neverCountry?: boolean } = {},
): Locale {
  return {
    tag,
    name,
    label,
    dir: opts.dir ?? "ltr",
    countries: opts.countries ?? [],
    neverCountry: opts.neverCountry ?? false,
  };
}

/** ADR-2609091700 plus jv, su, he, it, ar-MA. */
export const LOCALES: readonly Locale[] = [
  locale("en", "English", "English"),
  locale("zh-Hans", "Simplified Chinese", "简体中文"),
  locale("hi", "Hindi", "हिन्दी"),
  locale("es", "Spanish", "Español", { countries: ["ES"] }),
  locale("ar", "Modern Standard Arabic", "العربية الفصحى", { dir: "rtl" }),
  locale("fr", "French", "Français"),
  locale("bn", "Bengali", "বাংলা"),
  locale("pt", "Portuguese (region-neutral)", "Português"),
  locale("id", "Indonesian", "Bahasa Indonesia", { countries: ["ID"] }),
  locale("ur", "Urdu", "اردو", { dir: "rtl" }),
  locale("ru", "Russian", "Русский"),
  locale("de", "German", "Deutsch", { countries: ["DE"] }),
  locale("ja", "Japanese", "日本語"),
  locale("ko", "Korean", "한국어", { countries: ["KR"] }),
  locale("pcm", "Nigerian Pidgin (not English)", "Naijá"),
  locale("arz", "Egyptian Arabic (not Modern Standard Arabic)", "العربية المصرية", {
    dir: "rtl",
    countries: ["EG"],
  }),
  locale("mr", "Marathi", "मराठी"),
  locale("jv", "Javanese", "Basa Jawa", { neverCountry: true }),
  locale("su", "Sundanese", "Basa Sunda", { neverCountry: true }),
  locale("he", "Hebrew", "עברית", { dir: "rtl", countries: ["IL"] }),
  locale("it", "Italian", "Italiano", { countries: ["IT"] }),
  locale("ar-MA", "Moroccan Arabic (Darija)", "الدارجة المغربية", {
    dir: "rtl",
    countries: ["MA"],
  }),
];

export const LOCALE_TAGS: readonly string[] = LOCALES.map((item) => item.tag);

export const LOCALE_BY_TAG: Readonly<Record<string, Locale>> = Object.fromEntries(
  LOCALES.map((item) => [item.tag, item]),
);

/** Tags that must keep emitting after the expansion (live 200s today). */
export const STILL_EMIT: readonly string[] = ["id", "es", "de", "ko", "arz"];

/** New path locales this change ships. */
export const NEW_LOCALES: readonly string[] = ["jv", "su", "he", "it", "ar-MA"];

export function isLocale(tag: string | undefined | null): tag is string {
  return Boolean(tag && Object.prototype.hasOwnProperty.call(LOCALE_BY_TAG, tag));
}

export function getLocale(tag: string): Locale {
  const found = LOCALE_BY_TAG[tag];
  if (!found) throw new Error(`unknown locale: ${tag}`);
  return found;
}

export function localePath(tag: string, pagePath = "/"): string {
  const normalized = pagePath.startsWith("/") ? pagePath : `/${pagePath}`;
  if (tag === DEFAULT_LOCALE) return normalized === "/index.html" ? "/" : normalized;
  if (normalized === "/" || normalized === "/index.html") return `/${tag}/`;
  return `/${tag}${normalized}`;
}

export function localeFromPath(pathname: string): string | undefined {
  const match = pathname.match(/^\/([^/]+)(?:\/|$)/);
  if (!match) return undefined;
  const tag = match[1];
  return isLocale(tag) ? tag : undefined;
}

/**
 * Country → locale. MA prefers ar-MA and falls back to ar when that tag is
 * absent. jv/su are excluded even if a caller invents a country row.
 */
export function localeFromCountry(country: string | undefined | null): string | undefined {
  if (!country) return undefined;
  const cc = country.trim().toUpperCase();
  if (!cc) return undefined;
  if (cc === "MA") {
    if (isLocale("ar-MA")) return "ar-MA";
    if (isLocale("ar")) return "ar";
    return undefined;
  }
  for (const item of LOCALES) {
    if (item.neverCountry) continue;
    if (item.countries.includes(cc)) return item.tag;
  }
  return undefined;
}

export function hreflangTags(): readonly string[] {
  return LOCALE_TAGS;
}

export function hreflangHref(tag: string, pagePath = "/"): string {
  return `${SITE_ORIGIN}${localePath(tag, pagePath)}`;
}
