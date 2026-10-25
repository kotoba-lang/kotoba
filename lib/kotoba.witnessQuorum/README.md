# witness-quorum

`@etzhayyim/witness-quorum` — deterministic witness selection, a quorum
accept/reject/escalate decision rule, and Ed25519-signed validation-membrane
attestation production, over a pluggable witness transport (in-memory or
PDS-polling).

| Namespace | What it does |
|---|---|
| `selector.clj` | deterministic `sha256(cid) mod sorted-fleet` witness selection over a fleet |
| `quorum.clj` | `collect-quorum`/`quorum-state` — pure accept/reject/escalate reducer by threshold, given a stream of attestations |
| `attestation.clj` | 3-layer validation membrane (schema/deterministic/policy) + Ed25519-signed attestation, parameterized by a membrane rule |
| `signer.clj` | generic Ed25519 sign/verify helpers |
| `orchestrator.clj` | `write-with-witnesses` — "write, then collect witness quorum" orchestrator over a pluggable write client / witness transport |
| *(host-supplied)* | the production HTTP-fan-out + PDS-polling `WitnessTransport` is **deliberately not ported** — see below |

Zero etzhayyim-specific coupling beyond an NSID string constant and a
`"council"` escalation label — every fleet topology, membrane rule, and
signer is a caller-supplied parameter.

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/
kotoba-datomic/*.ts` (+ 3 dedicated test files) to `kotoba-lang/
witness-quorum` per the org-taxonomy library-placement rule
(ADR-2606302300). Design authority remains ADR-2605231400, in
`etzhayyim/root` — that ADR's own composition-spec naming is superseded by
ADR-2605262130, but ADR-2605262130 §D8 explicitly states the witness/quorum
semantics themselves are *preserved*, just claimed to be reimplemented
natively in Rust. That claim did not hold: this package is, as of the
relocation, **the only complete working implementation of this logic
anywhere in the `kotoba-lang` ecosystem** — its intended Rust successor
(`kotoba-net`/`kotoba-dht`/`kotoba-server` in `kotoba-lang/kotoba`) and its
cited Python counterpart (`kotodama.kotoba-datomic`) were both deleted in
an unrelated Rust/Python-workspace purge on 2026-07-01, before either ever
reimplemented this domain. Named `witness-quorum` (not `kotoba-datomic`,
the module's original directory name) to describe what it actually does
and avoid echoing the name of the now-deleted Rust crate.

No live consumer imports `@etzhayyim/sdk/kotoba-datomic` today (only
doc/ADR references). The TypeScript original was relocated here as a
**physical move only**, then ported to Clojure (see below), and the
TypeScript has since been **deleted** per ADR-2607012200 — the
`kotoba-lang` org's admission rule is pure Clojure/CLJC with zero vendor
SDK and zero network I/O from the lib. This Clojure implementation is now
the only implementation.

## Clojure port

`src/kotoba/lang/witness_quorum/{selector,quorum,attestation,signer,
orchestrator}.clj` is a port of the pure-logic + in-memory-transport
surface (`witness-selector.ts`, `quorum.ts`, `attestation.ts`, `signer.ts`,
and `orchestrator.ts`'s `writeWithWitnesses` + in-memory transport +
deterministic test signer). `pds-transport.ts` (the production HTTP
fan-out + PDS-polling transport) is **deliberately NOT ported** — it's a
production-specific I/O adapter, not core witness/quorum logic, and this
package's real target consumers (Murakumo babashka cell-runners) are
expected to reach PDS via `kotoba`'s own XRPC layer rather than mirroring
this exact TS transport shape 1:1. `WitnessTransport` stays a documented
plain map of functions (`{:request-attestation fn :subscribe-attestations
fn}`) so a project can supply its own production transport without needing
this package to anticipate every shape.

**Plain `.clj`, not `.cljc`** — deliberately, unlike `kotoba-lang/ipfs`'s
CLJC port. This package's own docstrings describe an exclusively
server-side Murakumo-Pregel-cell / orchestrator deployment topology; there
is no evidence of, or plausible use case for, a browser/CLJS consumer of
witness selection or cell-signing logic. Forcing CLJS parity here would be
busywork with no real payoff — an honest scope boundary, not a gap.

Namespace-per-module, mirroring the TS file boundaries:
`kotoba.lang.witness-quorum.{selector,quorum,attestation,signer,orchestrator}`.

Notable adaptations from the TS original (all synchronous — no
Promise/async plumbing on the JVM):
- **Ed25519 is built on `kotoba-lang/ed25519`** (`ed25519.core`), not
  Bouncy Castle and not the JDK's `java.security` Ed25519
  KeyPairGenerator/KeyFactory used free-hand. Two independent
  disqualifiers ruled out the alternatives: (1) verified empirically that
  the JDK's native Ed25519 key generation does **not** derive the same
  public key from a raw 32-byte seed that RFC 8032 / `@noble/curves` (the
  TS original's dependency) do, even driven through a fixed-output
  `SecureRandom`; (2) Bouncy Castle is **not loadable under babashka** —
  its GraalVM native image has no `org.bouncycastle.*` classes baked in,
  so any BC import throws `ClassNotFoundException` at runtime under `bb`,
  which matters directly here since this package's own docstrings
  describe an exclusively `bb`-based deployment topology. `ed25519.core`
  solves both: pure RFC-8032 math (SHA-512 + `BigInteger` only) derives
  the public key from a raw seed, then the JDK's own built-in
  `java.security` Ed25519 `Signature`/`KeyFactory` (core JDK, not a
  3rd-party jar — fine under `bb`) does the actual signing/verification.
  Verified byte-for-byte identical to `@noble/curves`' `getPublicKey`/
  `sign` for a known seed — see `signer_test.clj`'s
  `cross-language-ed25519-interop-test`, which pins a (seed, canonical,
  signature) triple generated from this repo's own `@noble/curves` npm
  dependency via `node -e`.
- `WriteCapableClient.write` (a single-method TS interface) becomes a
  plain function `(fn [write-opts] -> {:uri ... :cid ...})` — idiomatic
  Clojure prefers a function argument over a single-method object.
- `WitnessTransport.subscribeAttestations` (which returned an
  `AsyncIterable<Attestation>` raced against a `setTimeout` in
  `collectQuorum`) becomes a function returning a `poll-fn`: `(fn
  [remaining-ms] -> {:status (:value|:timeout|:done) ...})`, a blocking
  poll-with-timeout contract that `collect-quorum` drives in a loop.
  `create-in-memory-witness-transport` implements this over a
  `java.util.concurrent.LinkedBlockingQueue` per quorum-group — actually
  simpler than the TS original's lazy queue/waiters bookkeeping, since
  `ConcurrentHashMap.computeIfAbsent` on the same key from both the
  producer and consumer side makes subscribe-before-or-after-dispatch
  irrelevant.
- Map keys are kebab-case Clojure keywords (`:record-cid`, `:cell-node`,
  `:membrane-version`, ...), not camelCase strings. If a future
  `pds-transport`-equivalent needs to serialize an attestation to JSON to
  match the `com.etzhayyim.kotoba-datomic.attestation` lexicon's camelCase
  wire shape, that key transformation happens at that future boundary, not
  here — this port operates purely in-memory today.

Tests (`test/kotoba/lang/witness_quorum/*_test.clj`, run via `clojure
-M:test`; every dependency here -- `ed25519.core`, `java.util.concurrent`,
`java.security.MessageDigest` -- is on babashka's classlist too, so this
package (unlike `kotoba-lang/ipfs`'s `com.sun.net.httpserver`-based mock
server tests) has no actual `bb` incompatibility; `kbb -M:test` is
just the test-runner this repo is wired for, not a requirement): 26 tests /
77 assertions, covering deterministic selection, the full quorum-state
decision table (witnessed/rejected/pending/escalated, including the
"any :escalate vote forces escalation regardless of :escalation-policy"
rule), attestation production + membrane validation, the Ed25519
cross-language interop vector, and an end-to-end
`write-with-witnesses` orchestration test using the in-memory transport
(mirroring the spirit of the original `witnessed-write.test.ts`).

## Development

```bash
kbb -M:lint      # clj-kondo (errors fail)
kbb -M:test      # cognitect test-runner
```

## License

Apache 2.0 + Charter Compliance Rider v3.6 (`/CHARTER-RIDER.md`).
