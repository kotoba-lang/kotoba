# ADR-0067 — A date nobody reads is decoration

Date: 2026-08-18

## Status

Accepted and executable for `qualification/tcb-inventory.edn`.
`qualification/build-identity.edn` has the same shape and is **not** fixed here.

## What was measured

ADR-0059 fixed a receipt whose `:measured-at` was a string literal and named
the remainder: *other fixed strings in this repository that claim to describe a
measurement have not been looked for.* Two were visible —
`:tcb/as-of "2026-08-01"` and `:build-identity/as-of "2026-08-03"`.

Measured 2026-08-18: **nothing reads either of them.** No source, test or
script in this repository consults `:tcb/as-of`, and the inventory it dates had
been edited that same morning — five times, by ADR-0042 through ADR-0065. So it
was seventeen days stale, wrong, and consulted by nobody.

ADR-0059 was careful to say these might be *authorial* claims rather than
reports of a run, and that the distinction matters. It does. **An authorial
claim that nothing checks and nobody reads is still decoration**, and the
inventory's own doctrine — *"an inventory update must be an intentional review
action"* — makes this particular date the evidence that the review happened.

## Decision

**Pair the date with a digest of everything it dates.**
`:tcb/content-digest` is the SHA-256 of the inventory with `:tcb/as-of` and
itself removed, canonicalised by `aiueos.key-lifecycle/document-bytes` — the one
canonicaliser this repository has.

Change any entry and the digest moves, so **the date has to move with it**.
No git required, which matters because the fleet ships a tarball with no
`.git`.

Three errors, all fail-closed: `:content-digest-missing`, `:as-of-stale`
(recorded ≠ computed), `:as-of-malformed`.

**Scoped like the classpath half** (ADR-0062): `{:review :not-in-scope}` for
callers validating a synthetic inventory built inside a test. A map assembled
in a test is not a review artifact, and demanding it carry a review date asks a
question that has no answer.

## The cost, stated

Editing `src/aiueos/tcb.cljk` now takes two steps: record the file's new digest,
then recompute the content digest that covers the record. The second depends on
the first, so they cannot be done at once.

That is the mechanism working — a review artifact that could be updated in one
pass would be one where the date could drift from the content again — but it is
a real cost and the next person will hit it. It is written here rather than
discovered.

## Executable evidence

`aiueos.tcb-test`: **32 tests, 59 assertions, 0 failures.** Full suite
**643 / 9433 / 12**; `-M:test-fleet` **642 / 9361 / 0**; `-M:tcb-check` valid.
Lint unchanged.

**Both directions**: renaming one entry's `:role` without re-recording fails
`the-review-date-moves-with-the-inventory`; deleting `:tcb/content-digest`
fails that *and* `an-entry-changed-without-re-review-is-stale`, because a
missing digest is fail-closed rather than an absent check.

## Remaining boundary

- **`build-identity.edn` is untouched.** Same shape, same measurement (nothing
  reads `:build-identity/as-of`), and it has its own validator that could carry
  the same pair. Left because doing two of these half-well is worse than one
  properly, and because its `:adopted` list is a different kind of claim that
  deserves its own reading rather than a copied mechanism.
- The date is still typed by a human. Nothing checks it against a clock — a
  reviewer who changes an entry and writes last year's date passes, as long as
  they recompute the digest. What is enforced is that **the date was touched
  when the content was**, not that it is true.
