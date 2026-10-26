# ADR-0129 — The object-producer advance, measured whole instead of sampled

Date: 2026-08-31

## Status

Accepted as a measurement. It does NOT take the advance, move a pin, or touch
a committed object. What it does is replace a five-object sample with the
whole inventory, because the decision that was deferred on that sample needs
the rest of it.

## Context

`reproduce-kotoba-kernel-object.sh` pins amu `9cf3a0a` and its comment records
why the pin has not moved:

> THE FULL ADVANCE WAS MEASURED AND NOT TAKEN. […] Five objects were compiled
> there and compared against the checked-in bytes […] ALL FIVE DIFFER. Taking
> that advance means regenerating every object in this script and every pinned
> digest in `build-uefi.sh`, which is a change to the shipped kernel and not a
> side effect of adding DHCP.

That reasoning is sound and the conclusion may well still be right. But five
of sixty-six is a sample, and "all five differ" supports "some differ", not
"all differ" — and it cannot say anything at all about a third outcome the
sample never contained.

## What the whole inventory says

`os/aiueos/scripts/measure-object-producer.cljk` compiles every committed
object with a given compiler and compares the bytes. Against amu `0085e138`,
with the same flags `reproduce-kotoba-kernel-object.sh` uses:

| | |
|---|---|
| Committed `.o` files | **67** |
| Measured (have a sibling source) | **66** |
| Skipped, reported rather than filtered away | **1** — `ecdsa-p256-public` |
| Reproduce byte for byte | **4** — `broker-admit`, `ime-romaji`, `scanout-bind`, `session-restore` |
| Differ | **58** |
| **Failed to compile** | **4** — `dhcp-option-u32`, `dhcp-reply-valid`, `ecdsa-p256`, `ecdsa-p256-sign`. All four now compile; see below — three were an allowlist that had drifted, one was this measurement asking the wrong question |

## Re-measured once the toolchain was whole

Against amu `512f7e2a`, which carries kotoba-native `db7b7119`, from worktrees
nobody edited while it ran:

| | |
|---|---|
| Measured | **66** (67 committed, 1 skipped with its reason) |
| Reproduce byte for byte | **4** |
| Differ | **62** |
| Fail to compile | **0** |
| Could not run | **0** |
| Needed a retry | **0** |

**Nothing upstream is in the way of the advance any more.** What it costs is
62 objects to regenerate and every pinned digest in `build-uefi.sh` to move,
which is a change to the shipped kernel and wants boot evidence — a decision,
not a task, and not one this measurement makes.

Two runs were discarded on the way to this one, and both for reasons worth
keeping. The first was contaminated: it was compiling against a compiler
worktree while `deps-lock.edn` was regenerated *in that worktree*, and it
recorded `ecdsa-p256-sign` as failed on a toolchain that no longer existed by
the time the run ended. The second recorded `ipv4-checksum` as **failed** when
its message was `FileNotFoundException` while *loading* the compiler frontend
on a machine at load average 76 — the toolchain never started. That object
compiles, and differs. `:could-not-run` now exists as a verdict distinct from
`:failed` precisely so that a run cannot report *could not answer* as
*answered no*.

Two things here were not visible from five.

**Four objects no longer compile — and the diagnosis in the first version of
this ADR was wrong.** They report exit 70, `:kotoba/internal-error`, "internal
compiler error", `:details {:entry main}`, which this ADR first read as a
compiler crash and a regression in amu's codegen. It is neither.

Calling `compile-source` directly instead of through the CLI, which sanitises
the diagnostic, gives the real message: *Kotoba kernel object declares an
aiueos export with no admitted symbol*, with the object's own export names in
`:unlisted-exports`. The allowlist refused them.

`elf64.clj` and `elf64.cljc` are a twin (kotoba-native ADR-0036) and the JVM
loads the `.clj`. They had drifted: 74 entries against 69, three names only in
`.cljc` and eight only in `.clj`. The three the JVM was missing —
`aiueos-dhcp-option-u32`, `aiueos-dhcp-reply-valid` and
`aiueos-ecdsa-p256-sha256-verify` — are three of these four. The two DHCP
entries were in `.clj` at the pinned `a60da444`, where `.cljc` did not exist;
introducing the portable twin moved them instead of copying them.

The fourth, `ecdsa-p256-sign`, is not a regression at all and its failure here
was a defect in this measurement. `reproduce-ecdsa-sign-object.clj` says in its
own header that the pinned compiler cannot build it as shipped either, and that
it needs an allowlist entry and a fuel tier that have never existed upstream;
it is produced by that bespoke recipe, not by the generic command this
measurement used. Measuring it the generic way was asking the wrong question.

kotoba-native `db7b7119` makes both tables the union — 79 entries, identical —
adds the three ecdsa entries the bespoke recipe had been patching in, puts the
ecdsa objects in the fuel tier, and adds `elf64-twin-parity-test` so the tables
cannot drift again. With that pin all four compile and export the symbols they
should. **No codegen regression was involved.**

**The 58 that differ all get smaller, and none stays the same size.** The size
delta runs from −8 to −10,408 bytes; the total goes from 264,768 to 160,488,
a 39% reduction. The earliest difference is at offset 40 — past the ELF header,
in `.text`. This is consistent with codegen improvement rather than drift, and
it is the shape you would want the advance to have. It is also why every pinned
digest in `build-uefi.sh` moves.

Note that reproduction is not explained by an object being trivial:
`broker-admit` has no `:export` clause, and neither do the four that crash.

**The one that was skipped, and why saying so matters.** The first version of
this measurement filtered out objects with no sibling `.kotoba` and reported
the remainder: 67 committed objects went in, 66 came out, and the receipt said
66 with nothing to record that a difference existed. That is the shape this
whole series is about, in a tool written to find it.

`ecdsa-p256-public.o` is not sourceless. `ecdsa-p256-sign.kotoba` defines both
`aiueos-ecdsa-p256-sign` and `aiueos-ecdsa-p256-public`, and
`reproduce-ecdsa-sign-object.clj` writes both `.o` files from that one source —
identical 52,264 bytes, differing only in which admitted symbol
`package-kernel-object` selects. Measuring it needs that recipe rather than the
generic command, so the script now reports it as skipped with its reason
instead of quietly narrowing the denominator.

## What this changes about the decision

Nothing about the 58, deliberately. It converted "we would have to regenerate
everything" into a list with four names on the blocking end — and then those
four turned out not to block anything, once the real error message was read.
What remains is the honest shape of the advance: 62 objects to re-measure and
every pinned digest in `build-uefi.sh` to move, with nothing upstream in the
way of doing it.

## What it does not claim

The 58 differing objects were not booted, executed, or otherwise shown to be
correct — only to be different, and smaller. A smaller object is not a better
one until something runs it. This measurement says what the advance would
disturb, not whether the result would work.

The receipt is `qualification/object-producer-measurement.edn` and it names
the compiler it measured, because a reproduction count without one is a number
with no closure.

It does not name the ROUTE, because at `512f7e2a` there was only one: the
aiueos targets had no JDK-free implementation, so every object in it was built
through `clojure`. ADR-0130 gives the tool a `--jvm-free` pass-through and a
`:route` key; a later receipt without that key is ambiguous, this one is not.

That matters more than it looked at the time. ADR-0130's cross-route comparison
found that the JVM packager under-fuelled three of these objects
(`ecdsa-p256` by 8.6x, both DHCP objects by 64x) against what actually ships,
because the two `elf64` twins disagreed. So three rows of this receipt were
measured through a packager that was wrong about them, and the `:differs`
verdict for those three is right for a reason the receipt does not give.
