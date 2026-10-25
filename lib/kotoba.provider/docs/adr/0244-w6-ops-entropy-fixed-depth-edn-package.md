# ADR 0244: T8.3 entropy kit fixed-depth EDN request+reply package

- Status: Accepted
- Date: 2026-08-01
- Depends: entropy draw bounds 0172; process/git/scoped-fs EDN pattern 0238–0243

## Context

Entropy kit request is `[:record [[:n :i64]]]` with limits `[1,64]`; result is
hex or error. Process/git/scoped-fs/secret gained pure fixed-depth EDN packages.
Entropy needs the same pure codec surface; CSPRNG remains host-injected.

## Decision

1. Ship **entropy-edn-package** (wasm32):
   - `entropy_req_edn(n)` → `{:n N}` when n ∈ [1,64]
   - `entropy_reply_hex_edn(hex)` → `{:tag :hex :hex "…"}` (lowercase hex,
     even length ≤128, dual quote/backslash reject)
   - `entropy_reply_error_edn(code,message)` → error arm
   - `main` → **-2315**
2. Package sha `aa2d8c8e…`.
3. Does **not** flip `:wasm-aot :implemented` (W4 recursive nested EDN open).
   CSPRNG draw remains host-injected.

## Evidence

- browser-host / wasm main → -2315
- ops kit registry + sha tests

## Related

- T8.3; ADR 0167/0172; process 0238; git 0240; scoped-fs 0243; W4 residual
