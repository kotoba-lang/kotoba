# ADR-0044 — The machine names the key it talks to

Date: 2026-08-18

## Status

Accepted and executable for the hosted profile. It converts ADR-0043's largest
recorded gap into a decision. It does not implement pin distribution or
rotation, and it records no pin for any real endpoint.

## Context

ADR-0043 put the first bytes off a socket and named what it had not done: *the
machine's trust in the cloud is the JDK's default trust store, which this
repository neither owns nor pins.* That is the load-bearing gap of everything
ADR-0041 decided. A machine whose storage and inference authorities are both
remote has one question underneath every other one — **who answered?** — and
until now the answer was "whoever several hundred anchors chosen by the runtime
packager are willing to vouch for."

That default is right for a browser, which must reach hosts nobody enumerated
in advance. It is wrong here: this machine talks to **two** authorities, both
known before it boots. Every property the stack has built — the digest that
catches a lying gateway, the allowlist that bounds reach, the alias endpoint
that gets re-checked — assumes the connection reached the host it named. Any
one bad anchor makes all of them true about the wrong machine.

## Decision

**An https peer is trusted because its key is one the policy named, and for no
other reason. The platform trust store is not consulted.**

- The pin is `:aiueos.cloud/trust-anchors` in policy: a set of SHA-256 hex
  digests of the leaf certificate's **SubjectPublicKeyInfo**. Over the *key*,
  not the certificate — an authority that renews with the same key keeps
  working, and one that changes key does not, which is the event worth
  noticing.
- **The empty set denies**, exactly as the empty `net-allow` does. An operator
  who has not said is not an operator who said yes.
- **Three refusals, deliberately distinct**: `:no-trust-anchors` (nothing was
  declared), `:peer-unmeasured` (nothing was measured), `:peer-not-pinned`
  (what was measured is not what was declared). Only the third is an attack;
  the first two are a machine that must not proceed as though it had checked.
- **An https request with no anchors never reaches the socket.** There is
  nothing to connect for: the handshake could not have been judged.
- **The refusal is reported as itself.** A trust manager that rejects mid-flight
  surfaces as an I/O exception, and reporting `:request-failed` would hide the
  one fact worth having. The verdict is recorded as the handshake runs and
  returned in place of the exception it became, with the key that was actually
  seen.
- The successful result carries `:aiueos.provider.cloud/peer-spki`, so a receipt
  can name the key it talked to.

The seam is unchanged: the provider **measures** the SPKI digest,
`aiueos.cloud/admit-peer` **decides**.

## Executable evidence

Real TLS, on loopback, against a certificate the test generates with the JDK's
own keytool — generated rather than checked in, because a private key in the
repository is a private key in the repository. A missing keytool **fails** the
test rather than skipping it: a suite that silently does not run reports the
same green as one that ran.

- a pinned peer serves a block end to end, and the verdict names the key;
- **a peer outside the pin set is refused mid-handshake** — reported as
  `:peer-not-pinned` with the key it saw, and the server records **zero
  requests**, because the connection never completed;
- https with no anchors never reaches the socket;
- **the same certificate the JDK's default client cannot reach at all is
  reached by aiueos, and the only reason is the pin.** That assertion is what
  makes "replaced, not extended" a measurement rather than a claim.

`aiueos.cloud-test` 31 tests, `aiueos.provider.cloud-test` 11,
`aiueos.provider.cloud-tls-test` 5: together **43 tests, 117 assertions, 0
failures**.

**Both directions, shown.** Two mutations: a trust manager that records the
verdict but does not throw makes the refusal test fail in all three of its
assertions — including the server's hit list growing, which is the connection
completing that should not have; and dropping the pinning `SSLContext` back to
the platform default makes aiueos unable to reach the server *at all*, which is
the same fact from the other side.

Full suite **563 tests, 9165 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 37
:external 6 …}`. Lint unchanged.

## What the TCB entry now says

`java.net.http` stays in the inventory, but its gap changed. It is no longer
*"the trust decision is the platform's"* — that decision came home. What
remains platform-owned is the **TLS implementation**: the handshake, the record
layer, the cipher suites, none of which this repository can content-address
from inside itself. That is a smaller and more honest gap, and it is the same
gap ADR-0041's step 4 exists to close for the bare-metal profile, which has no
implementation at all.

## Remaining boundary

- **No pin is recorded for anything real.** Neither `kotobase.net` nor
  `api.murakumo.cloud` has a pin written down anywhere, so the hosted provider
  as configured today would refuse both. **A pinning client with no pin
  distribution is a client that cannot connect** — that is the next decision,
  and it is an operational one: how a pin reaches a device, and what happens
  when an authority rotates its key.
- **Pinning is not certificate validation.** Expiry, revocation, name
  constraints and chain semantics are not checked; the key either is the one
  named or it is not. For two known authorities that is the stronger property,
  but it is a different property.
- **The bare-metal profile is untouched.** It still has no TLS at all.
