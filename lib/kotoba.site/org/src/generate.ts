import { copyFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadAllCatalogs } from "./catalog.ts";
import { DEFAULT_LOCALE, LOCALES } from "./locales.ts";
import { PLAY_FILES, PLAY_HREF, playDir } from "./play.ts";
import { renderPage } from "./render.ts";

export const PUBLIC_HEADERS = `# kotoba-lang-org locale pages.
#
# Worker kotoba-lang-org negotiates \`/\` before the static cache pin.
# These rules apply to locale-prefixed documents only. Do not cache \`/\`
# as a single English HIT — the Worker sets CDN-Cache-Control: no-store.

/index.html
  Cache-Control: private, no-cache
  CDN-Cache-Control: no-store
  Vary: Accept-Language, Cookie, CF-IPCountry

/play/double-21.wasm
  Cache-Control: public, max-age=86400, must-revalidate
  Content-Type: application/wasm

/play/*.js
  Cache-Control: public, max-age=86400, must-revalidate
  Content-Type: text/javascript; charset=utf-8

/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: same-origin
  X-Frame-Options: SAMEORIGIN
`;

export function publicDir(): string {
  return join(dirname(fileURLToPath(import.meta.url)), "..", "public");
}

export function generatePages(outDir = publicDir()): string[] {
  const catalogs = loadAllCatalogs();
  const written: string[] = [];
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, "_headers"), PUBLIC_HEADERS);
  written.push("_headers");

  const playOut = join(outDir, "play");
  mkdirSync(playOut, { recursive: true });
  for (const name of PLAY_FILES) {
    copyFileSync(join(playDir(), name), join(playOut, name));
    written.push(join("play", name));
  }
  writeFileSync(join(playOut, "index.html"), renderPage(DEFAULT_LOCALE, catalogs[DEFAULT_LOCALE], PLAY_HREF));
  written.push("play/index.html");

  for (const locale of LOCALES) {
    const html = renderPage(locale.tag, catalogs[locale.tag], "/");
    const relative = locale.tag === DEFAULT_LOCALE ? "index.html" : join(locale.tag, "index.html");
    const target = join(outDir, relative);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, html);
    written.push(relative);
  }
  return written;
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const files = generatePages();
  for (const file of files) process.stdout.write(`${file}\n`);
}
