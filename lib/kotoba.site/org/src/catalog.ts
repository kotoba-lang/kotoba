import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { LOCALES, isLocale } from "./locales.ts";

export interface Catalog {
  title: string;
  description: string;
  hero: string;
  noAmbient: string;
  grantNarrowly: string;
  language: string;
  searchLanguages: string;
  noMatching: string;
  github: string;
  browseRepo: string;
  authorityNote: string;
  installLabel: string;
  installHint: string;
  copy: string;
  copied: string;
  playTitle: string;
  playCaption: string;
  playRun: string;
  playReady: string;
  playVerifying: string;
  playSuccess: string;
  playError: string;
  playDemos: string;
  docs: string;
}

const REQUIRED_KEYS: (keyof Catalog)[] = [
  "title",
  "description",
  "hero",
  "noAmbient",
  "grantNarrowly",
  "language",
  "searchLanguages",
  "noMatching",
  "github",
  "browseRepo",
  "authorityNote",
  "installLabel",
  "installHint",
  "copy",
  "copied",
  "playTitle",
  "playCaption",
  "playRun",
  "playReady",
  "playVerifying",
  "playSuccess",
  "playError",
  "playDemos",
  "docs",
];

export function catalogsDir(): string {
  return join(dirname(fileURLToPath(import.meta.url)), "..", "catalogs");
}

export function parseCatalog(raw: unknown, tag: string): Catalog {
  if (!raw || typeof raw !== "object") throw new Error(`${tag}: catalog must be an object`);
  const record = raw as Record<string, unknown>;
  const out = {} as Catalog;
  for (const key of REQUIRED_KEYS) {
    const value = record[key];
    if (typeof value !== "string" || value.trim() === "") {
      throw new Error(`${tag}: missing catalog string ${key}`);
    }
    out[key] = value;
  }
  return out;
}

export function loadCatalog(tag: string): Catalog {
  if (!isLocale(tag)) throw new Error(`unknown locale: ${tag}`);
  const text = readFileSync(join(catalogsDir(), `${tag}.json`), "utf8");
  return parseCatalog(JSON.parse(text), tag);
}

export function loadAllCatalogs(): Record<string, Catalog> {
  const dir = catalogsDir();
  const files = readdirSync(dir).filter((name) => name.endsWith(".json"));
  const catalogs: Record<string, Catalog> = {};
  for (const locale of LOCALES) {
    const file = `${locale.tag}.json`;
    if (!files.includes(file)) throw new Error(`missing catalog file ${file}`);
    catalogs[locale.tag] = loadCatalog(locale.tag);
  }
  return catalogs;
}
