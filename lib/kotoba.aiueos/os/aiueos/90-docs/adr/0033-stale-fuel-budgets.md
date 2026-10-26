# ADR-0033 — Twelve objects running on half a fuel budget, and a per-boot syscall ceiling nobody had noticed

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0032

## Context

ADR-0032 reported that "8 objects" reproduce to different bytes at the current
compiler, all carrying `.data[8]` = 256 where the current base is 512. That
number was wrong in both directions, and measuring it properly is most of this
ADR.

`.data`'s second quadword is an object's **initial fuel budget** — the number of
invocations it gets before the prologue's `cmpq $0,0x8(%r9); jne; ud2` fires. It
is only load-bearing for objects with **no prologue replenish**; those in
`bounded-memory?` overwrite it at `.text+7`, immediately after the opening
`leaq`. Across the 57 shipped objects:

| | count |
|---|---|
| carrying the stale 256 | **33** |
| …of which also replenish → the 256 is **dead data** | 21 |
| …of which genuinely run on 256 for a whole boot | **12** |

ADR-0032's eight came from auditing only the `quot`-carrying objects; five of
those eight in fact replenish, so their 256 never mattered, and nine genuinely
affected objects were missing from the list.

The twelve: `capability-mutation-plan`, `capability-plan`, `journal-plan`,
`kernel-probe`, `page-mapping-plan`, `pci-extent-valid`, `pci-region-valid`,
`process-teardown-plan`, `service-lifecycle`, `service-task-transition`,
`syscall-range-valid`, `virtio-cap-valid`.

## Decision

Rebuild those twelve from unmodified source at the current compiler. No source
edits; the rebuild is the entire change.

## Consequences

- **The `.text` drift is real but not semantic, and its shape is now known.**
  Eleven of the twelve changed (`kernel-probe` is byte-identical); sizes fall
  6–22%. The old compiler **re-evaluated each `let` binding at every use site**;
  the current one materialises it once. Instruction counts pin this exactly —
  `capability-plan` has 3 `quot` in source and emitted **8 `idivq` before, 3
  now**; `service-task-transition` 1 in source, **4 before, 1 now**. No new
  instruction class appears in any new build except `nopl` padding, and
  critically `idivq` stayed `idivq`: nothing was strength-reduced to a shift, so
  the signed-division hazard of ADR-0031 was neither introduced nor silently
  removed.

- **734,912 differential cases, zero divergences.** All twelve are pure scalar
  functions, so the case space was attacked directly rather than sampled: caller
  tuples taken from `pci.c`/`syscall.c`/`scheduler.c`/`process.c`/`paging.c`, a
  cartesian grid over each object's own guard constants and their ±1 neighbours,
  and fixed-seed random including full 64-bit values. Unused argument slots
  carry poison rather than zero, so an over-read would surface as divergence.
  Every call ran in a forked child against a `MAP_SHARED` block with
  resume-on-trap, comparing return value, termination signal, **measured** fuel
  consumption, and the whole 80-byte `.data` outside the fuel word.

  **Three live negative controls**, because "no divergence" from a harness that
  cannot find one is worthless: zeroing the new side's fuel word produced SIGILL
  on all 41,107 cases with the harness surviving; flipping one guard immediate
  `0→1` caught 284 divergences; crossing two different objects caught 6,361.

- **Was 256 ever close? No — and the fix is not where the risk is.** Measured
  fuel is **1 per call** for all twelve (each has two charge sites, but the
  second belongs to the unreachable `(defn main [] 0)`), so the budget is
  literally calls-per-boot: 256 before, 512 now.

  The three PCI validators are *not* on the 256×32 slot scan — that is
  `pci-config-read`, which replenishes. They fire only on present virtio
  devices: ~20–40, ~4 and ~4 calls against 256 in the gate's configuration. The
  structural worst case is 256 buses × 32 devices × 8 functions × a 48-cap walk
  = **3,145,731**, against which doubling 256 to 512 is four orders of magnitude
  short. So this rebuild removes a latent risk with large margin; it does not
  make a dense or hostile PCI topology safe, and should not be cited as if it
  did.

- **The tighter exposure is elsewhere, and it is the finding worth keeping.**
  `capability-plan` is charged once per syscall dispatch and `syscall-range-valid`
  once per `LOG_WRITE`. Both scale **1:1 with user syscalls**, so their fuel word
  is a hard ceiling on syscalls per boot — 256 before, **512 now**. For a
  syscall-path validator that is a very low ceiling: today's boot performs ~14–20
  of each along a straight-line self-test, so there is margin, but this is the
  one number that scales with *workload* rather than with topology, and no real
  workload lives under 512 syscalls. `service-lifecycle` and
  `service-task-transition` sit on the timer ISR but are gated by a one-shot
  deterministic fault injection that cannot re-fire once the generation advances.

  **These two belong in a replenishing tier, not in a doubled static budget.**
  That is the next increment, and it is a `bounded-memory?` classification
  decision rather than a rebuild.

- **`kernel-probe` is also linked by `build-multiboot.sh`** — the only one of the
  twelve, and exactly the missed-link class that broke that build at ADR-0024.
  Pinned in both scripts, and both verified by building rather than reading.

- Repo sweep after the rebuild: **0 objects remain at 256-without-replenish**;
  36 at 512; the 21 dead-256 objects deliberately untouched, since rebuilding
  them would be pure codegen churn for no runtime effect. They still block a
  compiler-pin bump in `reproduce-kotoba-kernel-object.sh`, which remains the
  open item from ADR-0032 along with deriving that script's coverage from
  `build-uefi.sh` — it still checks 36 of 57 objects.
