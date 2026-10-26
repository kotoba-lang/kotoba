# ADR-0266: The sealed control-effect vocabulary is this repository's to export, and a consumer's to compare

- Status: accepted
- Date: 2026-09-03
- Adjudication: kotoba-lang
  `docs/adr/ADR-abort-reaches-the-sealed-effect-row.md`; amu ADR-0326.
- Implementation: unchanged. `984a507` stands.

## Context

`984a507` widened `effect-row-from-hir` so that a member of the closed set
`control-effects` — today `#{:abort}` — passes through the bridge unchanged
into the sealed row, while everything that is neither `[:cap/call <id>]` nor
in that set is refused as before.

Hours earlier the same day, amu ADR-0300 section 4 wrote the opposite into a
test: `:abort` names no authority, so the bridge refuses and the definition
gets `:unbridged-effect`. Neither repository knew about the other's decision.

The consequence was not an argument, it was a stall. amu held its kotoba-kir
pin at `08bdab8b` — the commit *before* `984a507` — because advancing it
turned eight assertions red. Twenty-six commits of this repository's work,
including a `[:slice T]` boundary refusal that amu had asked for, the
alpha-normalization move and a ClojureScript-safe i64 ordering, sat behind an
unmade decision for a day.

## The ruling

**`:abort` reaches the sealed row.** kotoba-lang adjudicated it from
`lang/surface-status.edn`, not from a preference between implementations:
`:effect-row-integration` is a *named precondition* of the sanctioned
widening path for the typed abort ability, and a row member that cannot reach
a definition identity is refused at the row's boundary rather than integrated
into it. The shielding axis is `:control-effect-tracking`, and the identity
is the last boundary a control effect crosses.

So nothing in this repository changes. What changes is that the reason is
now written down somewhere other than a commit message, and that a consumer
compares.

## The set is this repository's to export

`control-effects` is public because it must be compared, not because it must
be imported. That distinction is the one kotoba-native ADR-0050 and
kotoba-verifier ADR-0024 landed for the float admission lists, and it applies
here for the same reason:

- **Exported**, so a consumer can ask what this repository actually branches
  on rather than restating it from a docstring.
- **Not imported** by the consumer's own decision path. amu derives its own
  expectation, `#{:abort}`, and asserts equality. If it imported the set
  instead, the two would agree by construction and the comparison would prove
  nothing — the shape ADR-2608136000 calls a check that cannot fail.

amu's `the-sealed-control-effect-vocabulary-agrees-across-the-pin` is that
comparison, and it runs across the `deps.edn` pin. The next divergence is
therefore caught by the pin advance that carries it, rather than by a test
stranded behind a pin nobody dares advance — which is exactly what happened
between 2026-09-02 and 2026-09-03 for want of it.

It lives in amu rather than in kotoba-verifier, the repository the float
lists use, because kotoba-verifier has no part in definition identity. The
consumer that diverged is the one that has to compare.

## What stays closed

Growing `control-effects` is a contract change in kotoba-lang first, then
here. A keyword the compiler did not mean as a control effect is still
refused with `effect row member is not a wire capability call`, so the set
cannot grow by a keyword arriving. Nothing today proposes a second member.

The ten frozen vectors in `test/kotoba/kir/fixtures/code-identity-vectors.edn`
were re-asserted when the bridge learned `:abort` and are unchanged: admitting
a new member SHAPE must not move a row that never had one.
