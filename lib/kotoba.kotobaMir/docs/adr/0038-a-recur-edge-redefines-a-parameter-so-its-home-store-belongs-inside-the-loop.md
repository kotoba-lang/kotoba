# ADR 0038: a recur edge redefines a parameter, so its home store belongs inside the loop

Status: accepted. Date: 2026-09-03.

## Context

`store-at-definition` splices a spill store at the point a value was defined
rather than at the point the register ran out, and it says why:

> A definition dominates every use of its value, because the program is in SSA
> form, so a store placed there is executed before any reload of it can be
> reached.

That is true of every value this allocator sees except one family. A function
with a direct reentry edge has a `:mir/recur` that **redefines the parameter
homes** and branches back to the `:mir/reentry` marker. The marker is emitted
after `entry-argument-plan`'s instructions:

```clojure
out (cond-> (:instructions entry)
      direct-reentry? (conj {:mir/op :mir/reentry :mir/parameters parameter-homes}))
```

and every entry-plan value was given `def-position` = `(count (:instructions
entry))` — the index the marker occupies. A store spliced there lands *before*
the loop header. It runs once. The reloads inside the body run every iteration,
so from the second iteration on they answer with the value the parameter held
on entry.

`spill-assigned` then cannot repair it, and says so in its own comment: "a value
already in a slot needs no second store: it never changes, so what was written
the first time is still what is there." Under SSA that is right. Across a recur
edge it is not.

## What it did

`os/aiueos/kotoba/aiueos/sha256.kotoba`, compiled for
`x86_64-aiueos-kernel-v1`. `round-block` recurs on `(workspace, i)` and reads
`i` twice per iteration: the exit test `(= i 64)` at the top, and `(+ i 1 ...)`
at the bottom, after ten guest calls. The allocator put `i` in `r12`, evicted it
for a body temporary, and backed it with frame slot `0x60`:

```
1998: movq %rsi, %r12            ; i -> its parameter home
199b: movq %r12, 0x60(%rsp)      ; the ONE store, before the loop header
19a3: <loop header>              ; :mir/reentry
19a8: cmpq %rax, %r12            ; (= i 64) -- reads the register, correct
...
1d29: movq 0x60(%rsp), %r13      ; (+ i 1) -- reads the slot, ALWAYS 0
1d34: addq %rcx, %rdx            ; so the next i is always 1
1da4: movq %rdx, %r12
1db7: jmp 0x19a3
```

`i` is 1 on every iteration after the first, `(= i 64)` never holds, and the
object spins until its fuel guard traps with `#UD`. Measured in QEMU under OVMF:
`AIUEOS_INITRAMFS_OK` is printed, `AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK` never
is, and `RIP` resolves to object offset `0x175`, which is the `ud2` of a fuel
guard. aiueos ADR-0150 recorded the symptom and bounded it to amu
`9cf3a0ac..7e8f06d7`; the bisect lands on kotoba-native `da3b56b` (x86 direct
self reentry), which is the commit that pinned kotoba-mir `3aea0acc` (the x86
half of this allocator path) and emitted the x86 back edge for it.

The defect is **not** x86-only. The regression test below fails on both targets
at the same assertion: AArch64 has enough registers that the aiueos objects
never spilled a parameter home, so nothing had reached it.

## Decision

An entry-plan value's definition position is one instruction later when the
function has a direct reentry edge — after the `:mir/reentry` marker rather than
before it. The store then sits at the top of the loop body, where the parameter
home register is correct on the entry path and on every back edge.

```clojure
def-position (zipmap (keys (:assigned entry))
                     (repeat (cond-> (count (:instructions entry))
                               direct-reentry? inc)))
```

Nothing else moves. `spill-assigned`'s "no second store" rule stays: within one
iteration the parameter does not change, so the slot written at the top of the
body is still correct at any later eviction. Functions without a reentry edge
keep the position they had, so no existing object's bytes move for that reason.

## Consequences

- One store executes per iteration in a direct-reentry function that spills a
  parameter. That is the cost of the value being live; the alternative was
  reading the wrong one.
- `test/kotoba/mir_test.cljk`
  `direct-reentry-spills-a-parameter-home-inside-the-loop` asserts that no
  `:mir/spill-store` precedes the `:mir/reentry` marker, on every target, and
  carries an evidence floor: the fixture must actually produce a reentry edge,
  at least one store and at least one load, or the run failed to measure rather
  than passed. Reverting only the `cond->` above turns it red on both targets
  with `(not (> 4 5))` — a store at index 4, the marker at index 5.
- The rule this ADR narrows is worth stating in the negative: **an allocator may
  splice a store at a definition only for values no edge redefines.** `:mir/recur`
  is the one edge in this MIR that does.
