# Vendored: `@noble/curves` ed25519 + `@noble/hashes`

Verbatim (unmodified except import-path patching, see below), not hand-transcribed
-- `actor-host.js` needs a genuinely synchronous Ed25519 (`gen_keypair`/`sign`/
`verify`) to wire as WASM host-import functions, and `Web Crypto`'s
`SubtleCrypto` is async-only (see `actor-host.js`'s own header comment). Ed25519
is real elliptic-curve arithmetic, not something to hand-roll the way
`sha256_hex` hand-rolls SHA-256 -- so this vendors the actual audited,
widely-used [`@noble/curves`](https://github.com/paulmillr/noble-curves) (MIT,
Paul Miller) `ed25519.js` entry point and its full transitive dependency
closure, copied file-for-file from the published npm packages (no bundler
needed -- browsers resolve relative ESM imports natively):

- `@noble/curves@1.9.7`: `ed25519.js`, `utils.js`, `abstract/{curve,edwards,
  hash-to-curve,modular,montgomery}.js`
- `@noble/hashes@1.8.0`: `sha2.js`, `utils.js`, `_md.js`, `_u64.js`,
  `crypto.js` (ed25519 signing hashes with SHA-512)

Both packages are MIT-licensed (see `curves/LICENSE` / `hashes/LICENSE`).

**Vendored (not CDN-imported)** deliberately, even though this repo already
consumes *itself* via a pinned jsdelivr commit elsewhere (see the top-level
README) -- an `https:` import specifier works in a real browser with no flag,
but Node's default ESM loader refuses `https:` specifiers outright (no
`--experimental-network-imports`), which would break the project's own
`node test/verify-*.mjs` convention. Vendoring keeps both the browser and the
Node test runner working identically off the same relative-path imports, with
zero network dependency at run time either way.

**Only 3 lines patched** across the whole closure: the bare `@noble/hashes/...`
specifiers (`ed25519.js`×2, `curves/utils.js`×2 on one line, `hashes/utils.js`×1)
rewritten to relative paths pointing at the sibling `hashes/` directory copied
alongside. Nothing else was touched (`.d.ts`/`.map` files were dropped -- not
needed at runtime). Diff against the real npm packages to re-verify.

To re-vendor after a version bump: copy the same file list from
`node_modules/@noble/{curves,hashes}/esm/...`, re-apply the same 3 import-path
edits, and re-run `test/verify-actor-host.mjs`.
