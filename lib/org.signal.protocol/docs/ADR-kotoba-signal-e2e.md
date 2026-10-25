# ADR: kotoba-signal — Signal E2E (X3DH → Double Ratchet, group) in CLJC/EDN

- Status: accepted
- Date: 2026-07-01

## Context

`kotoba-lang/kotoba`'s `AGENTS.md` states the runtime's authorization model as
"CACAO (depth-2 delegation) + Signal E2E (X3DH → Double Ratchet, group)". The
"Signal E2E" half used to be a Rust crate, also named `kotoba-signal`, inside
the `kotoba-lang/kotoba` Rust workspace. That workspace was **fully removed**
in `kotoba-lang/kotoba` PR #259 (2026-07-01); see that repo's
`docs/rust-crate-migration.md` for the policy driving the removal: new
implementations are CLJC/EDN-first, with native adapters (Rust/etc.) allowed
later but never holding semantic authority. The `AGENTS.md` line referencing
Signal E2E is now the only trace of the prior Rust implementation — the actual
code is gone.

Separately, ADR `2606271500-kotoba-stage-obs-live-aozora`
(`90-docs/adr/2606271500-kotoba-stage-obs-live-aozora.md` in the superproject)
specifies that **private live-streaming distributes segment encryption keys via
"the group ratchet"** — i.e. it depends on exactly the group-messaging half of
Signal E2E existing and working.

This repository (`kotoba-lang/kotoba-signal`) is the CLJC/EDN re-implementation
that fills both gaps: it gives `kotoba-lang/kotoba` back its Signal E2E
primitive, in the CLJC-first form the migration policy requires, and gives the
aozora private-streaming ADR a real group-ratchet dependency to build on.

## Decision

Implement, in plain JVM Clojure (see README "Scope" for why not CLJC/CJS yet):

1. **X3DH** (`src/kotoba/signal/x3dh.clj.cljk`) — identity/signed-prekey/one-time-
   prekey bundles, `x3dh-initiate` / `x3dh-respond`, HKDF-SHA256 key derivation
   over 3–4 X25519 DH outputs, SPK signed with a separate Ed25519 identity key
   (no XEdDSA — see README "Why JVM-only...").
2. **Double Ratchet** (`src/kotoba/signal/ratchet.clj.cljk`) — root KDF (HKDF) +
   symmetric-key chain KDF (HMAC-SHA256, one-way) + AES-256-GCM message
   encryption, with a DH ratchet step per direction turn.
3. **Group ratchet / sender-keys** (`src/kotoba/signal/group.clj.cljk`) — one
   sender's chain key, distributed once per member via a pairwise X3DH
   channel, walked forward by the sender per segment/message and independently
   walked forward by each member in lockstep. This is the primitive the
   aozora private-streaming ADR consumes: one broadcaster ratchets forward
   once per media segment, every already-bootstrapped viewer derives that
   segment's AES key without a fresh DH round.
4. **HKDF-SHA256** (`src/kotoba/signal/hkdf.clj.cljk`) — hand-rolled per RFC 5869
   (the JDK has no built-in HKDF, only the HMAC it's built from), pinned
   against all three RFC 5869 Appendix A test vectors.

Dependencies: reuse `io.github.com-junkawasaki/ed25519-clj` (already vendored
by `orgs/kotoba-lang/cacao`) for Ed25519 sign/verify/did:key — no new Ed25519
implementation. X25519 and AES-GCM come directly from the JDK
(`java.security`/`javax.crypto`), not reimplemented, for correctness (see
README).

## Scope / non-scope

In scope (implemented + tested, `kbb -M:test`: 23 tests / 62 assertions):
- X3DH key agreement, round-trip verified.
- Double Ratchet: root KDF, chain KDF, AES-256-GCM messages, full bidirectional
  session with DH ratchet turns.
- Sender-keys group ratchet: distribution message + signature, sender/member
  lockstep derivation, chain forward secrecy.

Out of scope (explicit follow-up, not a hidden gap in what's listed above —
see README for the same list with more detail):
- CJS / browser / non-JVM runtimes (no vetted pure-JS/WASM X25519 dependency
  exists yet in the kotoba-lang graph; adding one is a separate ADR).
- Key revocation / rotation *policy* (the primitives to rotate SPKs and
  sender-keys exist; scheduling/policy for when does not).
- Group membership management (add/remove members, access control lists).
- Skipped-message-key recovery for out-of-order/dropped messages, in both the
  Double Ratchet and the group ratchet (both currently assume in-order
  delivery within a chain).
- Header encryption ("sealed sender"-style header protection).

## Consequences

- `kotoba-lang/kotoba`'s "Signal E2E" authorization claim is backed by real,
  tested code again, in the CLJC/EDN-first form the post-PR#259 migration
  policy requires.
- ADR 2606271500 (aozora private live-streaming) now has a concrete group-
  ratchet dependency (`kotoba.signal.group`) to build its segment-key
  distribution on, rather than a forward reference to a removed Rust crate.
- Manifest registration (`manifest/repos.edn` / `manifest/west.yml`) for this
  repo is handled by a separate process per current working policy — not part
  of this ADR's scope.
