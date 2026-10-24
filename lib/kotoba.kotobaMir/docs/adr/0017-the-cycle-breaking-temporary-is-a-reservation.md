# ADR-0017: The cycle-breaking temporary is a reservation, not a proposal

- Status: accepted
- Date: 2026-09-02

## Context

A parallel copy that contains a register cycle breaks it through one frame
slot. `schedule-parallel-copies` takes that slot as an argument and reports
whether it used it, and the allocator pins it on first use by stepping
`:next-slot` past it. That much is right.

The seed was not. `entry-argument-plan` returns the same number under two
names -- `:stable-slot-count` and `:temp-slot` -- because at entry the two
coincide: one past the entry spills is both the next free slot and a fine
place to put a temporary. `allocate-without-spills` then carried `:temp-slot`
into the loop unconditionally:

```clojure
next-slot (cond-> (:stable-slot-count entry) (:used-temp? entry) inc)
temp-slot (:temp-slot entry)          ; <- carried even when nothing reserved it
```

When the entry parallel copy had no cycle, nothing stepped `:next-slot` past
that number, so the body's first `spill-assigned` was handed the very slot
`:temp-slot` still named. Every later cycle break then stored into a slot that
held a live value, and the reload that value's next use performed read the
temporary instead.

A function whose arguments all fit in registers at entry gets `:temp-slot` 0,
and slot 0 is what the first spill takes -- so the collision lands on the value
spilled earliest, which in practice is the first argument.

Measured 2026-09-02 on `kotoba-lang/aiueos`
`os/aiueos/kotoba/hkdf-sha256.kotoba`, compiled to
`x86_64-aiueos-kernel-v1`. Its `hmac-mode` holds `ctx` in slot 0 across six
calls; the fourth call wants the literal 92 in `%rdx` and 0 in `%rcx` while
those two registers hold each other's values, so the swap breaks its cycle
through slot 0:

```
2a04: movq %rcx, (%rsp)     ; the literal 92 into the slot holding ctx
2a0f: movq (%rsp), %rdx     ; 92 -> arg 3, as intended
2a17: movq (%rsp), %rdi     ; 92 -> arg 1, which is ctx
```

The object then read and wrote absolute addresses 92+i for the rest of the
call. `expand-label-mode` in the same object did it twice, with 54 and 92.

The KIR reference interpreter runs the same program correctly in under 65,536
fuel, so nothing above this layer could see it.

## Decision

**`:temp-slot` is only carried into the body when something reserved it.**

```clojure
temp-slot (when (:used-temp? entry) (:temp-slot entry))
```

Left `nil`, `emit-call` derives the temporary from the CURRENT `:next-slot`
and pins it on first use -- which is what both of its `(or (:temp-slot state)
(:next-slot state))` sites already assume, and what makes the pin correct.
Once pinned it is reused by every later cycle in the same function, so this
costs at most one slot and usually none.

## Consequences

- A function that both spills and contains a copy cycle gets a frame one slot
  larger than before, and its cycle stores move to that slot. Nothing else in
  the suite changed: 103 tests / 1984 assertions pass unchanged.
- The regression test is
  `the-parallel-copy-temporary-never-lands-on-a-live-slot`. It transcribes the
  GMIR `amu` builds for the `hmac-mode` shape -- an earlier hand-written
  version shared one zero constant between the call sites, which changes the
  pressure and did not reproduce -- and then interprets the PHYSICAL stream
  over one tracked value, reporting what argument register 0 held at each of
  the six calls. Before the fix, x86-64 reports
  `[tracked tracked tracked other other other]`; after it, six `tracked`. The
  count of calls seen is asserted first, so a run that does not reach six is
  not counted as a pass.
- AArch64 has eight preserved registers and does not spill on this fixture, so
  the test is a real discriminator only on x86-64 today. It runs on both
  targets rather than being narrowed, because the defect is in
  target-independent code and a future pool change can move which target
  reaches it.
