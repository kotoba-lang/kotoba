# ADR-0201 — the #108 flake is real, and it was swallowing dead guests

- Status: accepted
- Date: 2026-09-03
- The measurement behind ADR-0200's retry width and both of its limits.
- Does not close kotoba-lang/aiueos#108. It narrows what may be blamed on it.

## The claim under audit

`smoke-qemu-uefi.sh` retried every timeout, three times, at ten minutes each,
with the message `known flake kotoba-lang/aiueos#108`. Nobody had measured the
rate that budget was for. Three questions had to be answered before the retry
could be kept, narrowed or removed:

1. Does the issue exist, and does it name a signature?
2. Does it reproduce **on this host**?
3. What does a good boot actually cost, so a timeout can be set from data?

## 1. The issue exists and it is specific

kotoba-lang/aiueos#108, OPEN, *"Flaky hang in the ring-3 process phase on slow
QEMU/TCG runners"*. It is not a vague flake claim. It names:

- **a signature** — *"the dumped serial tail consistently ends at
  `AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec segments=rx,rw
  result=42 domains=4,5`"*, i.e. the boot task is inside
  `aiueos_process_enter()`'s wait loop and never observes its exit condition;
- **a mechanism** — a suspected lost-wakeup race between the wait-loop
  condition checks and `hlt` under dilated TCG timing;
- **a rate and a place** — *"~1 boot in ~15-25 on ubuntu runners; never
  reproduced locally (macOS, QEMU 10, faster host)"*.

**Everything needed to stop it swallowing a dead guest was in the issue from
the day it was filed.** The retry never read it. It keyed on exit status 124,
which a lost wakeup and a `#UD` produce identically, so the one fact that
separates them — *where the serial log stops* — was on disk, unexamined, in
every run that printed the message.

## 2. It reproduces here. Rarely.

Two independent measurements on this workstation (macOS, QEMU 10, concurrent
agent load), against a known-good image, retries disabled:

| measured by | n | flakes | load |
|---|---|---|---|
| this ADR, `measure-boot-flake-rate.cljs`, 16 consecutive boots of one built image | 16 | **0** | 67-125 |
| BISECT-SHA256, `boot-sample.cljs` | 8 | **1** (caught live: quiet at 109.7 s, then silent ~500 s) | 63-99 |
| combined | **24** | **1** | |

So the issue's *"never reproduced locally"* is **out of date** — it has now been
reproduced here once. But 1 in 24 is far from the 1-in-15-to-25 the ubuntu
runners saw, and this host is the only host that runs these gates now (the
workspace retired GitHub Actions).

**Verdict: the retry is kept and narrowed, not removed.** A real hang that
reproduces once in twenty-four justifies a second attempt. It does not justify
retrying *anything* that fails to exit. From ADR-0200 on, a retry requires the
signature — the last serial line beginning `AIUEOS_KOTOBA_ELF_PROCESS_OK` — or
no guest output at all. Everything else is reported on the first attempt.

n=24 is small and is stated as such. It is enough to say the flake is real and
rare; it is not enough to put a confidence interval on the rate, and none is
claimed.

## 3. What a good boot costs

`measure-boot-flake-rate.cljs --out build/aiueos --runs 16 --timeout 180`, one
already-built image booted sixteen times with **no rebuild between runs** —
deliberately, because a rebuild between runs would make a compiler change and a
flake look alike.

```
SCANNED 16
  pass 16
PASS-BOOT-SECONDS n=16 min=68.5 p50=85.1 p90=122.0 max=165.5
FLAKE-RATE 0/16
DEAD-OR-BROKEN 0/16
```

Every run's load average is printed beside its wall clock, because this
workstation runs many concurrent agents and a duration read at one hour is not
comparable with one read at another. The 165.5 s run was at load 124.9; the
68.5 s run at 119.5. **The correlation is weak enough that no curve is fitted
and none should be quoted.**

Two numbers come out of this, and they are different kinds of number:

| limit | value | why |
|---|---|---|
| wall clock | **360 s** | 2.2x the slowest good boot observed (165.5 s). Was 600, which was the ubuntu CI job budget, never measured here |
| quiescence | **150 s** | 2.25x the longest silence observed in a good boot (66.5 s over n=7, BISECT-SHA256) |

The quiescence limit is the one that fires. It is justified by the boot's
**phase structure**, not by a single reading: a healthy full-evidence boot has
exactly one long silent stretch, PCI enumeration under TCG between
`AIUEOS_APIC_TIMER_OK` and `AIUEOS_PCI_OK`, measured byte-for-byte at 47 s.
Silence there is expected; silence elsewhere is not.

**Caveats that are not rounded away.** 66.5 s is an observed maximum over seven
runs, not a bound. The gap grows with load but not monotonically — largest at
load 84-87, not at 96-99 — and the 165.5 s run above was at a load higher than
anything in that n=7. That is exactly why the limit is 2.25x and not 1.35x: a
quiet limit that kills a healthy boot converts this fix into the bug it fixes.
These are one workstation's numbers under concurrent agent load; the method
transfers, the numbers should be re-measured per host with the tool.

## What this changes in wall clock

| what happened | before | after |
|---|---|---|
| a Kotoba object traps after the ADR-0199 gates | 3 x 600 s, announced as a flake | the kernel exits: **~6 s** |
| a trap in the one object still ahead of those gates | 3 x 600 s | quiet watchdog: ~18 + 150 = **~168 s**, one attempt |
| a genuine #108 hang | 3 x 600 s = 1800 s | quiet at ~110 s + 150 = ~260 s per attempt, retried: **worst case ~780 s** |
| a good boot | unchanged | unchanged |

## The tool

`os/aiueos/scripts/measure-boot-flake-rate.cljk`. It exists because a retry
budget nobody measured is not a measurement, and the next agent to change these
numbers should change them against a file. Three exit codes, and the third is
the point: `3` COULD-NOT-RUN when there is no image, no QEMU, no OVMF, or fewer
than four runs asked for. **A rate computed from zero boots is not a low rate**,
so it is a refusal and not a warning. Verified both ways: `--out <nothing
there>` and `--runs 1` each exit 3 with a named reason.

## What is not done

- **#108 itself is not fixed.** The lost wakeup in `aiueos_process_enter()`'s
  wait loop is still there; the issue's own suggestion (re-check the condition
  after a bounded number of ticks, or add a watchdog re-dispatch in the timer
  path) is untouched. This ADR only stops it being used as an explanation for
  things that are not it.
- **The issue text still says "never reproduced locally".** That is now false
  and this ADR is the counter-evidence; the issue has not been edited.
- **n=24 across two tools and two load regimes.** Enough to keep the retry, not
  enough to tune it.
- **The 47 s PCI phase is not used programmatically.** ADR-0200's watchdog is
  phase-*informed* (the threshold comes from that structure) but not
  phase-*aware*: it does not know which phase the guest is in, so it cannot
  apply a tighter limit outside the known-quiet stretch. That is the next
  increment, and it would take the dead-guest detection from ~168 s to ~30 s.
