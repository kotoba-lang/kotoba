# ADR 0016: T6.4 oracle-required product-shell (mirror-delete)

- Status: accepted
- Date: 2026-07-31
- Depends: ADR-0012 product-shell; ADR-0014 cljs dual-source; ADR-0015 call-record; murakumo T6.4 trail
- WBS: T6.4 — same pure artifact on cljs/browser after preload

## Decision

Delete host pure mirrors under `try-oracle` on all com-cloudflare product-shell
hosts. Pure helpers **require** shipped KIR on every platform:

| Module | Oracle id(s) |
|--------|----------------|
| `client` | `:client` |
| `workers` | `:workers-path` |
| `zones` | `:zones-path` |
| `logpush` | `:logpush-path` |
| `pages` | `:pages-bulk` (path) / pages helpers |
| `stream` | `:stream` |
| `analytics` | `:analytics` / `:analytics-parse` |
| `deploy` | `:deploy` + `:pages-bulk` |

`cloudflare.kotoba.oracle` gains `require-ready!`, `preload!`, `preload-catalog!`
(same contract as murakumo).

**Still host (not pure):** HTTP/JSON, getenv token fetch, MessageDigest SHA-256,
JVM `rest!` convenience, live deploy I/O. `stream/destinations` remains a host
catalog map for callers; `destination-url` is oracle-only.

## Non-claims

- Does not flip T8.3 signed-wasm production readiness.
- Does not implement native guest record parameter wire (T5.2 remainder).
- nbb/browser must preload KIR before requiring product-shell ns.

## Evidence

JVM suite (authority + parity + unit + call-record) green after mirror-delete.
