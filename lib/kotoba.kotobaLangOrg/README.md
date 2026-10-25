# kotoba-lang.org

The language's public static site, moved out of
[kotoba-lang/kotoba-lang](https://github.com/kotoba-lang/kotoba-lang) by root
ADR-2610100100 so that the language authority holds the language only.

- `site/` is the site, unchanged (its own README describes it).
- The page's language claims are still derived from the language authority
  files, now read from the kotoba-lang commit pinned in `authority.lock`:
  `scripts/fetch-authority.sh` copies them in before the build (they are
  `.gitignore`d). Advancing that commit is how a spec change reaches the page.
- Build: `sh scripts/fetch-authority.sh && npm ci && npm run site:build`.
  CI requires the committed `site/dist` to be reproduced byte for byte.
- Deploy: Cloudflare Workers Builds (`site/cloudflare-build.json`,
  `site/wrangler.jsonc`).
