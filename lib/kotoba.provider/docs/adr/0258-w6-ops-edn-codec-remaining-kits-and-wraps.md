# ADR 0258: T8.3 edn-codec remaining ops kits + audit wraps

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0256 host pure-EDN wire; ADR 0257 secret/http wraps; W4 packages 0250–0255

## Context

ADR 0256/0257 covered secret + HTTP (+ partial process/entropy request helpers).
Remaining ops kits (git, scoped-fs, process replies, entropy replies) still
lacked host pure-codec helpers and audit wraps, so hosts could not attach
symmetric W4 request/reply EDN to those authorities without reimplementing
encode.

## Decision

1. Extend **`provider.edn-codec`** with pure helpers:
   - process reply ok/error
   - git request + reply ok/error
   - entropy reply hex/error
   - scoped-fs read/write request + content/written/error reply
2. Audit wraps (host authority unchanged; codec/on-call failures swallowed):
   - `wrap-process-spawn`
   - `wrap-git-run`
   - `wrap-entropy-draw`
   - `wrap-scoped-fs-transact`
3. **HTTP** wrap also attaches pure W4 `reply-edn` (ok/err arms) when status
   is known.
4. Does **not** flip `:wasm-aot :implemented` — host-injected I/O remains.

## Evidence

- Unit tests: git/fs host wire optional; process/git/entropy/fs wrap audits
  when browser-host available

## Related

- T8.3 host authority residual; ADR 0256–0257; W4 0250–0255
