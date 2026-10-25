import type { Catalog } from "./catalog.ts";
import { DEFAULT_LOCALE, LOCALES, SITE_ORIGIN, getLocale, localePath } from "./locales.ts";
import {
  DOCS_HREF,
  FREEBUFF_BOOTSTRAP,
  GITHUB_HREF,
  INSTALL_COMMAND,
  PLAY_BOOT_URL,
  PLAY_HREF,
  PLAY_WASM_SHA256,
  PLAY_WASM_URL,
  WASM_WEBCOMPONENT_DEMOS,
  playSource,
} from "./play.ts";

export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function hreflangLinks(tag: string, pagePath = "/"): string {
  const alternatePath = pagePath === PLAY_HREF ? "/" : pagePath;
  const links = LOCALES.map((locale) => {
    const href = `${SITE_ORIGIN}${localePath(locale.tag, alternatePath)}`;
    return `  <link rel="alternate" hreflang="${escapeHtml(locale.tag)}" href="${escapeHtml(href)}">`;
  });
  const defaultHref = `${SITE_ORIGIN}${localePath(DEFAULT_LOCALE, alternatePath)}`;
  links.push(`  <link rel="alternate" hreflang="x-default" href="${escapeHtml(defaultHref)}">`);
  const canonical = `${SITE_ORIGIN}${localePath(tag, pagePath)}`;
  links.unshift(`  <link rel="canonical" href="${escapeHtml(canonical)}">`);
  return links.join("\n");
}

export function languageSwitcher(tag: string, catalog: Catalog, pagePath = "/"): string {
  const current = getLocale(tag);
  const items = LOCALES.map((locale) => {
    const href = localePath(locale.tag, pagePath);
    const currentAttr = locale.tag === tag ? ' aria-current="page" data-current="true"' : "";
    return `        <li><a hreflang="${escapeHtml(locale.tag)}" lang="${escapeHtml(locale.tag)}" href="${escapeHtml(href)}"${currentAttr}>${escapeHtml(locale.label)}</a></li>`;
  }).join("\n");
  return `<nav class="switcher" translate="no" lang="en" dir="ltr" aria-label="${escapeHtml(catalog.language)}">
      <details>
        <summary data-language-selector-opener aria-label="${escapeHtml(`${catalog.language}: ${current.label}`)}"><span data-language-selector-current>${escapeHtml(current.label)}</span></summary>
        <div class="switcher-panel">
          <p class="switcher-search-hint">${escapeHtml(catalog.searchLanguages)}</p>
          <ul>
${items}
          </ul>
        </div>
      </details>
    </nav>`;
}

const PAGE_CSS = `html{color-scheme:light dark}
body{margin:0;font-family:system-ui,sans-serif;line-height:1.6;background:#fff;color:#1a1a1a}
@media (prefers-color-scheme:dark){body{background:#1a1a1a;color:#f2f2f2}}
main,header{max-width:52rem;margin-inline:auto;padding:1.25rem}
header{display:flex;flex-wrap:wrap;gap:1rem;align-items:center;justify-content:space-between;border-bottom:1px solid #ccc}
.nav-actions{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center}
h1{font-size:1.75rem;line-height:1.3;margin:.4rem 0}
.lead{font-size:1.1rem}
.claims{padding-inline-start:1.2rem}
.note{border-inline-start:4px solid #3460fb;padding-inline-start:1rem;color:#333}
@media (prefers-color-scheme:dark){.note{color:#ddd}}
.fold{display:grid;gap:1rem;margin-block:.75rem 1.25rem}
@media (min-width:40rem){.fold{grid-template-columns:1fr 1fr;align-items:stretch}}
.install,.play{border:1px solid #ccc;border-radius:.5rem;padding:.85rem}
.install-row{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
#kot-install-command{flex:1 1 12rem;margin:0;padding:.55rem .7rem;overflow:auto;background:#f4f4f4;font-size:.85rem}
@media (prefers-color-scheme:dark){#kot-install-command{background:#111}}
.play-source{width:100%;min-height:6.5rem;box-sizing:border-box;font-family:ui-monospace,monospace;font-size:.85rem;padding:.6rem;direction:ltr;text-align:left}
.play-host{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.play-actions{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-top:.75rem}
button{min-height:44px;padding:.4rem .9rem;font:inherit;cursor:pointer}
.switcher details{position:relative}
.switcher summary{cursor:pointer;min-height:44px;display:flex;align-items:center}
.switcher-panel{position:absolute;inset-inline-end:0;z-index:2;background:#fff;color:#1a1a1a;border:1px solid #999;border-radius:.5rem;padding:.75rem;max-height:70dvh;overflow:auto;min-width:16rem}
@media (prefers-color-scheme:dark){.switcher-panel{background:#111;color:#f2f2f2}}
.switcher ul{list-style:none;margin:0;padding:0}
.switcher a{display:flex;align-items:center;min-height:44px;padding-inline:.25rem}
.switcher a[aria-current="page"]{font-weight:700}
code,pre{font-family:ui-monospace,monospace}`;

function firstView(catalog: Catalog): string {
  const source = playSource();
  return `<section class="fold" aria-label="${escapeHtml(catalog.installLabel)} / ${escapeHtml(catalog.playTitle)}">
      <div class="install" id="install">
        <p><strong>${escapeHtml(catalog.installLabel)}</strong></p>
        <div class="install-row">
          <pre id="kot-install-command" dir="ltr"><code>${escapeHtml(INSTALL_COMMAND)}</code></pre>
          <button type="button" id="kot-install-copy" data-copied="${escapeHtml(catalog.copied)}">${escapeHtml(catalog.copy)}</button>
        </div>
        <p class="hint">${escapeHtml(catalog.installHint)}</p>
      </div>
      <div class="play" id="play" data-wasm="${escapeHtml(PLAY_WASM_URL)}" data-sha="${escapeHtml(PLAY_WASM_SHA256)}">
        <p><strong>${escapeHtml(catalog.playTitle)}</strong></p>
        <p class="hint">${escapeHtml(catalog.playCaption)}</p>
        <textarea class="play-source" id="kot-play-source" spellcheck="false" translate="no" dir="ltr" readonly>${escapeHtml(source)}</textarea>
        <div id="kot-play-host" class="play-host" aria-hidden="true"></div>
        <div class="play-actions">
          <button type="button" id="kot-play-run">${escapeHtml(catalog.playRun)}</button>
          <p id="kot-play-status" role="status" aria-live="polite" data-verifying="${escapeHtml(catalog.playVerifying)}" data-success="${escapeHtml(catalog.playSuccess)}" data-error="${escapeHtml(catalog.playError)}">${escapeHtml(catalog.playReady)}</p>
        </div>
        <p class="hint">${escapeHtml(catalog.playDemos)} ${WASM_WEBCOMPONENT_DEMOS.map(
          (demo) =>
            `<a href="${escapeHtml(demo.href)}" rel="noreferrer">${escapeHtml(demo.label)}</a>`,
        ).join(" · ")}</p>
      </div>
    </section>`;
}

export function renderPage(tag: string, catalog: Catalog, pagePath = "/"): string {
  const locale = getLocale(tag);
  const dirAttr = locale.dir === "rtl" ? ' dir="rtl"' : "";
  return `<!DOCTYPE html>
<html lang="${escapeHtml(tag)}"${dirAttr}>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>${escapeHtml(catalog.title)}</title>
  <meta name="description" content="${escapeHtml(catalog.description)}">
${hreflangLinks(tag, pagePath)}
  <style>${PAGE_CSS}</style>
  <script>${FREEBUFF_BOOTSTRAP}</script>
</head>
<body>
  <header>
    <a href="${escapeHtml(localePath(tag, "/"))}">Kotoba</a>
    <div class="nav-actions">
      <a data-micro="docs" href="${escapeHtml(DOCS_HREF)}">${escapeHtml(catalog.docs)}</a>
      <a href="${escapeHtml(pagePath === PLAY_HREF ? "#play" : PLAY_HREF)}">${escapeHtml(catalog.playTitle)}</a>
      <a data-micro="github" href="${escapeHtml(GITHUB_HREF)}">${escapeHtml(catalog.github)}</a>
      ${languageSwitcher(tag, catalog, pagePath)}
    </div>
  </header>
  <main>
    ${firstView(catalog)}
    <p class="kicker">${escapeHtml(catalog.hero)}</p>
    <h1>${escapeHtml(catalog.title)}</h1>
    <p class="lead">${escapeHtml(catalog.description)}</p>
    <ul class="claims">
      <li>${escapeHtml(catalog.noAmbient)}</li>
      <li>${escapeHtml(catalog.grantNarrowly)}</li>
    </ul>
    <p><a data-micro="github" href="${escapeHtml(GITHUB_HREF)}">${escapeHtml(catalog.browseRepo)}</a> (${escapeHtml(catalog.github)})</p>
    <p class="note">${escapeHtml(catalog.authorityNote)}</p>
  </main>
  <script type="module" src="${escapeHtml(PLAY_BOOT_URL)}"></script>
</body>
</html>
`;
}

export function emitTags(html: string): string[] {
  return [...html.matchAll(/hreflang="([^"]+)"/g)].map((match) => match[1]);
}
