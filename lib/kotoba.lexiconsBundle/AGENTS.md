# @etzhayyim/lexicons-bundle

Runtime `@atproto/lexicon` `Lexicons` instance built from `00-contracts/lexicons` (SSoT). Used by `@etzhayyim/xrpc` consumers so XRPC client+server calls validate against our schemas natively — extension fields (`performerType`, `viewerFollowing`, `nanoid`, etc.) pass because they're declared in the lexicon, not because validation is bypassed.

## Files

- `src/index.ts` — exports `getLexicons(): Lexicons` (lazy-init, shared)
- `src/lexicons.gen.json` — generated bundle (3318 docs, ~2.3 MiB raw / ~500 KiB gzipped). **Do not edit by hand.**
- `scripts/build-bundle.mjs` — regenerates `lexicons.gen.json` by walking `00-contracts/lexicons/**/*.json`

## Regenerate

```bash
npm run build -- /path/to/00-contracts/lexicons
# or: ETZHAYYIM_LEXICONS_DIR=/path/to/00-contracts/lexicons npm run build
```

Run after any change under `00-contracts/lexicons/`.

## Why this exists

`@atproto/api` ships the upstream Bluesky `Lexicons`. Yoro's PDS extends `app.bsky.actor.profile` with `performerType`, `viewerFollowing`, `nanoid`, etc. AT Protocol lexicon validation **does** allow unknown fields by default (open object semantics), but the upstream bundle disagrees in places — and historically wproto worked around this with a raw-fetch fallback that masked real schema bugs.

This package replaces the bundled lexicons with our SSoT so the validator becomes a strict guardrail: validation failures now surface real PDS/AppView bugs (e.g. empty-string URI fields, missing required keys) instead of silently degrading.

Consumers should call `getLexicons()` and pass the result to XRPC clients. Do not instantiate ad-hoc `Lexicons` from a subset of files.
