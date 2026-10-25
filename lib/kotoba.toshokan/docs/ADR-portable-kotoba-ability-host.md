# ADR — portable Kotoba ability host for toshokan

- Status: Implemented, NDL vertical slice
- Date: 2026-07-25

## Decision

Toshokan separates application semantics from host mechanisms:

1. `src/toshokan/portable_effect.kotoba` is the authoritative NDL scope and
   limit policy. Its exported `test-*` definitions are executed from one
   source on KIR/JVM, restricted ESM, and Wasm by `kotoba test`.
2. `toshokan.sources.ndl-core` remains the pure portable response parser.
3. `toshokan.portable` creates a data-only `kotoba.portable-effect/v1`
   request containing a component-bound ability.
4. CLJ/CLJS hosts dispatch through
   `kotoba.lang.portable-effect/dispatch`, whose only provider path is
   `guard-component-ability-call`.
5. The workerd adapter calls compiler-generated restricted ESM for scope and
   limit admission, then owns only the unavoidable host work: closed wire
   decoding, final URL validation, timeout/byte enforcement, `fetch`, and
   receipts. `scripts/build-portable-effect.sh` creates that generated module.
6. Wasm/Kototama remains the confined target for untrusted guests. Portability
   does not downgrade that stronger execution profile.

## Invariant

An endpoint string is never authority. A network operation requires the
effect row, component ability, logical resource, target, operation, limits,
host provider, and last-boundary URL validation to agree.

## Honest boundary

The policy and its tests are Kotoba today. The NDL parser is still portable
CLJC because the compiler's bounded XML profile cannot yet express the
text-bearing SRU/DC-NDL payload. Also, host adapters cannot disappear:
network I/O, credentials, byte accounting, timeouts, and sandboxing are
machine authority and therefore intentionally remain outside the guest.

There is one semantic policy test definition, but three executions. The
existing NBB suite keeps its parser fixtures; the workerd `.mjs` test is only
an adapter-binding smoke test. There are no separate CLJS or JVM policy tests.
