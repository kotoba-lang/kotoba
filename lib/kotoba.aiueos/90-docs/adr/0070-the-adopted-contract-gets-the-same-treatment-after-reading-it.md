# ADR-0070 — The adopted contract gets the same treatment, after reading it

Date: 2026-08-19

## Status

Accepted and executable. It closes the last non-upstream item this series had
named: `qualification/build-identity.edn`, deliberately left by ADR-0067.

## Why the mechanism was copied, and what was checked first

ADR-0067 refused to copy its date/digest pairing here on the grounds that the
`:adopted` list is *"a different kind of claim that deserves its own reading
rather than a copied mechanism."* So it was read.

What is **already checked**, by `tcb/property-errors`: every property names a
statement, a mechanism, and either a gate or an explicit assurance gap; every
named path exists; every mechanism under `src/` is in `:tcb/files`. Measured:
11 adopted properties, 6 naming gates, 3 carrying gaps. That is a well-guarded
document.

What is **not** checked is the same thing as before — `:build-identity/as-of`,
read by nothing, saying 2026-08-03 about a contract whose gate files this series
has been editing for two days. The reading confirmed the mechanism applies, for
the same reason and not by reflex: this document's whole claim is that its
properties are *maintained on purpose rather than surviving by accident*, and
the date is the evidence of the maintaining.

## Decision

**`:build-identity/content-digest`**, computed the same way, checked the same
way, with one difference learned from ADR-0067's fallout: **a document carrying
no digest is out of scope rather than in violation.** Synthetic documents built
inside tests are shape fixtures, not review artifacts — five existing tests
proved that by failing the moment the check was unconditional. That the
document *on disk* carries one is asserted separately, so neither check is
fail-open.

**A named gate with no tests in it is not a gate.** Existence was already
checked; emptiness was not, and **an empty file passes an existence check
exactly as well as a full one.** This is a floor, not a proof — a file with
tests in it may have stopped testing *that property*, and nothing here can tell.
What it catches is the gate being gutted rather than renamed.

## The fixed point, and what it cost

`build-identity.edn` is itself pinned in `:tcb/files`, and the inventory now
carries a digest of its own contents. So editing it needs four steps in order:
write the document, record its own content digest, re-pin its file digest in the
inventory, recompute the inventory's content digest. It converged in two rounds
and both are visible in this branch.

ADR-0067 predicted the two-step and wrote it down "rather than discovered". The
four-step is the same mechanism meeting a document that the inventory also
pins, and it is written down here for the same reason.

## Executable evidence

`aiueos.tcb-test`: **35 tests, 63 assertions, 0 failures** (3 new).
Full suite **653 / 9,449 / 12**; `-M:test-fleet` **649 / 1,929 / 0**;
`-M:tcb-check` valid; lint unchanged.

**Both directions**: renaming one adopted property in the real document without
re-recording fails `the-adopted-contract-carries-its-own-review-digest` and
`the-checked-in-property-record-is-clean`; pointing a property's gate at a file
containing no `deftest` fails `a-named-gate-with-no-tests-in-it-is-not-a-gate`,
which writes and deletes an empty file to prove it.

## Remaining boundary

- **The semantic hole stays open.** A gate file can keep its `deftest` forms and
  stop asserting anything about the property that names it. No mechanism here
  can see that, and pretending otherwise would be the decoration this ADR is
  about.
- Gate files under `test/` are not in `:tcb/files`, so their *content* is
  unpinned by design — pinning them would make every test edit an inventory
  review.
- With this landed, **every non-upstream item this series named is done**. What
  remains is #625/#626, the owner decisions (repository visibility, install
  target, real pins, hardware), and the host↔guest profile question named twice.
