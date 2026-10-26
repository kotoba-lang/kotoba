# ADR 0195: a budget nobody has spent past is a number, not a bound

Status: accepted. Date: 2026-09-03.

## Context

Two ADRs in this repository reasoned from **2,147,483,647** as though it were
the fuel ABI:

- **ADR-0142** capped `sha256-region`'s window at 1 MiB, in as many words:
  *"the replenish immediate is 32 bits so 2,147,483,647 is the largest tier ANY
  object can have, which at 14,894/block pays for 8.80 MiB."*
- **ADR-0175** concluded that `evaluate_token` **cannot be one Kotoba object**,
  because the output projection alone is 248,320 × 5,120 = 1,271,398,400 MACs
  ≈ 27,970,764,800 fuel — thirteen times that ceiling — and left the forward
  pass with C calling each object in turn.

Both were right about the number and wrong about what it was. It is the width
of the immediate in `mov qword [r9+8], imm32`, which the CPU sign-extends. The
context field is a `uint64_t`, the charge is `dec qword [r9+8]`, and the image
route has always written eight data bytes.

kotoba-native ADR 0078 widened the object replenish (`movabs r10, imm64;
mov [r9+8], r10` above 2^31, the existing 8-byte form at or below it, so no
shipped object's bytes move). kotoba-kir ADR 0268 put the ceiling at 2^53−1.
Between them there are byte goldens on two runtimes and a KIR test that a
budget past 2^31 is carried rather than truncated.

**None of that is a claim about a machine.** A ceiling that has been raised and
never walked past is a larger number, not a larger bound.

## Decision

**Spend more than 2^31 fuel on a CPU, and prove the guard still fires.**

`os/aiueos/native/fuel-wide-probe.kotoba` is a self-recursive countdown in four
stages, writing one character to the 0xe9 debug console after each, then
exiting 33 through `isa-debug-exit`. `os/aiueos/scripts/smoke-qemu-fuel64.cljk`
compiles it **twice from one source**, differing only in `--fuel`, and boots
both under OVMF.

```
PROBE total-cost=2200000005 enough=2500000000 short=2000000000 2^31=2147483648
IMAGES-DISTINCT enough=e129baf78987 short=4823b1f61990
IMAGE-FRESH enough artifacts=2
SCANNED 2
IMAGE-FRESH short artifacts=2
SCANNED 2
enough: exit=33 console="F1234O" elapsed-ms=37692 reached-fuel=2200000005 charges-per-second=58367824
short:  exit=0  console="F123"   elapsed-ms=29699 reached-fuel=1500000004 charges-per-second=50506751
AIUEOS_FUEL64_QEMU_OK spent=2200000005 past-2^31-by=52516357 budget=2500000000
                      control-stopped-at=1500000004 of=2000000000
```

**2,200,000,005 fuel spent, 52,516,357 past 2^31, and the object returned.**
Under the ceilings that stood on 2026-09-02 that budget could not have been
compiled at all: `kotoba.verifier` admitted at most 1,048,576.

### The control is the half that makes it evidence

A run that only ever finishes is equally consistent with a guard that never
fires, and a fuel bound whose guard never fires is not a bound. The two images
are the **same source, the same compiler, the same flags** except the budget —
`IMAGES-DISTINCT` proves the two artifacts differ, and after amu ADR 0332 that
line is not free: the UEFI packager was discarding `--fuel` entirely, so on
that route the two images would have been byte-identical and the "control"
would have been the experiment run twice.

The short budget stops at `F123`, exactly where the arithmetic says: three
burns cost 1,500,000,004 and fit inside 2,000,000,000; the fourth needs
700,000,001 more and only 499,999,996 remains, so the guard fires *inside* it.
It never prints `4`.

Its exit is 0 rather than 33, which is the `ud2` signature under `-no-reboot`:
the prologue traps, there is no IDT to take vector 6, the CPU triple-faults and
QEMU exits on the reset it is told not to perform. The smoke asserts the exact
console **and** that the status is not 33; the console is what distinguishes
"stopped for lack of fuel" from "stopped for some other reason", because the
only difference between the two images is the budget.

### The measured rate, and what it says about the ceiling

**58,367,824 charges/second** under QEMU TCG on this host (Apple M4; there is
no other x86-64 here).

**That number is a snapshot, not a constant, and the second run says so.** The
same smoke re-run twenty minutes later on a busier workstation reported
**26,664,727** charges/second for the identical artifact — same console, same
2,200,000,005 spent, 2.2× slower. Quote the *order* (tens of millions per
second under TCG on a loaded machine) and re-measure before quoting a figure.
The table below is computed at the faster of the two, which is the kinder
direction for the argument it supports: if the ceiling is a bound at 58M/s, it
is more of one at 27M/s.

At 58,367,824 charges/second:

| budget | TCG, this host | a real CPU at 1e9 charges/s |
|---|---|---|
| 2^31−1 (the old imm32 ceiling) | 36.8 s | 2.1 s |
| 2^53−1 (the new ceiling) | 4.9 years | 104 days |
| 2^62−1 (the wasm ceiling) | 2,503 years | 146 years |
| 2^63−1 (what the qword could hold) | 5,007 years | 292 years |

**That is not an argument that 2^53−1 is a good budget.** It is an argument
that it is a *bound* — finite, exactly counted, and reached in a time a person
could observe. A tier anywhere near it, on an object this kernel calls with
interrupts disabled, is a hang and not a bound. The ceiling is what the
mechanism may carry. The per-object tiers stay measured by execution with a
stated margin, and no shipped object is within six orders of magnitude of it.

## Consequences for the two ADRs that quoted the old number

- **ADR-0142's 1 MiB window no longer follows from the encoding.** At 14,894
  fuel per 64-byte block the new ceiling pays for roughly 36 TiB, which is past
  every other bound in that object. Whether to raise the window is a separate
  measurement and this ADR does not make it.
- **ADR-0175's arithmetic is unchanged and its conclusion is not.**
  27,970,764,800 fuel for the output projection is now **four orders of
  magnitude inside** the ceiling — 0.1 hours at the TCG rate above, 28 seconds
  at 1e9/s. The road is open.

  **It is not built, and this ADR does not build it.** ADR-0175's other
  findings stand on their own: `ffn` and `linear_attention` are not objects,
  the four-lane binary64 score tree is implemented but unverified, and the
  whole-token figure is larger than the projection alone. What has changed is
  that "one object cannot hold the budget" has stopped being a reason. The tier
  such an object would need is the whole-token cost, which nobody has measured
  — the projection is a lower bound on it, not an estimate of it.

## What this does not claim

The probe runs through the **image** route, so what it exercises is the 64-bit
context word and the `dec qword [r9+8]` guard past 2^31. The **wide immediate**
itself (`movabs r10, imm64`) is proven by byte goldens on both runtimes and by
`aiueos-fuel-wide-probe` being in the production object table — it has not been
executed, because that would need the object linked into a kernel image and
called, which is a larger change than this stream should make. The two claims
are separate and are reported separately.

## Reproducible from where

**Not from amu main, until the pin bump in amu #764 merges.** Measured rather
than assumed — the smoke run against the shared amu checkout answers:

```
COULD-NOT-RUN compile-failed at fuel=2500000000:
  :error :verify  "native fuel budget is not admitted"
```

because `kotoba.verifier` at the pin amu main currently carries admits at most
2^20, so the probe's 2,500,000,000 is refused before any machine sees it. The
run recorded above used an amu carrying kotoba-kir `233bd6bb`, kotoba-native
`95361f3f` and kotoba-verifier `d1985d62`.

This is the gap SMOKE-FRESHNESS named: a QEMU proof that reproduces only
against a private branch. It is written down here rather than left for someone
to rediscover, and the three-outcome convention (ADR-0155) is what let the
harness say so — `COULD-NOT-RUN` rather than a failure, because a machine that
cannot compile the probe has not disagreed with anything.
