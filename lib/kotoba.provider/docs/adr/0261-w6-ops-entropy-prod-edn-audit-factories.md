# ADR 0261: T8.3 entropy production/test EDN-audit factories

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0254 entropy W4 package; ADR 0258–0259 wraps/factories

## Context

Production factories covered HTTP/secret/process/git/fs (0259) but not
entropy CSPRNG. Also `wrap-entropy-draw` only handled `{:tag :hex}` while
`os-draw` / `mem-draw` return `{:tag :bytes :bytes [...]}` (provider.entropy
contract), so reply EDN audit was always empty for production draws.

## Decision

1. Fix **`wrap-entropy-draw`** to accept `:bytes` and convert to lowercase hex
   for pure W4 `entropy_reply_hex_edn` (audit only; transport reply unchanged).
2. Ship factories:
   - `entropy-mem-draw-with-edn-audit`
   - `entropy-os-draw-with-edn-audit`
3. Does **not** flip `:wasm-aot :implemented` — CSPRNG remains host-injected.

## Evidence

- Unit tests: mem-draw wrap attaches request EDN + hex reply EDN when
  browser-host available

## Related

- T8.3 host authority residual; ADR 0254; entropy-transport os-draw
