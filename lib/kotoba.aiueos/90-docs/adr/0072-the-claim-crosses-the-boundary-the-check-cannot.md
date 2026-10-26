# ADR-0072 — The claim crosses the boundary the check cannot

Date: 2026-08-19

## Status

Accepted and executable. It answers the half of the host/guest question
ADR-0071 left, and it answers it **as a misconfiguration signal, not a security
control** — which is the whole of what is available.

## The impossible version, first

ADR-0071 ended: *"answering it means the launcher writing evidence into the
image it boots."* That is impossible, and saying why is most of the design:
**the image's digest is the thing being verified, so mutating the image
invalidates the claim being recorded.**

What can cross is the kernel command line, which the launcher already builds.

## Decision

**A verified launch appends `aiueos.boot.verified=<release-id>`**, and a
production guest refuses to run without it (`:host-verification-unclaimed`,
beside ADR-0065's anchor violations). `:research` is untouched.

**This is not a security control and must not be read as one.** The command
line comes from the same host that would be lying — a compromised launcher can
claim a verification it never did. What it catches is *misconfiguration*: a
production image started by a launcher that does not even claim to have checked
it, which the guest previously had **no way to notice at all**.

Stating that ceiling is the point. A mechanism that looks like attestation and
is not would be worse than the silence it replaced.

**Silence rather than an empty claim.** An unverified launch appends nothing,
so a guest cannot find the key with nothing after it and read that as a
verification.

## Executable evidence

Full suite **662 / 9,470 / 12**; `-M:test-fleet` **658 / 1,950 / 0**;
`-M:tcb-check` valid with three digests and the content digest re-recorded;
**lint back to 75 warnings** after two corrections of my own (see below).

**Both directions**: dropping the claim from the QEMU arguments fails
`a-verified-launch-tells-the-guest-on-the-command-line` — which asserts on
`vm/argv`, the actual arguments, not on the helper that builds them; loosening
the guest's pattern to a suffix match fails
`the-host-claim-is-read-out-of-the-command-line`, whose fixture includes
`not-aiueos.boot.verified=release-42` precisely because a suffix match accepts
it.

The command-line pattern also matches the **first** token on the line. A
space-prefixed pattern would have missed `aiueos.boot.verified=… quiet`, and
the test carries that case.

## Two corrections in my own work

The first version of the vm test asserted on `cmdline-with-evidence` alone —
the helper, not the arguments. It now asserts on `vm/argv`, because a helper
that returns the right string while nothing passes it to QEMU is exactly the
gap between an intermediate and an artifact that ADR-0071 was about.

And the first version added `clojure.string` to a `.cljc` test's requires for
assertions that live in `#?(:clj …)` only, taking lint from 75 warnings to 76.
**Leaving that while writing "lint unchanged" would have been a false report**;
it is now interop with no namespace at all, and lint is back to 75.

## Remaining boundary

- **A lying host is not addressed and cannot be here.** Real attestation needs
  something the guest can verify without trusting the launcher — a TPM
  quote, a signed measurement — and none of that exists in this repository.
- **Nothing supplies the profiles or reads `/proc/cmdline` at a real call
  site.** `host-verification-claim` is pure and takes the string; the code that
  would read `/proc/cmdline` at boot is not written. Fourth naming.
- The guest now refuses to run in production without a claim, which means
  **every existing production boot config becomes invalid until its launcher
  is updated.** That is intended and is the same one-way step ADR-0065 took
  with anchors.
