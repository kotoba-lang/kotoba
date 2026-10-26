# ADR-0062 — A red gate hid a real failure for four ADRs

Date: 2026-08-18

## Status

Accepted and executable. The suite's standing failures go **19 → 12**, and the
twelve that remain are the value-runtime family whose red ADR-0050 established
as correct.

## What was wrong

`aiueos.tcb-test` had six failures and `aiueos.sbom-test` one, and every ADR in
this series has quoted them as "the baseline nineteen". They had **two
independent causes**, and the loud one hid the quiet one.

**The loud cause.** `tcb/validate`'s classpath half asks *is every jar this JVM
loaded recorded in the inventory* — a question that only has an answer when the
JVM was started with the classpath the inventory describes. Under the `:test`
alias it is not: the test runner, ClojureScript and their transitive
dependencies are all loaded, producing **seventeen `:classpath-unrecorded`
errors**. Those errors made `:valid?` false and polluted every assertion that
compared `:errors` exactly, which is four of the six. The test that came
closest to noticing says so in its own message — *"the check runs under more
than one alias; recorded-but-absent is normal"* — and then handled only the
recorded-but-absent direction, not the present-but-unrecorded one.

**The quiet cause.** `checked-in-tcb-inventory-has-no-drift` asserts the
inventory's counts as literals, deliberately: *"deriving it would make the
inventory grow silently."* It expected `:files 34 :external 5`. The inventory
is at **39 and 6** — the `net`/`cloud`, `anchors`, `boot_admission` and
`java.net.http` entries added by ADR-0042 through ADR-0049. **Of this series.**

That assertion existed precisely to catch a silently growing TCB, and it did
catch it — into a test that was already red for an unrelated reason, where the
result was indistinguishable from the noise. **One red hides another**, and the
one it hid was mine.

## Decision

**A check that cannot see its subject says so instead of failing.**
`tcb/validate` takes `{:classpath :measured | :not-in-scope}` and reports
`:classpath-scope` in its result, so a skipped half and a passed half do not
look the same. `kbb -M:tcb-check` — the production alias, the only place
the question means anything — keeps `:measured`.

`aiueos.sbom/regulated-evidence` threads the same option and records
`:tcb-classpath-scope` in the evidence, because release evidence about the
wrong classpath is worse than evidence that names which one it looked at.

**The counts are corrected, not derived.** 34 → 39 and 5 → 6. The comment
explaining why they are literals stays true and now has an incident behind it.

**One assertion was replaced rather than scoped.**
`every-classpath-jar-is-recorded-with-a-role` asked the unanswerable question;
it is now `every-recorded-classpath-entry-has-a-role`, which is checkable under
any alias — an entry with no role is a jar nobody reviewed, recorded as though
someone had — with the stronger claim left to `-M:tcb-check` and said so in the
test.

## Executable evidence

- `aiueos.tcb-test` and `aiueos.sbom-test`: **38 tests, 79 assertions, 0
  failures** (were 7 failures between them).
- Full suite **632 tests, 9411 assertions, 12 failures**. The nineteen this
  series has been quoting is now twelve, and future ADRs should quote twelve.
- `kbb -M:tcb-check`: `{:valid? true :classpath-scope :measured :files 39
  :external 6 :classpath 9 :properties 6}`. Lint unchanged.

**Both directions.** Forcing the classpath half out of scope unconditionally
fails four tests — `resolved-jar-digest-drift-is-fail-closed`,
`an-unrecorded-classpath-jar-is-fail-closed`,
`classpath-digest-drift-is-fail-closed` and the adoption one — proving the real
classpath checks are live rather than scoped away. Putting the stale counts
back fails `checked-in-tcb-inventory-has-no-drift` alone, which is the
assertion that was blind for four ADRs, now demonstrably not.

## Remaining boundary

- **Twelve failures remain**, all `every-kotoba-source-is-built-or-declared-unbuilt`.
  ADR-0050 decided that red is correct: the objects are genuinely built by
  nothing, and the fix is upstream ([#625](https://github.com/kotoba-lang/amu/issues/625),
  [#626](https://github.com/kotoba-lang/amu/issues/626)).
- **Nothing prevents the same hiding from recurring.** A suite with any
  standing red can conceal a new failure in the same file, and this repository
  now has twelve of them. The only structural answer is to have none, which
  waits on the upstream answer.
- The inventory's counts are still literals a human must update. That is the
  intended design, and it now has a documented failure mode: it only works if
  the test asserting them is otherwise green.
