# kotoba-lang-org — locales + origin negotiate

Worker **kotoba-lang-org** for kotoba-lang.org. This directory is the locale
registry, catalogs, generated locale pages, and the origin Worker that
negotiates language **before** the static asset cache can pin English on `/`.

This pull request does **not** deploy. Do not treat these pages as live.

## Live measured (2026-09-11)

- `/id/` is 200 Indonesian. `/jv` and `/su` are 404.
- `/` ignores `Accept-Language` and `CF-IPCountry` (stays `en`). CF cache HIT is common.
- hreflang ADR-2609091700 includes id, es, ar, de, ko, arz — not jv / su / he / it.
- The production wrangler config is assets-only (`main` omitted). That is why
  `/` is a single English object at the edge.

## What this change ships

- Registry: ADR-2609091700 tags **plus** `jv`, `su`, `he`, `it`, `ar-MA`.
- Catalogs under `catalogs/{tag}.json` and switcher + hreflang on every page.
- Pages for the new codes (`/jv/`, `/su/`, `/he/`, `/it/`, `/ar-MA/`).
- id / es / de / ko / arz still emit in the hreflang cluster and the switcher.
- Origin negotiate on the Worker, before `ASSETS` cache:

  `path > cookie (kotoba_lang) > Accept-Language > request.cf.country > en`

  Country map: ID→id, IL→he, KR→ko, ES→es, IT→it, DE→de, MA→ar-MA (fallback ar),
  EG→arz. **Never** country→jv/su.

- `/` responses set `CDN-Cache-Control: no-store` and
  `Vary: Accept-Language, Cookie, CF-IPCountry`. Locale-prefixed paths stay
  publicly revalidatable.
- First view (every locale), above the title/lead: one-line Homebrew install
  plus the existing digest-bound Play artifact (`org/play/double-21.wasm`,
  344 bytes, SHA-256 checked before instantiate). Wide layouts put install
  and Play side by side. `/play/` is a 200 page (bare `/play` 308s there) so
  the live 404 is not repeated. Extra demos link the existing
  wasm-webcomponent GitHub Pages examples. The in-page runner vendors
  `KotobaWasmElement` (`org/play/kotoba-wasm-element.js`, Apache-2.0) and
  still verifies the checked-in wasm digest before instantiate. This is
  not a new in-browser compiler.
- Freebuff micro-conversions (`docs_view`, `github_click`, `cli_copy`,
  existing `trial_started`) fire only when `bfcid` is present. No GMV events.

## Cloudflare deploy (human / Jun)

Deploy historically needs a Cloudflare token held by Jun. This agent did not
run `wrangler deploy` and makes no live claim.

When a human deploys from this directory:

```bash
cd org
npm test
npm run generate
npx wrangler deploy
```

Requirements:

1. `assets.run_worker_first: true` (already in `wrangler.jsonc`). Without it
   the Worker never sees `/` and the English HIT returns.
2. After deploy, purge `/` and `/index.html` so an old English HIT is not
   served. Locale paths (`/id/`, `/jv/`, …) can stay cached.
3. The full marketing generator still lives in `kotoba-lang/kotoba-lang/site`
   (`generate.cljk` + hash catalogs). Merging this registry into that
   generator is a separate step. Do not overwrite that `dist/` with
   `org/public/` unless you intend to replace the long-form pages.
4. Copy `locales.edn` / `src/locales.ts` into
   `kotoba-lang/kotoba-lang/site/src/kotoba/site/locales.cljk` when regenerating
   the long-form site so hreflang stays one cluster.

## Honesty

Locale catalogs restate the existing public title / hero / deny-by-default
lines. They do not invent GMV, a language Release URL, or customer-traction
counts. Measured host figures stay in kotoba-lang repository authorities.

Kawasaki personal branding is not added on this host (it was not already
policy in the live pages).

## Tests

```bash
cd org
npm test
```

Tests use Node's built-in runner (`node --experimental-strip-types --test`). No `npm install` is required.
