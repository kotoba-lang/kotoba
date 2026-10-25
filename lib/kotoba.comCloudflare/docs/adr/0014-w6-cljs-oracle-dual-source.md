# ADR 0014: W6 cljs dual-source product-shell for com-cloudflare

- Status: Accepted
- Date: 2026-07-28

## Context

Murakumo completed cljs/nbb product-shell dual-source (#122–#133). Cloudflare
hosts still used `#?(:clj [cloudflare.kotoba.oracle …])` and threw on cljs
resource load ("JVM-only in this slice").

## Decision

1. **Optional cljs oracle load** on `cloudflare.kotoba.oracle`:
   - `register-kir!` / `set-resource-loader!` / `clear-cache!`
   - nbb/node default: `resources/<catalog-path>` from `process.cwd()`
   - `as-i64` / `i64->host` BigInt bridge
2. **Dual-source pure helpers** via `try-oracle` + host mirrors when ready:
   - client constants + URL/auth pure
   - workers/zones/logpush/pages path pure
   - stream destination/redact/validate/paths/summary pure
   - analytics query text + report-ok gate
   - deploy constants/validators/paths/MIME/size gates pure
3. **Still host**: HTTP/JSON/getenv, multipart encode, SHA-256 MessageDigest,
   JVM `rest!` convenience layers.

Ship `nbb.edn` for smoke (kotoba-kir + resources/).

## Evidence

- JVM suite green (authority + parity + unit)
- `test/cloudflare/kotoba_oracle_cljs_load_test.cljk`
- nbb smoke: ready? + bearer-auth/path helpers

## Related

- ADR 0012/0013 product-shell host-wire
- murakumo ADR-260728-w6-cljs-oracle-load + dual-source trail
