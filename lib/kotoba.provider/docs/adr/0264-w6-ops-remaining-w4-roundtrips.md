# ADR 0264: T8.3 remaining ops W4 round-trips (secret/process/git/entropy/fs)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0251–0255 W4 packages; 0256–0259 codecs/wraps; 0263 HTTP round-trip

## Context

ADR 0263 fixed the production composition for HTTP:

1. Guest pure W4 request EDN
2. Host transport (authority)
3. Guest pure W4 reply EDN

Other ops kits still only had **audit wraps** (0257–0258) and factories
(0259/0261) that return the host reply while side-channeling EDN events.
Hosts that want an explicit round-trip result map (request-edn + reply-edn +
host result) lacked a symmetric API for secret/process/git/entropy/scoped-fs.

## Decision

1. Ship explicit W4 round-trip APIs on **`provider.edn-codec`**:
   - `secret-w4-roundtrip` / `secret-w4-roundtrip-with-map`
   - `process-w4-roundtrip` / `process-w4-roundtrip-echo`
   - `git-w4-roundtrip` / `git-w4-roundtrip-echo`
   - `entropy-w4-roundtrip` / `entropy-w4-roundtrip-mem` (bytes→hex for reply arm)
   - `scoped-fs-w4-roundtrip`
2. Same honesty as 0263: host owns I/O/CSPRNG/spawn/git/store; guest packages
   are pure codecs only.
3. Does **not** flip `:wasm-aot :implemented`.

## Evidence

- Unit tests: map-fetch secret ok/not-found; process/git echo; entropy mem;
  scoped-fs read — when browser-host available

## Related

- T8.3 host authority residual; ADR 0263; ops kit transports
