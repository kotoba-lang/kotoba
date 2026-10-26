# ADR-0061 — Registered is not run, but unfindable is worse

Date: 2026-08-18

## Status

Accepted and executable. ADR-0060's gate is now registered and the registration
is checked. The census that came out of measuring it is the more interesting
half, and it is recorded rather than acted on.

## The item this closes

ADR-0060 ended by saying its own gate was "a script that passes when run", and
that the criticism this series made of eleven verifiers nobody invoked applied
to it. `:offline-floor-smoke` is now in `scripts/tasks.edn`, and
`aiueos.smoke-task-registration-test` requires every **nbb** smoke to be named
there.

## Why only the nbb ones — and why that is not a loophole

`tasks.edn` already says why the bare-metal `.sh` chain is deliberately not
behind nbb: those are the OS's own dependency-minimal build tools, and running
them through Node would put Node in the boot-evidence path. **That is a
decision, and a gate that ignored it would be demanding the repository
contradict itself** to satisfy a rule written later.

A smoke *written in nbb* has no such objection — it is already Node. So there
is nothing to weigh against being findable, and `tasks.edn`'s own comment
records the cost of not being: the multiboot smoke went uninvoked until a build
break reached main and sat there.

## The census, which is the honest part

Measured 2026-08-18 across `scripts/` and `os/aiueos/scripts/` — invocation
sites only, not mentions in ADRs:

| smoke | invocation sites |
|---|---|
| `smoke-qemu-kotoba-native.sh` | 9 |
| `smoke-qemu-uefi.sh` | 6 |
| `smoke-qemu-multiboot.sh`, `-grub-multiboot.sh`, `-usb-boot.cljs` | 1 each |
| **the other 13** | **0** |

Thirteen of eighteen QEMU smokes are called by nothing. Most of them —
`-cr3`, `-wx`, `-page-fault`, `-page-fault-recovery`, `-overlap`,
`-owner-state`, `-no-memory`, `-page-table` — are **entry points**: each sets
its own environment and calls `smoke-qemu-kotoba-native.sh`, which is why that
one has nine callers. Nothing invokes an entry point by definition, so a count
of zero there is a statement about **how this OS is tested — by hand, when
someone decides to** — and not a defect list.

**That distinction is the reason this ADR does not add a gate demanding all
eighteen be registered.** The evidence in ADR-0039 and ADR-0040 came from those
scripts; they are not dead, they are manual. Turning "manual" into "red" would
produce thirteen failures nobody can fix and one more permanently-red gate,
which is the thing this series has spent eleven iterations arguing against.

## What registration is and is not

**Registered is not run.** Nothing in this repository runs `tasks.edn` on a
schedule. What registration buys is that a gate is findable and nameable —
the difference between a script and a script nobody knows exists — and the test
says so in its own docstring rather than letting a green check imply more.

The third assertion is the one that would have caught a real error: every task
whose command names a script under `os/aiueos/scripts/` must name a script that
exists. A task pointing at a renamed or deleted file is a runner that fails only
when someone finally tries it.

## Executable evidence

`aiueos.smoke-task-registration-test`: **3 tests, 11 assertions, 0 failures**.
Full suite **632 tests, 9401 assertions, 19 failures** — the baseline nineteen.
Lint unchanged.

**Both directions**: removing `:offline-floor-smoke` from `tasks.edn` fails the
registration assertion by name; pointing its command at a script that does not
exist fails both that assertion and the existence one.

A third finding came out of writing it: the first version asserted
`(str/includes? @tasks-text smoke)` inline, and `clojure.test` printed the
whole of `tasks.edn` into the failure. **A message nobody can read is this
series' own defect from the other side** — too much rather than too little —
so the assertion now compares a precomputed boolean.

## Remaining boundary

- **Nothing runs any of this on a schedule.** Registration made the gate
  findable; a runner that invokes it is a different piece of work, and on this
  workspace that means a murakumo fleet gate rather than anything in this
  repository.
- The thirteen manual entry points stay manual, and this ADR is the first place
  that says how many there are.
