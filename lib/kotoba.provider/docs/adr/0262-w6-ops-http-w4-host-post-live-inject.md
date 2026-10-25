# ADR 0262: T8.3 live guest host_post inject via browser-host typedCapCall

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0260 http-w4-host-edn package; browser-host typed ABI

## Context

ADR 0260 shipped the guest surface `host_post_edn` (W4 encode +
`typed-cap-call :http/post`). Host pure codec wire (0256) could not invoke it
because capability inject was missing — pure `instantiateKotoba(wasm)` denies
cap 4 by default.

## Decision

1. Extend **`provider.edn-codec`** with capability-aware invoke:
   - `invoke-export*` accepts `allowCapabilities` + `inject-mode`
   - `http-w4-host-post-edn` — live call of `host_post_edn` with inject
     - `:echo` returns request EDN (cap path proof)
     - `:ok-200` returns fixed ok arm string
   - `http-w4-host-post-denied` — no allow list; proves fail-closed
2. Inject is the **host authority boundary** (string→string). No ambient
   network from the guest or from edn-codec itself.
3. Does **not** flip `:wasm-aot :implemented`.

## Evidence

- Optional host tests: echo inject returns W4 request keys; ok-200 inject;
  deny without allow exits non-zero

## Related

- T8.3 host authority residual; ADR 0260; browser-host `typedCapCall`
