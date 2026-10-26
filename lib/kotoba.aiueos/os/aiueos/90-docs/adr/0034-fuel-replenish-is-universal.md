# ADR-0034 — Fuel replenish becomes universal, and a journal writer three calls from `ud2`

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0033

## Context

ADR-0033 doubled twelve objects' static fuel budget from 256 to 512 and flagged
`capability-plan` and `syscall-range-valid` as needing a replenishing tier
because they consume fuel 1:1 with user syscalls. Chasing that turned up the
larger fact.

Reading the emitter rather than the symptom: `package-kernel-object` emits

```
lea r9,[rip+.data]        ; 7 bytes
<replenish>               ; 8 bytes -- ONLY if bounded-memory?
sub rsp,8 / call <entry> / add rsp,8 / ret
```

with `.data+8` initialised to 512. The replenish sits **in the exported wrapper,
before the call**, so an object that has one refills on **every call** and its
fuel bounds work *within a single invocation*. An object without one decrements
a single 512 across the **entire boot**, then hits the prologue `ud2`.

**23 of 57 shipped objects had no replenish** — not two. Several scale with
workload rather than with boot structure: `net-arp-reply-valid` is charged per
received frame, `capability-plan` per syscall dispatch, `syscall-range-valid`
per `LOG_WRITE`, `idt-gate-build` per gate against a 256-entry IDT.

Nothing chose this. `elf64.clj`'s own comment described being outside the set as
a hazard, and the set's name — `bounded-memory?` — describes what an object
*does*, while what it gated was whether the object gets any fuel at all.

## Decision

**Emit the replenish unconditionally.** The tier `cond` now selects only *how
much*; objects in no named tier get the existing `:else` 1024.

`bounded-memory?` is deleted rather than repurposed. With the gate gone its only
remaining job would be "selects 1024" — the exact complement of the other three
tiers, a 24-name list that must be maintained but that no longer changes a
single emitted byte, and that can silently drift out of true. `:else` says the
same thing and cannot drift.

## Consequences

- **`service-registry-build` was three calls from trapping.** Measured by
  execution, it costs **135 fuel per call** — an FNV walk over 16 + 32 + 28
  bytes plus a 16-step record writer — against a boot-wide 512. Three calls is
  405; a fourth needs 540. It would have hit `ud2` **partway through writing a
  512-byte journal sector**. The boot passes today, so it makes at most three
  calls; the exact count was not measured, and it does not matter — a journal
  writer with a hard *lifetime* limit of three invocations is wrong at any
  count. `net-arp-reply-valid` costs 6 and would have trapped on frame **86**;
  the 1-fuel objects on call **513**.

- **Per-call cost measured, not counted.** Flatten, resolve relocation, mmap,
  prime the fuel word, call in a forked child, read it back. Static counting
  would have been wrong twice over: each object has two charge sites but the
  second belongs to the unreachable `(defn main [] 0)`, and `idt-gate-build`'s
  16 stores are inlined and charge nothing. 21 of 23 cost exactly 1; the two
  exceptions are above. Worst margin against 1024 is 7.6×, so **no tier
  promotions were needed**. Bracketed from both sides with meter controls:
  starved → SIGILL, exact → clean, one short → SIGILL.

- **The 34 already-replenishing objects are unchanged.** Checked as new emitter
  vs base emitter at the same compiler pin — comparing against *shipped* would
  have conflated this change with compiler drift. 30 byte-identical; the other 4
  fail to compile at base and after alike, so they are untouched on disk. The 23
  changed by exactly +8 bytes each and nothing else.

- **The call displacement was verified by disassembly, not by arithmetic.** The
  wrapper growing 8 bytes shifts `call-end`, `wrapper-size`, `main-offset` and
  `call-disp`; for all 23 the `e8` target resolves to `kotoba_source_entry` and
  the bytes there are the fuel prologue. Two objects have non-trivial
  displacements (`net-arp-reply-valid` 647→671, `service-registry-build`
  3160→3184) and both land.

- 118 differential cases across the 23, zero divergences, with all three
  negative controls firing (zeroed replenish immediate, flipped guard immediate,
  crossed objects). kotoba-native 72 tests / 2640 assertions, delta zero against
  a base run in a separate worktree. Repo sweep: **0 objects remain
  unreplenished.**

- **No object among the 23 wanted a boot-wide cap.** Each is either charged per
  workload event or is a pure predicate; none bounds a resource whose *total*
  consumption across a boot is the thing being limited. So universal replenish
  is right for all of them, and the previous default was simply never chosen.

- **Still open, and now better quantified: 21 of 57 objects cannot be rebuilt
  today.** 17 already-replenishing objects (`sha256`, `rsa2048`, `fnv1a`,
  `copy-in`, `digest-equal` and 12 others) differ between their shipped bytes
  and a rebuild at the current compiler, and 4 (`object-transaction-route`,
  `service-registry-state`, `task-slot-plan`, `user-elf-valid`) fail to compile
  outright with the same `if`-branch type errors repaired in ADR-0032. This is
  the ADR-0032 item, unchanged in kind and now with an exact count. Repairing it
  is still one task: fix the 4, rebuild the 17, bump
  `reproduce-kotoba-kernel-object.sh`'s compiler pin, and derive its coverage
  from `build-uefi.sh` so an object can never enter the image without entering
  the check.
