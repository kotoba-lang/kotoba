# ADR 0256: T8.3 host pure-EDN codec wire + codec-aot honesty

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0246–0255 ops-kit W4 record-kv packages

## Context

Ops kits completed pure recursive request/reply EDN packages through W4 0255,
but:

1. Hosts had no first-class way to **invoke** those codecs without copying
   encode logic into Clojure.
2. `:wasm-aot :partial` notes still implied **codec AOT was open**, which is
   stale after 0250–0255.
3. Host I/O / fetch / spawn / store / CSPRNG remain intentionally host-injected
   and must **not** be claimed as guest wasm-aot `:implemented`.

## Decision

1. Ship **`provider.edn-codec`** (JVM):
   - Resolve package by registry name, materialize wasm bytes, invoke export
     via Node + `browser-host.mjs` (typed string/i64 ABI).
   - High-level helpers: secret request/reply, entropy request, process request.
   - **No** network/fs/spawn/CSPRNG — pure codec only.
2. Add qualification key **`:codec-aot :implemented`** on ops kits
   (http/secret/process/git/entropy/scoped-fs). Surface via
   `kit-package` select-keys.
3. Keep **`:wasm-aot :partial`**: residual is **host-injected authority**, not
   pure EDN encode/decode.
4. Update `kit_package.cljc` layer docs that claimed codec AOT still open.

## Evidence

- Unit tests: secret-request EDN shape via host wire when browser-host present
- `codec-aot-complete?` → true

## Related

- T8.3 residual host authority; ADR 0250–0255; browser-host typed ABI
