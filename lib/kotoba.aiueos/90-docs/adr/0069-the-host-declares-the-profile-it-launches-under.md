# ADR-0069 — The host declares the profile it launches under

Date: 2026-08-19

## Status

Accepted and executable. It closes the half ADR-0065 named and deliberately
left. It does **not** claim the host and the guest agree about the profile,
because nothing checks that.

## First: the gate is green on a node

ADR-0068 was written before the next tick and said so. The tick ran:

```
2026-08-18T15:31:33Z pass test-aiueos-774a5b2-murakumo-levi exit 0
                     — Ran 643 tests containing 1920 assertions. | 0 failures, 0 errors.
2026-08-18T15:32:19Z tick done — [… ["aiueos" :pass] …]
```

The signed receipt is in `manifest/fleet-ci.edn`. **The arc from ADR-0061 —
"registration is not execution" — is closed and observed**: registered, run on
levi, failed for a nameable reason, fixed, passed, recorded.

One correction: yesterday's report said the ledger held no aiueos receipt. It
did — **the local superproject checkout was behind**, which is the staleness
trap AGENTS.md documents, appearing in my own reporting rather than in code.

## The question ADR-0065 left

`:aiueos.boot/verified?` lives on the launcher's plan; `profile-violations`
judges a boot config from inside the guest. The two never meet, and requiring
one from the other meant answering: **does the guest's declared profile bind the
host that launches it?**

It still is not answered, and this ADR does not answer it. What it does instead
is smaller and has no ambiguity in it:

**The host declares its own intent.** `vm/plan` takes `:deployment-profile`,
and a launcher told it is starting a `:sensitive-local` or `:regulated` machine
**refuses to boot artifacts it could not check**. `:research` is unchanged —
it records `:aiueos.boot/verified? false` and proceeds, because a developer
booting what they just built is the normal case.

The plan carries the profile it was launched under, so a receipt can say which
rule was in force.

**This says nothing about the guest's `boot.edn`.** The launcher does not read
it, and a rule that claimed an agreement it never checked would be worse than
the note it replaced. If the two ever need to agree, that is a third rule with
its own evidence, and it is not this one.

## Executable evidence

`aiueos.vm-test`: **17 tests, 36 assertions, 0 failures** (3 new).
Full suite **650 / 9,445 / 12**; `-M:test-fleet` **646 / 1,925 / 0**;
`-M:tcb-check` valid with the review date and content digest re-recorded
(ADR-0067's two-step, as advertised). Lint unchanged.

**Both directions**: disabling the refusal fails
`a-production-launch-refuses-an-unverified-artifact` on both profiles;
narrowing `production-profiles` to `:regulated` alone fails it on
`:sensitive-local` only — which is the set being load-bearing rather than
decorative.

## Remaining boundary

- **Nothing supplies `:deployment-profile` at a real call site.** `aiueos.vm`
  is a library; the CLI that launches production machines is not in this
  repository, so the rule is available and unexercised outside tests. That is
  the same shape as `tasks.edn` registration in ADR-0061 — one step short of
  being run — and it is worth saying rather than implying.
- **Host and guest still do not compare notes.** Named twice now, in two ADRs,
  and still not done.
