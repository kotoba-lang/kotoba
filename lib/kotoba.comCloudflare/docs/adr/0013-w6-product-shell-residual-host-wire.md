# ADR 0013: W6 product-shell residual host-wire (stream/deploy/analytics)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0012 shipped all 9 KIR artifacts and host-wired client + REST path cores.
Residual catalog-only pure surfaces remained on stream, deploy, pages-bulk, and
analytics.

## Decision

Host-wire remaining pure exports:

| catalog | host | pure delegates |
|---|---|---|
| `:stream` | `cloudflare.stream` | redact-key, validate-flags→problems, destination-url, inputs/live-input/outputs paths, live-input-summary |
| `:deploy` | `cloudflare.deploy` | max-* constants, validate-*, path builders, multipart-part/encode, put content-type, size/count gates, directory-ok? |
| `:pages-bulk` | `cloudflare.deploy` | pages max-*, validate-asset-path, content-type-for-path, upload-token/upload-assets paths |
| `:analytics` | `cloudflare.analytics` | daily-query, path-query |
| `:analytics-parse` | `cloudflare.analytics` | report-ok? error gate |

### Still host

- `*!` HTTP, JSON encode/decode
- parse row projection + host tally maps (typed-map folds remain parity-only)
- sha256-hex / base64 body encoding
- plan map assembly

## Evidence

- authority + parity + unit: full suite green
- ADR 0012 product-shell loader

## Related

- com-cloudflare#14 first dual-source slice
- murakumo product-shell trail #86–#113
