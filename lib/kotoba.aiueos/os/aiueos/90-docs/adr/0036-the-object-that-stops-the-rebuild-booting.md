# ADR-0036 — The rebuild does not boot because of one object, and its name is `kernel-context-build`

- Status: accepted
- Date: 2026-08-16
- Extends: ADR-0031 (the signedness fix in `store64`), ADR-0034, ADR-0035

## Context

ADR-0035 stopped with the rebuild failing and the cause unlocated. It named the
missing step exactly: a **per-object differential**, defined, deferred, and
skipped, and it recorded that the deferral is what let a non-booting tree become
a merge candidate. It also fixed the standard for whatever finally lands —
**gated on the boot, not the digest**.

This is that differential, taken against the current compiler.

## What was measured

Compiler `a635509e`, which is **1,065 commits ahead** of the `0b16d9b6` that
`reproduce-kotoba-kernel-object.sh` pins.

| | frozen compiler (ADR-0035) | current compiler |
|---|---|---|
| byte-identical | 37 of 57 | **0 of 57** |
| different bytes | 16 | 53 |
| does not compile | 4 | 4 → **0 after the type fixes below** |

The four that did not compile were all type errors of one shape — source written
when the emitter let a bool stand in for a number. `(* (and ...) n)` in
`object-transaction-route` and `service-registry-state`; a base case of `1`
against a recursive `and` in `user-elf-valid`; and an unannotated recursive
predicate in `task-slot-plan`. None is a compiler bug: the language made bool a
type rather than a number deliberately. Fixed, and all four now boot with
byte-identical evidence (previous commit).

With all 57 compiling, the whole tree was migrated and booted. **It stops after
`AIUEOS_SMP_OK` — 17 markers where a good boot emits 67, with no exception
text.** It wedges where `AIUEOS_APIC_TIMER_OK` should follow.

## The finding

Binary search over the 53 changed objects, each probe restoring every other
object so that exactly one variable moves, converged in six probes and was then
confirmed by migrating the object alone:

**`kernel-context-build`, rebuilt with the current compiler, stops the boot.**
Alone: 17 markers. Everything else migrated without it: 67.

Its `store64` is the helper ADR-0031 fixed. It decomposes a 64-bit value with

```clojure
(quot (bit-and value -256) 256)
```

and its own comment explains why the mask is there: `quot` emits a **signed**
`idivq`, there is no shift operator, and masking the low byte off first makes
each division exact — an exact division by 256 being an arithmetic shift. The
correctness of every higher-half kernel address written into a context depends
on that being true of the emitted code.

So the object is not wrong. It is **precisely tuned to how the old compiler
emitted constant division**, and the current compiler emits something for which
the tuning does not hold.

## Consequences

- **A2 is located, and 56 of 57 are now landed.** The 52 objects that change
  bytes without changing behaviour were migrated in a following commit and the
  tree boots with evidence byte-identical to the pre-migration baseline (71
  lines, compared warm to warm). `kernel-context-build` stays on the frozen
  compiler until the wedge is explained.

  What that buys: the dependency on a compiler 1,065 commits behind is no longer
  57 objects wide. It is **one object**, and it is named. That is a smaller
  surface to explain, and it means the next compiler change can be tested
  against a tree that is otherwise current.
- **The division lead was checked and does not hold.** `kotoba-lang/kotoba-mir`
  carries a branch named `agent/amu-constant-division`, which was recorded here
  as suggestive and explicitly not evidence. The emitted sequences have now been
  read, and division is not what changed:

  | | shipped | rebuilt |
  |---|---|---|
  | `idivq` / `cqto` / shift instructions | 14 | 14 |
  | `andq` (the ADR-0031 mask) | 16 | 16 |
  | fuel replenish immediate | `0x10000` | `0x10000` |
  | `.data` | 0x50 | 0x50 |
  | `.text` | 0x951 | **0x1062 (+76%)** |

  Both still emit `andq` before `cqto; idivq`, so the ADR-0031 signedness fix
  survives the rebuild intact. **What changed is register allocation**: the
  shipped object is push/pop-heavy (108 `pushq`, 69 `popq`, 96 `movq`), the
  rebuilt one spills to stack slots instead (348 `movq`, 21 `pushq`, 14
  `popq`), and its deepest `%rsp` offset moves from 0x88 to 0xf8.

  So the object is still not wrong and the compiler is still not obviously
  wrong — the emitted code computes the same thing by a different discipline.
  **The mechanism of the wedge remains unexplained**, and finding it needs the
  boot debugged (a QEMU gdb stub through the timer path), not more static
  reading. Recorded as unexplained rather than attributed to the nearest
  plausible branch name.
- `os/aiueos/scripts/bisect-object-migration.sh` makes this repeatable. It takes
  the control run's marker count as GOOD rather than hardcoding one, because a
  cold boot emits four fewer markers than a warm one and a constant would let an
  ordering artifact read as a result. It refuses to report a culprit it has not
  re-confirmed alone.
- **The reproduce script's compiler pin is now the thing to remove, not to
  bump.** A rebuild that reproduces from a frozen compiler proves nothing about
  the current one — ADR-0035 said so, and 0 of 57 is what that looks like when
  measured.

## What is still unmeasured

- The emitted difference in `store64` itself. The object breaks; *which
  instruction sequence changed* is unread.
- Whether the other 52 changed objects are behaviourally identical or merely
  identical **on this boot path**. 67 markers agreeing is a strong signal and is
  not a proof: the smoke exercises one boot, not every input those objects see.
