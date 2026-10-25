# ADR 0284: bounded canonical value wire for ops-kit audit

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0256–0270; kotoba-lang canonical value codec

## Context

The six ops kits already produce typed W4 request/reply values, but the host
audit boundary exposed only EDN text. That preserved the guest codec evidence
while leaving each audit consumer to parse text, choose bounds, and rediscover
the value wire.

## Decision

1. Add `provider.value-codec` over the org-owned `kotoba.value.codec` facade.
2. Encode `:provider.ops-audit/v1` envelopes containing kit, direction, and the
   typed request or reply value.
3. Enforce the provider-owned 1 MiB limit before parsing legacy EDN and again
   after canonical encoding; reject tagged literals and malformed envelopes.
4. Emit `:request-value-bytes` and `:reply-value-bytes` from all six wrapper and
   W4 round-trip paths. Keep `:request-edn` and `:reply-edn` as compatibility
   evidence while the guest W4 packages still export text.
5. Keep host I/O authority, capability admission, and `:wasm-aot` qualification
   unchanged.

## Evidence

- Provider JVM suite: 243 tests / 2,014 assertions, all green.
- Real ClojureScript/Node compile and execution round-trips the new envelope.
- Compiler consumer conformance with this provider checkout: 16 / 16
  `:aarch64-kotoba-v1` pure-native cases.

## Consequences

Ops audit sinks can persist one deterministic typed byte format without loading
CID hashing or npm modules. EDN is now an explicit compatibility input, not the
canonical provider audit representation. Exact full-width i64 remains governed
by the shared codec gap and is never narrowed silently.
