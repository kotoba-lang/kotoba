# ADR-0200 — three outcomes, and a retry that has to name what it is retrying

- Status: accepted
- Date: 2026-09-03
- The harness half of ADR-0199. ADR-0201 measures the flake this narrows.
- Extends ADR-0155, which gave `smoke-qemu-uefi.sh` its exit-3
  (COULD-NOT-RUN) and exit-4 (REFUSED stale-image) floors. This adds the
  distinction ADR-0155 left inside exit 1.

## The defect

```sh
if [ "$status" -eq 124 ] && [ "$attempt" -lt "$qemu_attempts" ]; then
  echo "warning: QEMU hung on attempt ${attempt}/${qemu_attempts} \
        (known flake kotoba-lang/aiueos#108); retrying" >&2
```

One question — *was it a timeout?* — for two entirely different events. A
guest that had already died of `#UD` on the first boot and a guest that lost a
wakeup in the ring-3 phase gave the same answer, and the answer named the
second one.

This is the workspace's forbidden shape (AGENTS.md: *a check that could not
answer returning the same value as a check that ran and found nothing wrong*)
with an extra turn of the screw: the retry loop **converts a deterministic
failure into a flaky-looking one**. A miscompiled object does not fail once and
get investigated; it fails three times, is announced as a known flake twice,
and is then reported as a timeout. BISECT-SHA256 measured a run that *"spent 10
minutes reporting `known flake` for a kernel that had already died of `#UD` on
the first boot"*. TLS-DIAG hit the same wall from the other side: one of its
boots span for 9m53s.

Exit status cannot separate them, and no change to the kernel can make it: both
events are "QEMU is still running". **What separates them is what the guest
wrote, and when.**

## The decision

**A retry may only cover a timeout the harness can NAME. Every timeout that
produced guest output and is not the named signature is a result, reported
immediately, once.**

Four outcomes, and the exit status alone tells three of them apart:

| exit | meaning | literal |
|---|---|---|
| 0 | the guest ran and every assertion held | `AIUEOS_UEFI_SMOKE_OK` |
| 1 | a real failure | see below |
| 3 | COULD-NOT-RUN — nothing was measured (ADR-0155) | `COULD-NOT-RUN build-failed` / `qemu-missing` / `ovmf-missing` / `nbb-missing` |
| 4 | REFUSED stale-image (ADR-0155) | from `image-freshness.cljs` |

Exit 1 is subdivided by literal rather than by a new status, because fifteen
sibling scripts spawn this one and test it against zero. The literals:

| literal | what happened | retried? |
|---|---|---|
| `GUEST-DIED` | the kernel's own `AIUEOS_FATAL_EXCEPTION` line is in the log — whether it then exited or not | **never** |
| `GUEST-NO-EXIT` | the guest wrote something and stopped, and the last line is not the signature | **never** |
| `HOST-FLAKE-SIGNATURE` | every attempt's last serial line is `AIUEOS_KOTOBA_ELF_PROCESS_OK` | yes, up to `AIUEOS_QEMU_ATTEMPTS` |
| `HOST-NO-OUTPUT` | not one byte on either transport | yes |
| `error: unexpected QEMU exit status N` | a deterministic status nobody expected | never (unchanged) |

`HOST-NO-OUTPUT` is retried because nothing about the guest was measured: the
firmware never reached the debug console. That is the only timeout for which a
second attempt can honestly be said to be answering a different question.

## The timeout is now a measurement

Two limits, and the second one is the one that fires.

**`AIUEOS_QEMU_TIMEOUT` 600 -> 360.** 600 was never measured on this host; it
was a CI job budget, inherited from the ubuntu runners that issue #108 was
filed against and that this workspace has since retired. 360 is 2.2x the
slowest good boot measured here: `measure-boot-flake-rate.cljs` (this ADR's
tool), 16 consecutive boots of one already-built image with **no rebuild
between runs**, so a compiler change cannot be mistaken for a flake — all pass,
min 68.5 / p50 85.1 / p90 122.0 / **max 165.5** seconds, at load average
67-125. Full table and caveats in ADR-0201.

**`AIUEOS_QEMU_QUIET` = 150 (new).** How long the guest may write nothing on
*either* transport before the attempt ends. This is what makes a dead guest
fail fast, and unlike the wall clock it does not scale with how slow the host
is. The number is justified by the boot's phase structure: a healthy
full-evidence boot has exactly one long silent stretch — PCI enumeration under
TCG between `AIUEOS_APIC_TIMER_OK` and `AIUEOS_PCI_OK`, measured byte-for-byte
at 47 s — with the longest silence over n=7 good boots at 66.5 s
(BISECT-SHA256, 2026-09-03). 150 is 2.25x that, and deliberately not tight:
66.5 s is an observed maximum over seven runs, **not a bound**; the gap grows
with load but not monotonically (largest at load 84-87, not 96-99); and the
165.5 s run above was at load 124.9, higher than anything in that n=7. A quiet
limit that kills a healthy boot converts this fix into the bug it is fixing.

The watchdog normalises its exit to 124 on purpose. Every branch below, and
fifteen sibling scripts, already know what 124 means; *which* limit ended the
attempt is reported in the message, not encoded in a status nobody downstream
reads.

Every run now appends its QEMU wall clock to `build/aiueos/boot-times.log`:

```
boot status=97 elapsed=79s attempt=1
```

so the next agent to change this number changes it against a file, not against
intuition. **A run that reports "timed out" without saying how long it waited
cannot be compared with the runs that passed**, which is why the timeout report
now carries `after ${qemu_elapsed}s` and the write timeline.

## The write timeline, and why it is reported and not enforced

Every timeout report now says when the guest last wrote to *either* transport:

```
GUEST-NO-EXIT after 60s (attempts=1): the guest produced output and then stopped
  last serial: !!!! Can't find image information. !!!!
  last debug : AIUEOS_EARLY_FAULT_SMOKE synthetic mode=2 before-objects
  NOT kotoba-lang/aiueos#108: that hang stops at AIUEOS_KOTOBA_ELF_PROCESS_OK.
  write timeline: last byte on either transport at T+6s, then 54s of silence
```

That is a dead guest described exactly: it stopped six seconds in and the
remaining fifty-four were the harness waiting.

**It is not a kill switch.** A healthy full-evidence boot has a genuine ~60 s
stretch with no write on either transport immediately before its final marker
(measured by the BISECT-SHA256 stream, 2026-09-03). Any quiet threshold short
enough to catch a dead guest early would also kill boots that are working, so
the timeline is evidence for the reader and the wall clock stays the decision.

Two harness bugs the same stream had to fix before its numbers were
trustworthy are fixed here too, because they bite this file the same way:

- **Both logs are deleted before every attempt, not once before the first.** A
  retry that inherited the previous attempt's debugcon log started its clock
  about fifty seconds early and made the *build* look like the largest gap.
- **Both streams are watched.** Measuring quiet on debugcon alone reports the
  guest silent while it is actively writing to serial — and on this firmware
  the OVMF exception dump goes to *serial*, so a debugcon-only reader would
  have concluded the guest said nothing at all.

## A guest that died and DID exit

With ADR-0199 the common case is not a timeout at all: the kernel exits with
status 251. That used to arrive as `error: unexpected QEMU exit status 251`
followed by eighty lines of a debug log whose last useful entry had been
written by the firmware. It now leads with the kernel's own line:

```
GUEST-DIED after 6s: the guest terminated on a fatal CPU exception
  AIUEOS_FATAL_EXCEPTION vector=6 mnemonic=#UD/invalid-opcode error=0x00000000 ...
```

placed after every deliberate-corruption gate, so `AIUEOS_EXPECT_FAULT` — which
asks for exactly this fault on purpose — keeps its own handling and its own
`AIUEOS_FAULT_BOOT_OK`. Verified: that gate still exits 0.

## Evidence

Red and green are the same defect, twice, differing only in the harness.

| build | harness | outcome | wall clock |
|---|---|---|---|
| `#UD` before the objects, ADR-0199 table OFF | pre-ADR-0200 (`git show origin/main:...`) | `known flake kotoba-lang/aiueos#108` x2, then timeout | **198 s** at `AIUEOS_QEMU_TIMEOUT=60`; **1800 s** at the shipped 3 x 600 |
| same image | this branch, wall clock only | `GUEST-NO-EXIT after 60s (attempts=1)` + timeline | 77 s |
| same image | this branch, quiet limit 30 s | `ended by: the quiescence watchdog, after 33s ... (limit 30s)` | 58 s |
| same image | this branch, **shipped** limits (360 / 150) | `GUEST-NO-EXIT after 158s (attempts=1)`, ended by the watchdog after 150 s of silence, `last byte at T+6s` | **174 s** |
| good image | this branch, **shipped** limits | `AIUEOS_UEFI_SMOKE_OK` — the watchdog does **not** fire | 103 s |
| `#UD` after the ADR-0199 table | this branch | `GUEST-DIED after 6s` + the fatal line | **22 s** |
| `int3` (vector 3, generated no-error stub) | this branch | `GUEST-DIED after 5s`, `vector=3 mnemonic=#BP/breakpoint error=0x00000000` | 20 s |
| `mov $0x48,%ds` (vector 13, generated error-code stub) | this branch | `GUEST-DIED after 7s`, `vector=13 mnemonic=#GP/general-protection error=0x00000048` | 25 s |
| unmodified | this branch | `AIUEOS_UEFI_SMOKE_OK` | 95 s |
| `AIUEOS_EXPECT_FAULT=1` | this branch | `AIUEOS_FAULT_BOOT_OK synthetic-fault polled-receipt-written`, exit 0 | 118 s |

The reason literals are pinned, not just the verdicts. `error=0x00000048` in
the vector-13 row is the selector the probe chose: an error-code stub that
forgot its extra push would have printed the RIP there, and both fields would
still have looked like plausible addresses.

## What this does not fix

- **The retry width is narrowed, not removed.** `HOST-FLAKE-SIGNATURE` still
  retries three times. ADR-0201 says why that budget is justified (1 flake in
  24 boots across two tools) and why it is not tuned further (n is too small).
- **The watchdog is phase-INFORMED, not phase-AWARE.** Its threshold comes from
  the 47 s PCI stretch, but it does not know which phase the guest is in, so it
  cannot apply a tighter limit outside that stretch. Doing so would take
  dead-guest detection from ~168 s to ~30 s and is the next increment.
- **`smoke-qemu-firmware-matrix.sh` and fourteen other harnesses** are still
  unattested by ADR-0155's freshness receipt and have no timeout classification
  of their own. They spawn this script and inherit its behaviour where they
  spawn it; where they run QEMU themselves they do not.
- **A guest that dies without reaching `isa-debug-exit`** — the residuals in
  ADR-0199 §"What is still indistinguishable" — still arrives here as
  `GUEST-NO-EXIT`. That is the correct verdict and it is not the vector.
