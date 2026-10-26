# ADR-0211 — icount turns a clock that cannot measure into a counter that can

- Status: accepted
- Date: 2026-09-10
- Related: ADR-0165 (two arms that agree on the wrong fixture), ADR-0116
  (the exact-artifact benchmark), ADR-0202 (the board computed the answer),
  ADR-0112 (superseded as C-free evidence)

## Context

The question arrives as a performance question — how much slower is aiueos
than a Linux server, for code the amu native compiler produced? It has been
asked of the K16, of a Ryzen 5 6600HS, and of QEMU. Every form of it runs into
the same two walls.

**There is no time unit on this side.** ADR-0116 fixed that missing timing is
`N/A` and never zero, and that raw TSC cycles stay raw until a calibrated
monotonic frequency exists. ADR-0202's physical board reports TSC deltas
(800–1344 cycles for four micro-infer jobs) and says in the same breath that
they are a serialized TSC delta, not a wall time.

**And under TCG the clock is worse than absent — it is confident.** ADR-0165
measured four runs of one fixture at ratios 1.17, 1.45, 1.55, 1.57 and named
the spread as the load rather than the code, then concluded that the
defensible statement about speed is a COUNT.

## What was measured (2026-09-10)

Two things, both on this workstation, both reproducible by
`os/aiueos/scripts/smoke-qemu-target-parity-icount.cljk`.

**1. The two targets share an emitter, byte for byte.** The code image
`target-parity-core.kotoba` emits for `x86_64-linux` is 180 bytes; those exact
bytes appear at offset 93 of the object the same source emits for
`x86_64-aiueos-kernel-v1`, and its 127-byte compute body appears again at 4173
inside the bootable probe image. `kotoba.compiler.nbb.cli` already said this in
a comment ("nothing about code generation kept them off this route"); it is now
a measurement that a mutant fails.

The consequence is the useful part: `x86_64-linux` is `:abi :sysv` +
`:runtime :kototama-linux-supervisor-v1` and `x86_64-aiueos-kernel-v1` is
`:abi :aiueos-kernel-v1` + `:runtime :none`, and **the difference between them
is entirely at the boundary and nowhere in the loop.** An OS comparison here
cannot be a codegen comparison.

**2. `-icount shift=0,sleep=off` converts guest `rdtsc` from a host clock into
an instruction counter.** Three runs printed `000001EA000003AC` byte for byte.
Sizes 30 / 60 / 90 land on 490 / 940 / 1390 — a straight line at 15.0
instructions per iteration over a fixed 40. The same image booted without
icount printed `00003A98` then `000032C8`: a ~30% spread in which the
30-iteration fold reads HIGHER than the 60-iteration one, which is an ordering
a clock cannot have and a translator can. The probe's own check catches that
inversion and exits 51 rather than 33, so the noisy arm names itself.

This matters beyond aiueos. The workspace's benchmark ladder is refused for
host load routinely — amu-rank tick 358 refused at load1 21.18 on the morning
this was measured. **An icount count is immune to that**, because it is not
measuring time at all.

## Decision

1. Where a number is wanted from a QEMU guest, use `-icount shift=0,sleep=off`
   and report a COUNT. Do not convert it to ns, and do not compare it with
   silicon numbers from the codegen ladder — TCG prices a 256-bit vector
   operation at about what it prices a scalar one (ADR-0165), so anything
   about ILP, cache or branch prediction is invisible or inverted here.
2. Keep the two-size difference and the untimed warm-up. ADR-0165 measured
   that without a warm-up a 256-element fold reported 788,000 ticks against a
   4096-element fold's 279,000, because the first pass pays for QEMU to
   translate the sequence and that cost exceeds the loop.
3. The smoke proves its own containment check can go red on every run, by
   compiling a one-constant mutant and requiring the original bytes to be
   absent from it — and refuses (exit 3, neither 0 nor 1) if the mutation
   matched nothing, so that a red result cannot be red for the wrong reason.

## What this does not say — and one thing it said wrongly

**It does not compare aiueos with Ubuntu**, because the aiueos half has not
been measured. But the reason recorded here first was WRONG, and the correction
matters more than the original claim.

The first draft of this ADR said the aiueos side "does not exist to be
measured", citing the README's capability table (ring 3, syscall entry/exit and
the capability handle table are "reference-profile only") and ADR-0112 being
`superseded as C-free evidence`. **That was reading, not measuring, and it
conflated two different things.** ADR-0112 is superseded as *C-free* evidence;
that says nothing about whether the path RUNS. Measured 2026-09-10:

- `os/aiueos/kernel/entry.S` has `aiueos_syscall_entry`, a native x86-64 CPL3
  syscall path, and `main.c` emits `AIUEOS_PLC_RT_OK ... program=signed-cpl3-elf
  ... transport=syscall ... capabilities=16,17,18,19 ... timing=logical-unqualified`.
- `scripts/tasks.edn` carries `:plc-rt-qemu-smoke`, whose doc is "Boot the
  receipt-bound PLC ELF at CPL3".
- The PLC build compiles Structured Text to `x86_64-aiueos-user-v1` — the CPL3
  user target — and its generated program is full of `(cap-call 16 0)`.

So a CPL3 capability-call path exists, on the hybrid C kernel, and its own
marker already admits the one thing this ADR is about: `timing=logical-unqualified`.

**What actually blocked the measurement today was a stale dependency pin.**
`./os/aiueos/scripts/build-plc-native-program.sh` fails at
`--target x86_64-aiueos-user-v1` with `exit 70 :kotoba/internal-error`. That
target routes through nbb (`bin/amu`'s `nbbNativeTargets`), so it loads the
`.cljc` twin of `kotoba.native.elf64`, where a capability id arrives as a JS
bigint and meets a plain number. kotoba-native fixed it in `b88a11b`
(2026-09-10 10:35). **amu's `deps.edn` pins kotoba-native at `a5711bdc`
(2026-09-08 12:36), which does not contain it.**

Discriminated, same command, one variable:

    kotoba-native src shadowed by the local checkout  -> :ok true, 8560-byte ELF
    amu's pinned a5711bdc                             -> exit 70, internal error

That pin was stale **in the checkout**, not on amu's main. amu `origin/main` is
`Merge PR #923 from deps/kotoba-native-5f2717c2` — already the merge of the fix.
The shared checkout was one commit behind it. `checkout`, `pin` and `repo main`
being three different things is the third time in this one session that the
answer turned on that distinction.

### And with amu at origin/main, the aiueos side builds AND boots

    AIUEOS_PLC_NATIVE_BUILD_OK  :target :x86_64-aiueos-user-v1
                                :artifact-bytes 8560   (two passes, byte-identical)

    AIUEOS_PLC_RT_QEMU_OK scans=100 signed-elf tamper-rejected
                          fixed-priority-preemption native-provider
                          apic-release transactional-output safe-state

**So the claim this ADR made twice — that the aiueos side does not exist to be
measured — is false, and now measurably so.** aiueos runs a signed CPL3 ELF
making `cap-call 16/17/18/19` through `aiueos_syscall_entry`, 100 scans, in
QEMU. The first version of that claim blamed a missing kernel; the second
blamed a dependency pin; the truth is that the path runs and neither reason
held. What was wrong both times was the same thing: a documented limitation was
quoted instead of executed.

### What is genuinely left, and it is small

Only the counting. The scan count is a literal in `os/aiueos/kernel/main.c`
(`scans=100`) which `smoke-qemu-uefi.sh` greps for verbatim, and the smoke has
no `-icount` hook — it reads `AIUEOS_QEMU_TIMEOUT`, `_QUIET`, `_ATTEMPTS`,
`_DISPLAY` and nothing else. So a per-capability-call figure needs one of:

1. an `AIUEOS_QEMU_ICOUNT` passthrough in the smoke, which alone yields a
   deterministic TOTAL for the 100-scan run — the first reproducible number for
   this path, and the end of `timing=logical-unqualified`; or
2. two PLC programs differing only in their number of `cap-call`s, booted the
   same way, so the difference isolates the boundary the way every other
   measurement in this ADR does.

Neither is OS work. Both touch shared boot-evidence code, so neither is done
here.

### Route 1 was tried and is refuted (2026-09-10)

Before adding the icount passthrough, the instrument it implies was measured.
QEMU here has `-plugin` support but ships no plugins, so
`os/aiueos/scripts/qemu-insn-count-plugin.c` was written to count executed
guest instructions and print the total at exit. It works. It is also the wrong
instrument, by four orders of magnitude:

| | guest instructions |
|---|---|
| one unmodified image, run 1 | 1,532,182,814 |
| the SAME image, run 2 | 1,528,370,810 |
| run-to-run noise | **3,812,004** |
| two images differing by 30 loop iterations | 16,949,555 apart |
| the signal wanted (30 x 15) | **450** |

**`-icount` makes the guest CLOCK deterministic; it does not make OVMF's
device-polling loops spin the same number of times**, and the firmware is
~1.5e9 instructions of the total. The same session's in-guest bracket was
byte-identical across three runs (`000001EA000003AC`) precisely because it runs
after boot and touches no devices.

So route 1 is struck: an `AIUEOS_QEMU_ICOUNT` passthrough would produce a
number, and the number would be noise. **The boundary has to be bracketed
inside the guest** -- which means the counter must be read either side of the
`syscall` in the CPL3 path, and that is a change to `kernel/main.c` or to the
PLC program, not to a smoke's argument list. Route 2 survives, with the added
constraint that its two programs must be bracketed rather than merely
differenced across whole runs.

The plugin is kept, with its resolution limit written at the top of the file,
because it is the only instruction counter available here and it is right for
coarse whole-run questions. What it must not be used for is this one.

The smoke still prints `NOT-MEASURED` for the boundary, because it still has
not been measured — but nothing structural is in the way any more.

The precondition is an executable CPL3 path, so `x86_64-aiueos-user-v1` has a
kernel to run under. That target's packaging was still being repaired on the
day this was written: a `cap-call` source exited 70 with `:kotoba/internal-error`
under `package-user` while the same source compiled for wasm32, `x86_64-linux`,
`aarch64-macos` and both aiueos kernel targets.

Nothing here is a claim about the physical K16, about a Ryzen 5 6600HS (which
has no probe receipt in this workspace at all), or about real silicon. This
workstation is the QEMU host; QEMU is not P5.

## Evidence

    PARITY-CODEGEN linux-image=180 compute-body=127 core-object@93 probe-image@4173
    PARITY-DISCRIMINATES mutated-body@-1 (-1 required)
    IMAGE-FRESH artifacts=1
    ICOUNT-DETERMINISTIC runs=3 identical=true status=[33 33 33] console="000001EA000003ACIP"
    ICOUNT-COUNT small=490@30it large=940@60it per-iteration=15.00 fixed=40.00
    HOST-CLOCK-ARM status=51 console="00003A98000032C8IP" differs-from-icount=true
    NOT-MEASURED boundary-cost aiueos-capability-call vs linux-syscall
    SCANNED 6
    TARGET-PARITY-OK codegen-identical and count-deterministic

Both red directions were exercised while landing. Mutating the probe's compute
body to `(* i 5)` produced `probe-image@-1`, exit 1, and two independent
findings — the containment check and the guest's own arithmetic check — while
the instruction count stayed `000001EA000003AC`, because a different multiply
constant is the same instruction shape. The counter counts instructions; the
guest checks the values.

## The instrument is calibrated against silicon

An icount number is only useful if it means what a real machine would count.
It does. The same 127 bytes were executed on `gad` (Ubuntu 24.04.2, AMD RYZEN
AI MAX+ 395, load1 0.29-0.37 throughout) by `os/aiueos/scripts/perf-parity-body.c`,
which mmaps them RX and calls them with the artifact's own ABI
(`rdi`/`rsi`/`rdx`, `r9` = fuel context, counter at `[r9+8]`):

| instrument | per iteration |
|---|---|
| `objdump` of the 127 bytes, counted by hand | **15** |
| QEMU TCG under `-icount shift=0,sleep=off` | **15.00** |
| `perf stat -e instructions` on Zen5 silicon | **15.0041** |

Three instruments, one number. So an aiueos-side icount count and a Linux-side
perf count are the same unit, and the comparison this whole line of work is
for becomes legible the day the aiueos side has a boundary to measure.

Two further facts fall out of the disassembly. The self-recursion is compiled
to a LOOP -- the back edge is `jmp` at 0x63, not a call -- and **three of the
fifteen instructions are fuel accounting** (`cmp [r9+8],0` / `jne` / `dec
[r9+8]`; the `ud2` is not executed). That is 20% of this loop body, measured,
against the codegen ladder's standing "four fuel instructions per call" item
which it has never been able to price on a loaded host.

On silicon the loop also costs 2.0371 cycles per iteration (IPC 7.37). A ns
figure is deliberately not quoted: the two sizes imply different clocks
(3.96 GHz from the n=30 run's own cycles and task-clock), which is the Ryzen
boost-state variance the codegen ladder already reports as unmeetable for its
separation heuristic. Cycles and instructions are the defensible units here.

**The harness's answer check earned its place.** The first version declared
`rdx` a plain asm input, and the callee clobbers it (`lea rdx,[rbx+0x1]`), so
gcc believed `acc` survived the call and stopped reloading it: rep 0 returned
1305 and rep 1 returned 30, i.e. `limit`. `perf` reported this happily --
830,458 instructions for 30 iterations against 824,456 for 60, the larger loop
apparently cheaper. Only the value comparison caught it. A counter that is not
checked against an oracle will report the shape of a run that did not happen.

## The Linux half of the boundary is measured and banked

The comparison needs two numbers. One of them can be taken today, so it was,
rather than waiting and then measuring both on a machine whose state has
drifted. `os/aiueos/scripts/perf-linux-syscall-boundary.c`, on the same gad
(load1 0.36-0.55 throughout):

| arm | marginal instructions per iteration |
|---|---|
| `syscall(SYS_getpid)` in a loop | 353.47 |
| the identical loop, syscall replaced by a volatile read | 5.00 |
| **difference — the Linux syscall boundary** | **348.5** |

~184 cycles. The second arm exists because the two-size difference cancels
everything constant but NOT the loop's own bookkeeping, which scales 1:1 with
syscalls; subtracting a null arm measures that instead of estimating it. It
came out at exactly 5.00 instructions per iteration.

For scale, in the unit this ADR establishes: **one Linux syscall costs about
23 iterations of the amu compute loop.**

`SYS_getpid` is chosen so the kernel-side work is close to nothing and what
remains is the boundary. The mitigation state is part of the number and is
recorded rather than assumed: on this host every vulnerability file reads
`Not affected` except `spec_rstack_overflow: Mitigation: IBPB on VMEXIT only`.
A host with PTI or retpolines active would measure a different boundary, and
that difference would be the mitigations rather than the OS design.

**What is still missing is the aiueos half, and only the aiueos half.** See the
correction below: the CPL3 path exists and the blocker is amu's kotoba-native
pin, so this number is waiting on a pin advance rather than on OS work. Until
the other half is taken on the same box, this number sits here alone and is not
divided by anything.

## Two things that happened while landing, recorded rather than chased

**`CLJC contract tests` is red on main and was red before this branch.** Run
34435926740, on the base commit 12c4ba6 (Merge #332), has
`CLJC contract tests -> failure` with `EDN examples and docs` and
`aiueos UEFI bare-metal smoke` both green — the same shape this branch's run
shows. Documented here rather than fixed, so that the next reader does not
attribute it to the parity smoke; and stated explicitly because a PR that says
nothing about a red check reads as if it had none.

**This ADR was 0210 for about forty minutes.** ADR-0210 (`a stick that asks`)
landed on main from a parallel session while this was being written, and the
collision would have been SILENT: two files named `0210-*.md` are two different
paths, so git merges them without a word and the number stops identifying a
decision. Renumbered to 0211 after merging origin/main. The root AGENTS.md's
rule against bare `ADR-<number>` ids is the same failure seen from the id side.

## Not done

The smoke is not registered as a fleet gate. It needs a QEMU with OVMF and an
amu checkout on the node, and its inputs live under west-managed `orgs/`, which
the fleet tree does not carry. Registering it needs those two facts fixed
first, not a line in `gates.edn`.
