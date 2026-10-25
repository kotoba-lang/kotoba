# base-l2

`kotoba.lang.base-l2` — Base L2 MST-root anchor client + ERC-4337 sponsored-write
helper, as **pure Clojure/CLJC cores over injected transports**.

The library performs **zero network I/O**: every JSON-RPC call goes through a
host-supplied `kotoba.lang.base-l2.rpc/ITransport`, and every sponsored
UserOperation goes through host-supplied `Bundler`/`SmartAccount` protocols
(`paymaster.clj`). The host backs `ITransport` with `babashka.http-client`
(JVM) / `fetch`. This is the kotoba-lang layer contract — pure Clojure, zero
network I/O, zero vendor SDK (ADR-2606302300 §Step-1). The original `viem`
vendor SDK has no place inside the library.

| Namespace | Ext | Role |
|---|---|---|
| `base-l2.abi` | `.cljc` | narrow hand-rolled Ethereum ABI encode/decode — **portable JVM+CLJS**; needs a real Keccak-256/EIP-55, which `eth-crypto.core` has provided on both platforms since `1253e01` (2026-07-26) |
| `base-l2.rpc` | `.cljc` | JSON-RPC orchestration over injected `ITransport` (7 `eth_*` methods) — portable JVM+CLJS, except `wait-for-transaction-receipt` (`Thread/sleep`-blocking, `#?(:clj ...)`-gated JVM-only) |
| `base-l2.l2` | `.clj` | `AnchorClient` — anchor / rootCount / anchors; signs EIP-155 legacy tx server-side via `eth-crypto`; drives `rpc` (JVM-only by **private-key custody policy** — the old transitive `abi`/`eth-crypto` blockers are gone) |
| `base-l2.paymaster` | `.cljc` | ERC-4337 sponsored write over injected `Bundler`/`SmartAccount` (never holds a key) — **portable JVM+CLJS**; its own logic was always platform-agnostic, and `abi` no longer blocks it |

JVM-only (`.clj`): **`l2` alone**, and for one reason that is a policy, not a
port gap — it signs raw transactions with a caller-held private key
(server-side `anchor-cron` consumer). Holding a raw key in a browser runtime
runs against this substrate's no-server-key posture for user-facing writes, so
`l2` stays where it is on purpose.

Everything else is portable `.cljc`. `rpc`'s only JVM-gated piece is its
`Thread/sleep`-polling `wait-for-transaction-receipt`.

`abi` and `paymaster` were `.clj` until 2026-08-28, and the docstrings that
justified it were **accurate when written and stale by the time they were
read**: they said `eth-crypto.core` "carries ZERO `#?()` reader conditionals"
and has "zero CLJS portability". That was true of `eebb35b` (2026-06-30), the
revision this repo pinned. Upstream `1253e01` (2026-07-26) shipped real
ClojureScript crypto — Keccak-f[1600] on js/BigInt lanes, pure-cljs
HMAC-SHA256, hand-written modInverse/modPow — and this repo simply kept
pinning the pre-CLJS revision for two months. **The blocker was a stale pin,
not a missing primitive.** Advancing the pin unblocked `abi`; `abi` unblocked
`paymaster` with no change to a single line of its code.

The `.cljc` claim is verified, not asserted: `bin/run_tests.cljk` runs the
SHARED suite under nbb, so the same viem-generated known-answer vectors gate
both platforms (CI job `cljs`).

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/{l2,paymaster}.ts`
to `kotoba-lang/base-l2`. Ported to Clojure with an injected-transport seam; the
TypeScript has been **deleted** — the `.clj` cores are the single canonical
implementation. Reuses `kotoba-lang/eth-crypto` (Keccak-256 / secp256k1 / RLP / EIP-155).

## Develop

```bash
kbb -M:lint     # clj-kondo (errors fail)
kbb -M:test     # JVM: viem cross-checked ABI + signing vectors; mock JSON-RPC

# ClojureScript: the SAME .cljc suite and the SAME viem vectors.
# Run from the repo root — the abi fixture is read by relative path under :cljs.
kbb --backend sci --classpath "$(kbb -A:test -Spath)" bin/run_tests.cljk
```
