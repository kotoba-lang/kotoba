# ADR-0063 — A gate that cannot go green is not a gate for this fleet

Date: 2026-08-18

## Status

Accepted and executable. `kbb -M:test-fleet` is green — 631 tests, 0
failures — and is what a murakumo fleet gate can run. `kbb -M:test` still
reports the twelve.

## Context

ADR-0061 registered the offline-floor smoke in `tasks.edn` and said plainly
that registration is not execution: **nothing in this repository runs anything
on a schedule.** On this workspace that means a murakumo fleet gate, which is
the CI authority (root ADR-2607300900).

Two things had to be true first, and only one of them was.

**Measured today**, on two reachable nodes: `repo1.maven.org` 200,
`github.com` 200, `clojure` present. So the dependency resolution a
`:jvm-test` gate needs works — *today, on those nodes*. Egress on this fleet is
not uniform and is not a property to write down as a constant (root AGENTS.md
says so, and says it about a section that had already turned its own
measurement into one).

**The suite was not green.** ADR-0062 took it from nineteen failures to twelve,
and the twelve are all `every-kotoba-source-is-built-or-declared-unbuilt`,
whose red ADR-0050 established as **correct**: nothing builds the `value-*`
objects, and nothing here can, because they are blocked on
[amu#625](https://github.com/kotoba-lang/amu/issues/625) and
[#626](https://github.com/kotoba-lang/amu/issues/626).

## Decision

**Exclude by name, not by threshold.** The blocked test carries
`^:upstream-blocked`, and `:test-fleet` is `:test` plus
`-e :upstream-blocked`. One test is dropped, it is dropped for a reason written
at the test, and every other assertion in the repository runs.

The alternative was lowering something until the suite passed — a failure
count ceiling, a namespace exclusion, a `:min-failures` fudge. That buys the
same green and makes **every future failure invisible instead of one known one
explicit**. This series has spent thirteen iterations on the difference.

**The assertion stays where a person looks.** `kbb -M:test` still runs it
and still reports twelve. Deleting it, or quietly widening its
`not-built-here` list, would have made the repository stop knowing something it
knows.

## Executable evidence

- `kbb -M:test-fleet`: **631 tests, 9339 assertions, 0 failures.**
- `kbb -M:test`: **632 tests, 9411 assertions, 12 failures** — unchanged,
  which is the point: the fleet alias hides nothing from the local one.
- `kbb -M:tcb-check`: `{:valid? true :classpath-scope :measured :files 39
  :external 6 …}` — the new alias adds no dependency the inventory does not
  already carry.

The difference between the two aliases is exactly one test: 632 − 631. A
larger gap would mean the exclusion selector caught something nobody intended,
and that arithmetic is the check on it.

## Remaining boundary

- **The gate is not registered yet.** That is a change to
  `scripts/fleet-ci/gates.edn` in `com-junkawasaki/root`, landing separately,
  and until it lands this ADR describes an alias nobody runs — the same state
  ADR-0061 described, one step further along.
- **Egress was measured on two nodes at one moment.** A gate that resolves
  dependencies will fail on a node that cannot reach maven, and the honest
  expectation is that this will happen rather than that it will not.
- The twelve remain, and the fleet will never see them. That is deliberate and
  it is also a hole: **if the upstream answer arrives and the objects start
  building, no fleet gate notices.** Whoever removes the metadata should be the
  person who reads #625 closing.
