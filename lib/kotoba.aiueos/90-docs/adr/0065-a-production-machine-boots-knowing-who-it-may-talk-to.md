# ADR-0065 — A production machine boots knowing who it may talk to

Date: 2026-08-18

## Status

Accepted and executable for the anchors half. The launcher half — requiring a
verified artifact — is named here and not done, with the reason.

## Context

ADR-0048 made PID 1 load the image's anchor set and record the outcome on the
boot config. ADR-0049 made the launcher check its artifacts and record that too.
Both ADRs then wrote the same sentence about their own work: **the fact is
recorded and no deployment profile turns it into a requirement.**

A record nobody reads as a requirement is the weakest form of this series'
recurring defect. It is not that the check did not run — it ran and wrote down
a true answer — it is that nothing consumes it, so a `sensitive-local` machine
with no pins boots exactly as happily as one with them.

## Decision

**`:sensitive-local` and `:regulated` require trust anchors.**
`anchor-violations` reads the boot config PID 1 produced and reports:

- `:trust-anchors-absent` — the image carries no anchor set;
- `:trust-anchors-empty` — it carries one that produced no keys.

Two violations rather than one, because they are different operator problems.
The second is a file someone shipped believing it did something.

**`:research` is untouched.** A development machine that reaches nothing
because it has no pins is a development machine working normally, and a rule
that made every local boot fail would be uninstalled within a day.

## What the test fixtures had to admit

Four existing profile tests failed the moment the rule landed, because they
build production configs with no anchors. They now spell the anchors in.

That is not incidental: **a fixture that omits the thing under test asserts the
absence of a requirement.** The four tests were, without meaning to, encoding
"a regulated machine may boot with no pins" — and they would have kept
asserting it.

## Executable evidence

`aiueos.deployment-profile-test`: **15 tests, 24 assertions, 0 failures**.
Full suite **635 / 9416 / 12** — the twelve upstream-blocked, unchanged.
`kbb -M:test-fleet`: **634 / 9344 / 0**. `-M:tcb-check` valid. Lint
unchanged.

**Both directions**: disabling the absent check fails
`production-profiles-require-trust-anchors` on both its sensitive-local and
regulated assertions, with the empty-set case still passing — which is the pair
of violations staying distinguishable rather than one masking the other.

## The half this does not do

`:aiueos.boot/verified?` lives on the **vm plan**, not the boot config. It is
produced by the launcher on the host, before the guest exists, and
`profile-violations` judges a boot config from inside the guest. The two never
meet.

Requiring it means `aiueos.vm` refusing to launch an unverified artifact under a
production profile — which means the vm plan carrying a profile, which it does
not. That is a real change with a real question behind it (**does the guest's
declared profile bind the host that launches it?**), and answering it by
half-implementing would produce a rule enforced in one direction only.

Named, not done.

## Remaining boundary

- **Nothing yet requires a *verified* artifact**, only anchors.
- The rule fires on the boot config PID 1 built. A host that never runs PID 1 —
  the bare-metal profile — has no profile check at all, and this changes
  nothing there.
- An anchor set with keys nobody can reach still satisfies it. The rule is
  "you named your keys", not "your keys are right", and the latter is
  `admit-peer`'s job at connection time.
