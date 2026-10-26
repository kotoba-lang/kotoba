# ADR 0205: boot is three jobs wearing one coat, and the layer that should hold them is missing

Status: accepted. Date: 2026-09-08. Extends: ADR-0204.
Owner question: *"そもそも boot と fuel という考え方は適切なのかな? 根本的な
アーキとして、どう os, boot と aiueos, kotoba, kototama を成立させると良い?"*

## Is "boot" the right notion? No — it is three unrelated jobs bundled into one

Every ~20 seconds the K16 does all three of these at once, and it does them
together only because there is nowhere else to put any of them:

| what actually happens | why it is bundled into boot | where it belongs |
|---|---|---|
| **the fuel budget is refreshed** | an image's budget is a lifetime cap; the only way to get another is a new image | per step, held by the caller (ADR-0204) |
| **new code arrives** | deploy = rebuild a 261,120-byte image, PXE-fetch it, reset | a new definition CID arriving; no reset |
| **all state is erased** | a new boot nonce, a fresh TCB, nothing remembered | state should survive a code change |

Reading that table is the whole argument. **The reboot is not a lifecycle
event; it is the only mechanism this machine has, doing three jobs.** Each of
the three has a proper home and none of them is "restart the CPU".

The third row is the one that is easiest to miss and hardest to live with. A
node whose identity is regenerated on every code change cannot hold a job, a
session, or a lease — and everything ADR-0202/0203 fought (the boot-nonce
binding, `ready?` flapping, jobs dispatched at a machine that is already gone)
is that row.

## Is "fuel" the right notion? Yes, but it is answering a different question

Fuel is a **step counter**: a proxy for time, for a guest you cannot preempt.
That is exactly right for WASM, for an object called from C, and for the KIR
oracle — none of which can be interrupted. It also has a property a timer never
has: **it is checkable before the machine runs**, which is what
`kotoba.compiler.fuel-estimate` and the admission gate are for.

The property actually wanted at run time is different: *no step may wedge the
machine*. On hardware with an interrupt controller the honest primitive for
that is **preemption**, not a counter.

And this workspace already has it, in Kotoba, in this repository:
`os/aiueos/native/rt-kernel.kotoba` — *"the hard real-time vertical slice. The
source owns the interrupt table, APIC setup, fixed-priority dispatcher,
periodic release... no C ABI or hosted runtime is present."* A Kotoba kernel
that owns the APIC and releases work periodically exists and is built by
`build-kotoba-rt-kernel.sh`. **The K16 stream kernel simply does not use it.**

So the answer is not to choose. It is to stop making one mechanism do both:

- **fuel = the compile-time bound.** Static, checkable, per step, and the thing
  admission refuses on. It never needs to be large, because it bounds a step.
- **the timer = the run-time bound.** It is what actually stops a step that
  overruns, and it can do what fuel cannot: end the step *without* ending the
  machine.

Today the K16 uses fuel as a run-time bound, and the outcome when it fires is a
halt that needs a person at the power button. That is the whole cost of not
having the second mechanism.

## The layer that is missing is kototama

The names line up cleanly once the question is asked:

| layer | owns | K16 today |
|---|---|---|
| **kotoba** | definitions, effect rows. No addresses, no budgets, no loop | present |
| **kototama** | the **tender**: the context (fuel word, grants, definition table), re-entry per step, the only thing that must be trusted | **absent on hardware** |
| **aiueos** | capability providers — MMIO, DMA, link frames, page tables. Supplies effects, never budgets | present |
| **firmware / boot** | bring the CPU to where the tender can run. Once | present, doing three jobs |

kototama's own maturity ladder is R0 contract → R1 JVM/Chicory → R2
browser-native. **There is no hardware tier.** On the K16 the kernel *is* the
artifact, packaged straight into a PE image, so there is no host holding the
context, no place to install a handler, and no place to swap a definition.

That absence explains every symptom without further hypotheses. The budget got
sealed into the image because nothing else could hold it. Deploy means reboot
because nothing else can receive code. State dies on deploy because the thing
that would have kept it is the thing being replaced.

## What "成立させる" looks like

**The image contains a tender, not a program.** It holds the context and a
definition table, and it re-enters the guest per step. It is small, it is not
Kotoba (the same reason `kexe_loader.c` and the object wrapper are not), and it
is the only trusted mechanism — which is the point: *a handler inside the
computation is not a handler* (ADR-0204).

**The guest is content-addressed definitions with effect rows.** Unison's real
lesson is not only abilities: it is that code has no version and no rebuild,
only hashes and names. A node running a definition CID does not need a new
image to run a different one — it needs the definition and a name to move.
`amu` already emits definition CIDs and `:kotoba.output-set/v1`; the Execution
IR already carries `{program, input, state, runtime, policy, effects}`.

**A step is `state + event -> state' + effects`** — the shape ADR-2607201300
already prescribes for `kotoba/app`, bounded by fuel at compile time and by the
timer at run time.

**Deploy stops being a reset.** A definition arrives over the wire and the
tender moves a name. LAN2 already carries commands and already answers them;
this is that channel doing the job it was shaped for. Reset survives for what
only firmware can change.

## Step 1 is landed: the image entry is a host loop

`kotoba.compiler.packaging.pe32plus/k16-preflight-tokens` now emits, in the
`--k16-preflight` image only:

```
        movabs r9, 0x128000        ; the guest's context
        mov    rax, [r9+8]         ; the budget the COMPILER sealed
        mov    [rip+tender-fuel], rax
tender_step:
        lea    rdi, [rip+boot-info]
        movabs r9, 0x128000
        mov    [r9+0x50], rdi
        mov    rax, [rip+tender-fuel]
        mov    [r9+8], rax         ; replenish
        movabs rax, returnable-entry
        call   rax
        mov    r15, rax
        cmp    r15, 250            ; "that was one step; call me again"
        je     tender_step
```

**The loader does not know the number.** It reads the word the compiler wrote
and writes that word back. This is not a stylistic choice; it removes two
whole failure modes. The loader cannot disagree with the artifact — that word
is the same one `elf64/artifact-fuel` checked `:limits :fuel` and `:fuel-abi
:initial` against, so it *is* the receipt. And there is no immediate to
overflow.

The first version of this did use an immediate: `mov qword [r9+8], imm32`,
with a guard refusing any budget at or above 2^31 because the field is
sign-extended. That guard was correct and the design was wrong. ADR-0203
raised `ir/max-fuel` to 2^53-1 specifically so the bound would stop being a
knob; a tender whose ceiling is the width of one instruction field puts the
knob straight back, one layer lower, where nobody would look for it. **Do not
re-introduce the immediate form.**

The snapshot is deliberately *outside* the loop and the replenish inside: the
budget is read once, before the guest has had an opportunity to touch
anything. `rdi` and `r9` are re-materialised every iteration because both are
caller-saved and the guest may clobber them.

`250` (`FA`) is the sentinel because the panel renders the low byte of this
same register as STATUS. A sentinel colliding with an ordinary return would
make a running node and a finished one print the same two characters.

### What was measured, 2026-09-08

| control | result |
|---|---|
| non-preflight image, unmodified compiler vs modified | **byte-identical**, `b3cc1297...` both — the change is scoped to `--k16-preflight` |
| preflight image byte scan | exactly one snapshot (context `0x128000`), one replenish, one `cmp r15,250 / je` |
| `je` target vs loop head | target `0x384`; snapshot begins `0x36f` and is 21 bytes, ending `0x384`. The branch lands on the instruction after the snapshot, which is the loop head |
| sealed word in `KERNEL.ELF` at `0x128000+8` | `1073741824` = 2^30, equal to the kernel verifier's `fuel=1073741824` |
| QEMU, preflight image `20728546...` (261,120 bytes) | exit 33, debugcon exactly `MPRCD` |

The 16-byte slot the tender saves into is at the **tail** of `.data`, after
every message, so boot-info, the memory map and all four messages keep the
offsets they had. A preflight image with the tender differs from one without
it in `.text` and in those 16 bytes, and nowhere else.

### What this does NOT show

**The loop has never been taken, and nothing here shows that it can be.** Two
independent reasons, both by construction:

- Under QEMU there is no RTL8125, so the preflight path branches to
  `:exit-boot` on the PCI ID mismatch *before* reaching the tender. The QEMU
  pass says the image is still structurally sound and boots identically. It
  says nothing about the loop.
- On the board the tender *is* reached, but the guest's `main` does not
  return at all — it runs `debug-run-cycles` and then resets. Zero iterations
  complete.

So the honest claim is exactly the one step 1 was for: **the mechanism is
present, and behaviour is unchanged because nothing yet returns the
sentinel.** A control that takes the branch is not available until step 2
makes the guest return per step. Until then, do not report that the tender
runs.

### The hardware measurement is pending, and why

The tender image (`36d81484...`, 261,120 bytes, compiler `a6102cda`) was
written to the PXE root at 16:42 JST and **has not been fetched.** The board
stopped speaking at `2026-09-08T07:02:39Z` (16:02 JST), 40 minutes before that
deploy, after fetching and booting the previous image (`0576a52e`): it sent one
`AIUEOS_NODE_HELLO_V1`, reached `state=live-not-ready enrollment-status=200
heartbeat-status=201`, and then went silent.

It is wedged, not off. Both host links report `status: active`,
`1000baseT <full-duplex>`, and both board MACs are still in the ARP cache; what
is absent is DHCP, netlog, bus3 and ICMP. A powered-down mini-PC would drop
link. This is the same failure ADR-0203 recorded once before and could not
attribute — it needed two power cycles then, and needs a person now.

So: **the tender is proven in the image and unproven on the machine.** Do not
close step 1 as measured-on-hardware until a boot of `36d81484...` appears in
the server log. Nothing here attributes the wedge to the tender — that image
has never run — and nothing here attributes it to `0576a52e` either; one boot
followed by silence is not yet a cause.

### On hardware, 2026-09-08 evening: the tender runs, and the reset is the wound

The tender image booted and the node came up:

```
AIUEOS_PXE_TFTP_OK bytes=261120
AIUEOS_NODE_HELLO_V1 boot=...
AIUEOS_MURAKUMO_RELAY state=live-not-ready enrollment-status=200 heartbeat-status=201
```

Behaviour is unchanged with the mechanism present, which is what step 1 asked.
Every boot since enrolls `200`/`201` with the node's own did:key.

What that exposed is a separate defect that had been eating the rig all day:
**the board stops at the platform reset.** The end-of-run path is

```
DE DE DE                 three fire-and-forget DMA transmits
(kernel-out-u8 3321 6)   0xCF9 <- 0x06 = SYS_RST|RST_CPU
223                      -> loader prints STATUS DF
```

Three facts bracket the failure to one instruction: `DE DE DE` reached the
wire, so the transmits were submitted; the panel showed `RTL8125` and **no
`STATUS`**, so `main` never returned, and the only statement between the last
DE and that return is the 0xCF9 write; and the panel text was still on screen,
so no POST happened and therefore no reset happened either.

`0x06` is a WARM reset and does not reset PCIe devices. Three transmits had
just been handed to the RTL8125, so the NIC is still bus-mastering when the CPU
is reset. It behaves like the race it is: DE-three-times landed at 15:10 and
the 19.7 s cadence ran until 15:43 before stopping for good.

The fix drains the last transmit descriptor's Own bit
(`wait-tx-complete-stream`, which already existed) before the write, with a D7
receipt emitted BEFORE the drain -- `stream-log` is itself a DMA submit, so a
receipt after the drain would re-arm what was just drained.

| image | self-resets observed |
|---|---|
| 1024 cycles | **0** across 3 power cycles |
| 64 cycles | 1 |
| 64 cycles + drain | **2** (21 s and 158 s apart), 3 boots, all enrolled |

Better, and not yet the steady 19.7 s cadence. After the last run the board
sent **no DHCP at all**, so it stops on its own rather than because the server
failed to answer.

### Two things measured today that were wrong when first claimed

**`AIUEOS_PXE_TFTP_FAIL stage=oack` is not a fault.** This firmware fetches in
two phases: an RRQ carrying `tsize` to learn the size, then a second RRQ
without it for the transfer. It abandons the probe TID with a TFTP ERROR
(`opcode-0005`) once it has the size, so **one benign FAIL per boot is normal**.
A reading of "50 OK / 61 FAIL" as a 45% success rate, and the load-starvation
hypothesis built on it, were both wrong. The diagnostic added that day is what
disproved them.

**Marker counts per boot are not evidence of where a run ended.** The netlog is
fire-and-forget UDP and ADR-0203 already recorded that only 216 of 259 runs
carried a DE *while the board kept rebooting throughout*. Separately, an
analysis that segments boots on time gaps misattributes markers across
boundaries, because lines without a timestamp inherit the previous one. The
non-lossy witness for "did the run end" is the PXE server's fetch log, and
nothing else.

### QEMU can reach the tender now, and the first thing it found was unfinished

2026-09-09. The preflight image branched to `:exit-boot` on the missing
RTL8125, so the emulator ran the ordinary halting entry and the tender was
never exercised there. `exit 33 / MPRCD` had been green for a week of runs in
which the changed code was not reached -- a control for absence. Four defects
found on hardware that week were pure control flow with no packet in them.

The branch now skips only the RTL8125 banner, and the loader marks its stages
on port 0xE9 (free on hardware, which ignores the port; and it is the only
channel the LOADER has, since the netlog belongs to the guest's NIC and the
ConOut panel only prints when `main` returns). The smoke asserts `PSTC` as a
prefix and `MPRCD` as a substring, verified red with a wrong prefix.

It earned itself on the first run: `PTC`, and the marker that was MISSING named
the defect -- the branch target sat below the snapshot, so `tender-fuel` was
never written and the guest was called with a zero budget.

### The open question, stated so the next attempt starts ahead of this one

**Making the guest return 250 under QEMU does not produce a second entry, and
does produce exit 63.**

What is eliminated, by measurement rather than reasoning:

- **The markers are in the image.** A byte scan for
  `mov dx,0xE9; mov al,c; out dx,al` finds exactly one site each for
  P, S, T, C, N, X and the loader's fail `F`. So a missing letter means the
  path was not taken, not that the instrument is absent.
- **`X` has never appeared, in any configuration.** X sits immediately after
  the tender's `call`, so on this evidence the guest has never returned through
  that call site here -- including the runs where it returns 250 rather than
  writing 0xF4.
- **Exit 63 appears only when the guest is made to return 250.** 63 is
  isa-debug-exit's `(31 << 1) | 1`, and 31 is `prepare-owned-pages`' code for
  `zero-page pml4` failing -- zeroing the page tables the machine is running
  on. Guarding that with the CR3 test did NOT change the exit, and a marker on
  the decision itself printed once and never a second time.

So something writes 31 without the tender re-entering, and the two facts do not
yet fit together. Three guesses were made and spent here (the NIC, the
page-fault probe, the ownership block); each produced a defensible guard and
none was the cause. The next attempt should place a marker immediately before
every `kernel-out-u32 244` site rather than reason about which one fires --
there are nine, and one run would name it.

### Narrowed 2026-09-09: the guest returns, and the return does not arrive

Marking all nine `kernel-out-u32 244` exits in `kernel.kotoba` with distinct
digits and running once eliminated every one of them: **no digit appeared, and
QEMU still exited 63.** So the 31 that produces that exit is not written by any
of the guest's exit paths, which is three more guesses retired than reasoning
would have retired in a day.

What the same run DID show:

```
PSTCMPRCD R F   ->  exit 63
          ^ R: the guest reached its hand-back and returned 250
            ^ X never appears, in any configuration tried
```

`X` is the byte immediately after `call rax; mov r15, rax` in the tender. If
the guest returns, X prints. **R fires and X does not**, so what is lost is not
the value -- the guest computed and returned it -- but the RETURN ITSELF.
Control never reaches the instruction after the call.

That has an obvious candidate and it explains the hardware/QEMU split. The
guest installs its own page tables and loads CR3 before it gets anywhere near
returning; from that instant the loader's code, its stack and the return
address on it are only reachable if the guest's map happens to cover them. On
the K16 it evidently does -- 17 re-entries were measured from one image load.
Under QEMU, UEFI puts the loader somewhere the guest's map does not reach, and
the `ret` goes nowhere.

**The mechanism, found in the guest's own comment.** `fill-identity-pd` writes
its PDEs through `store64-nx-page`, which sets byte 7 of each entry to 128 --
the NX bit -- and the line above it says so plainly:

> PDE 0 points to a 4 KiB PT. The remaining 2 MiB leaves preserve the first
> GiB identity map but are RW+NX rather than executable.

So from the instant the guest loads CR3, **everything in the first GiB except
the low 2 MiB is non-executable**. The loader's code is wherever UEFI put it.
Under OVMF in QEMU that is above 2 MiB, so the guest's `ret` becomes an
instruction fetch on an NX page and dies there. That is why `X` has never
appeared.

On the K16 the same map is installed and the return works, seventeen times from
one image load -- which means the board's firmware happens to place the loader
inside the low 2 MiB that PDE 0 maps at 4 KiB granularity. **The tender has been
working there by luck**, and the luck is a property of one firmware's
allocator.

**Do not "fix" this by having the guest avoid returning.** The tender's whole
contract is that the guest hands the step back, and it demonstrably works on
the board. What is missing is that the guest's page tables must map the caller
it intends to return to -- a real requirement of the tender design that nobody
had written down, and which the hardware satisfied by luck rather than by
construction.

The fix has a shape: the loader knows its own base and size and already writes
boot-info, so it can name its executable range there, and the guest can map
that range RX instead of inheriting the blanket NX. That keeps W^X -- the point
is not to weaken the map but to stop it from unmapping the one caller the guest
has promised to return to. Widening boot-info is the honest cost; nothing else
in the guest knows where the loader is.

### Confirmed 2026-09-09: the return works before CR3, and not after

Publishing an address the loader executes from -- `lea rax,[rip+0]` -- widened
the loader's variable block by 16 bytes, which moved the memory map, which the
guest rejects because it hardcodes the map at boot-info offset 96. So the guest
failed its own validation early, returned 18, and QEMU exited 37.

**And `X` printed.** `PSTCX`: the guest was called, it returned, and control
reached the instruction after the call. That is the first time X has ever
appeared, and it appeared on the one run where the guest returned WITHOUT
having installed its page tables.

That closes the question. The return path is sound; what breaks it is the
guest's own map. Before CR3 the loader is executable and the `ret` lands;
after CR3 it is NX above the low 2 MiB and the `ret` faults. The tender's
contract needs the guest to keep its caller executable, and nothing in the
guest currently knows where that caller is.

Two things the next attempt must carry, both learned by breaking them:

- **The guest hardcodes the memory map at boot-info offset 96**
  (`kernel-subregion boot 16480 96 16384`). Growing the loader's variable block
  moves the map and the guest rejects the whole boot-info. Either the new field
  goes after the map, or the offset and the version move together.
- **A base is not what to publish.** `data-address` is not in scope where the
  preflight tokens are built -- it depends on the token stream's own length --
  and the guest clears NX at 2 MiB granularity anyway, so an address inside the
  loader's text is both sufficient and the only thing cheaply available.

## Order, and what not to do

1. ~~**The image entry becomes a host loop**~~ — **landed 2026-09-08**, see
   above. It is the minimal tender: replenish, call, re-enter.
2. ~~**The guest returns per step**~~ -- **on main 2026-09-08, and NOT YET
   MEASURED ON HARDWARE.** `stream-resident`'s end of run no longer writes
   0xCF9; it drains the last transmit and returns 250, and the tender
   replenishes and re-enters. QEMU passes (exit 33, `MPRCD`); the board was
   stopped when this landed and has not run it.

   ⚠ It reached main by accident. It was committed to the branch with "branch
   only, not merged" in its own message, and a later branch->main merge for an
   unrelated fix carried it along, because merging a branch merges everything
   on it. Nothing is being reverted -- the reset path it replaces is the one
   that demonstrably halts the board, and main is not deployed automatically --
   but "unmeasured" is a property of the change, not of which ref it sits on,
   and the merge message that says "on the branch" is wrong.

   The cost is explicit: **a deploy no longer takes effect by itself**, because
   the board stops re-fetching. `k16-control.cljs R --to 10.10.10.2:9000` still
   resets at the one remaining 0xCF9 site.

### Step 2 ran on hardware, and named its own next step

Measured 2026-09-08, 21:40 and 21:52. `B7` is the boot-census byte `main`
emits, so counting it counts entries into `main`:

```
21:40:48.320                 one PXE fetch
21:40:49.053   +0.73s        the tender re-entered
21:52:05.700                 one PXE fetch
21:52:05.756   +0.06s        the tender re-entered, and died in 60 ms
```

**The tender loop is taken.** The run completes, emits DE three times and D7,
drains the last transmit, returns 250, and the image replenishes the sealed
budget and calls `main` again -- with no platform reset anywhere. That is the
mechanism ADR-0204 asked for, running.

**And the second entry dies immediately, both times.** The first runs its full
~0.7 s, 64 cycles; the second lasts 60 ms.

That is the answer to a question this ADR deferred when step 2 was scoped. The
note then said the one design judgement was "where the boot-once flag goes",
and the implementation chose the other option -- let `main` re-run its whole
init on every re-entry, on the reasoning that a re-entry is no worse than a
reboot minus the firmware. The measurement says otherwise: re-activating page
tables, re-installing the IDT and re-initialising a NIC that is already live
kills the machine in 60 ms. **A re-entry is not a reboot; the machine it starts
on is not the machine a reboot starts on.**

So step 2 is half landed. The tender re-enters, which was the hard part and is
now proven; what is missing is the flag that makes the second entry a STEP
rather than a second boot. It has to live somewhere that survives across
entries and that only the guest writes -- the guest's own RW segment does, and
its address is stable because boot-info is re-installed identically each
iteration.

### The watchdog will not help here, and the board said why

`D4` nine times, `D6` and `D2` never: **the LPC bridge at 00:1f.0 is not
Intel.** The TCO timer is an Intel PCH mechanism, so there is nothing on this
board for that code to arm, and no software change to this file will produce
one. Splitting D4 into three reasons the tick before is what turned "the
watchdog refused" into a finished line of enquiry rather than an open one.

This matters for the order of work: a watchdog would have papered over a run
that dies, letting the board recover in ten seconds instead of waiting for a
person. It is not available, so the dying run has to be fixed rather than
survived -- and step 2's boot-once flag is the fix, not a workaround.

3. **The tender gains a definition table**, so "which code runs" is a name, not
   an image.
4. **The timer becomes the run-time bound**, borrowing `rt-kernel.kotoba`'s
   APIC and periodic release rather than writing a second one.
5. **Definitions arrive over LAN2.** Deploy without reset.

Not to do, each for a reason already recorded here:

- **Do not let the guest replenish its own fuel** (ADR-0204). It would work.
- **Do not build a second runtime.** kototama exists; what is missing is a
  hardware tier of it, not a new thing beside it.
- **Do not add a second store for artifacts.** The five canonical IRs share one
  physical plane by decision (ADR-2608160200).
- **Do not treat the reboot loop as the design.** It was a way to iterate
  deploys without a button, and it worked; it is not how a node lives.

## What this does not settle

Whether the tender should be emitted by the packager (as the object wrapper is)
or be a distinct artifact the loader hands control to. Both keep the handler
outside the computation, which is the property that matters; the choice is
about who owns the bytes, and it should be made with kototama rather than for
it.

## The tender's return path, closed 2026-09-09

The tender re-enters the loader after the guest returns 250, and in QEMU the
loader never ran again: the guest returned (`R`) and the loader's own `T`/`X`
never printed. The cause was the guest's NX identity map covering the page the
loader would resume on. Fixing it needed the loader's text address, which only
UEFI knows, so the loader publishes it and the guest clears NX on the covering
PDE.

Publishing it was easy; **reading it took four runs, and each one was worth
more than the fix.** The slot first went after the 16 KiB memory map, growing
boot-info to 16480 bytes, and a copy of the accessor bounded at 16480 hung.

What the four runs established, one claim each:

| Run | Change | Trace | What it acquitted |
|---|---|---|---|
| 1 | marker before/after the read | `PSTCMa` | — the read does not return |
| 2 | marker in an `if` condition, not `(* 0 marker)` | `PSTCMa` | constant folding |
| 3 | same read at declared offset 0 | `PSTCMa` | the offset |
| 4 | marker on function entry | `PSTCMad` | the call |

Run 2 is the one to keep. The first marker was placed in a `(* 0 marker)`
addend, the sequencing idiom this codebase uses everywhere, and a foldable zero
multiply means **"the read hung" and "the compiler dropped the marker" print
exactly the same thing — nothing.** The conclusion from run 1 was right, but it
was not yet evidence; run 2 is what made it evidence.

What remained was the declared bound, and the emitter says why:
`kernel-load-u8` carries a profile maximum of 512 bytes, and
`emit-kernel-load-u8` compares the declared length against it and falls through
to **UD2** (`kotoba/native/x86_64.cljc`). A too-wide bound does not read wide.
It executes an undefined instruction, and at that point in boot the guest has
no `#UD` gate installed, so the firmware's handler takes it and dead-loops —
which is why it looked like a hang and not a fault. `-4k` and `-16k` variants
exist at 4096 and 16384; 16480 exceeds all three.

So narrow first and read second. The slot moved into the **last 16 bytes of the
map window**, and the read goes through `kernel-subregion` and
`kernel-load-u8-16k`, whose maximum is exactly that window. boot-info does not
grow, no ABI offset moves, and no bound wider than an op's profile is declared
anywhere. The guest's map bound drops 16384 -> 16368 so that a map reaching the
slot is refused rather than read back with an overwritten tail.

QEMU marker is now `PSTCMPRCDX`, exit 0. **`X` is the loader running after the
guest returned** — by construction rather than by luck, which is what ADR-0204
asked for and what the hardware run of 17 re-entries could not by itself prove.

The general lesson is not about this bound. It is that **a bounds check that
traps is indistinguishable from a hang unless something downstream is listening
for the trap.** The guest installs a `#UD` gate; this code runs before it. Any
guest code that runs before its own fault gates should be read with that in
mind.

## The one-in-five abort was an interrupt, not a mystery (2026-09-09)

About one QEMU run in five stopped with the trace cut short after `M` and
exit 0. It had been carried as a standing symptom, alongside "exit 63", for
long enough that single green runs were being read as evidence.

`-d int,cpu_reset` named it in one captured run. A healthy run logs 157
events, every one an APIC timer tick. The aborted run logs **97,886**: the
first 149 are the same timer, the 150th is a `#PF`, and the remainder are
that `#PF` re-entering itself with SP falling 0x30 each time until `#DF`
and `Triple fault`. Error code is `0x11` throughout — present, instruction
fetch — and `CR2` equals `RIP`.

Tick 149 is the only one whose IP is in guest text (`0x125058`) rather than
firmware. That is the tick that arrived after the CR3 switch.

Between the CR3 load and `install-page-fault-idt`, the firmware's IDT is
still live and every one of its handlers sits above 2 MiB, which
`fill-identity-pd` has just made NX. An interrupt in that window vectors
into a page that cannot be fetched; the `#PF` handler is equally
unfetchable. The fix is one call: `kernel-cli` before
`activate-page-tables`. It existed in the guest grammar and was never used.

Ten runs after: no aborts, all ten reached the full marker.

**The guest already depended on not being interrupted. It just had no way
to say so** — which is why this read as a coin flip rather than as a bug.

## The trailing byte is a race, and so is the exit code (2026-09-09)

`exit 63` and the wandering last byte (`MPRCD` / `MPRCDF` / `MPRCDX` /
`MPRCDXZ`) are one thing: **the guest writes the debug-exit port and then
keeps running.** The exit code is fixed at that write; everything printed
afterwards is a race against QEMU tearing down, and how much escapes varies
with `-smp` (a diagnostic byte on the tender fall-through appeared in 3 of
4 runs at `-smp 1` and in 0 of 3 at `-smp 2`).

How this was pinned down matters more than the conclusion. After `X`,
neither successor of the tender compare fired: no second `T` from the
loop-back, no marker from the fall-through. Both were instrumented, so
"neither branch ran" was a measurement, not an inference — and the `je`
was verified statically to resolve to the `T` byte at `0x3a7`, so a
mis-encoded displacement was excluded without a run.

Consequences for the gate: the marker's **prefix and required substrings
are trustworthy; its tail is not**, which is why `X` is asserted as a
substring. The exit code is trustworthy only as the value the guest chose
to write. `exit 63` therefore reports a guest status of 31 from a write
site that the 16/17 ladder does not explain — still open, and now a
specific question rather than a symptom.

On hardware none of this applies: there is no `isa-debug-exit`, the guest
simply returns, and the tender takes it.

## exit 63 has exactly one possible source (2026-09-09) -- WRONG, see below

Reading the code rather than running it: **31 is producible at exactly one
point in this kernel** -- the branch of `zero-five-status` taken when
`(zero-page pml4 0)` does not return 1. It reaches the debug-exit port as
`owned-status`, through `prepare-owned-pages` and the status ladder. Every
other status producer has a disjoint range (25-28, 30, 32-39, 40-44, 73-78,
79-84), and the healthy terminal writes 16 or 17.

So `exit 63` means one thing: **zeroing the PML4 page did not succeed.**

Both that branch and the ladder now emit a byte -- `p` and `l` -- BEFORE
the port write. Before matters: the guest keeps running after it writes the
port, so anything printed after a write is a race, and anything printed
before one is not. Both sites are failure paths, so a healthy run prints
neither.

Ten runs with the labels in place: all exit 33, identical traces, neither
label fired. **That is not evidence the fault is gone.** At the 2-in-10
rate previously observed, a clean run of ten has about an 11% probability,
and machine load was 101 during these runs against 37 during the batch that
produced two -- so load does not explain the difference either. The honest
state is that exit 63 has a name and a label waiting for it, and has not
been seen since.

What changed is the cost of the next occurrence. Before, a numeric exit code
had to be matched back to one of nine `kernel-out-u32 244` call sites by
hand, with a trailing marker that could not be trusted. Now the run says so
itself.

## Retraction: that source is dead code, and the code is full of dead checks

The section above is wrong in both of its steps, and the way it is wrong is
worth more than the conclusion was.

**The branch cannot execute.** `zero-page` returns 1 and nothing else:

    (let [stored (kernel-store-u8-4k page 4096 offset 0)]
      (if (= 0 (* 0 stored))        ; true for every value of `stored`
        (zero-page page (+ offset 1))
        0))

`(* 0 stored)` is 0 whatever the store returns, so the failure arm is
unreachable. Every status that depends on it is therefore unreachable too:
**30-34** in `zero-five-status`, **25-27** in `prepare-extra-pages`, and
**79-84** in `prepare-nic-pages`. Fourteen status codes that no run can
produce, several of them quoted in receipts as though they were outcomes.

Nor could the check work as written. `kernel-store-u8-4k` returns its
operand, so there is no failure value to test, and an out-of-range offset
does not return at all -- the emitter falls through to UD2, the same
mechanism that produced the earlier boot-info hang. The real check is the
readback beside it (35-39), which loads a byte and compares it.

**And the arithmetic was wrong.** `exit()` truncates to 8 bits, so
`exit 63` does not mean the guest wrote 31. It means the guest wrote a
value congruent to 31 mod 128 -- 31, 159, 287. `(+ 96 pre-cr3-nic-status)`
with `qualify-rtl8125` returning -1..3 gives 95..99, i.e. exits 191..199,
so that site is excluded on the corrected arithmetic and not on the old one.

What is now established about the terminator, by removing the device rather
than reasoning about it: with `isa-debug-exit` gone the run reaches 124 and
prints `PSTCMPRCDXF`, so the guest's port write **is** what ends QEMU, and
the natural trace is longer than the one the gate normally sees.

The tail still cannot order events: at `-smp 1` it ends `X Z` (both loader
bytes) and at `-smp 2` it ends `X F` (loader then guest). Bytes from
different CPUs interleave there. Only the prefix is evidence -- which is why
the gate asserts a prefix and required substrings and never a suffix.

The dead branches are marked in place rather than deleted, because removing
them renumbers a vocabulary that receipts already quote. **The label put on
the 31 branch yesterday has been removed**: a marker on unreachable code is
the same defect it was meant to diagnose, and would have had the next reader
waiting for a byte that cannot arrive.

exit 63 is unattributed again, and that is the accurate state.

## exit 63 is an interrupt receipt, and `F` means three different things

Found by reading, after the retraction above ruled out every status the
guest can write. It was never a guest status. `kotoba-native`'s
`interrupt_abi.cljc`:

    ;; 'F' on the debugcon port, 0x1f on isa-debug-exit.
    (def fail-closed-receipt
      [[0xb0 0x46 0x66 0xba 0xe9 0x00 0xee]
       [0xb8 0x1f 0x00 0x00 0x00 0x66 0xba 0xf4 0x00 0xef]])

`0x1f` is 31, and `(31 << 1) | 1` is 63. **`F` and exit 63 are one event** --
the fail arm of the two interrupt handlers that can return, the recoverable
`#PF` and the timer. Not a marker plus a separate symptom, which is how the
pair had been carried.

That it took this long has a specific cause: **three unrelated things emit
`F` on this port.** The guest's nic marker (`serial/trace-byte 70`), the
loader's `:fail` arm (`0xb0 0x46`), and this receipt. The smoke's own comment
asserted the trailing `F` was the guest's nic marker, so every trace ending
in `F` was read as a healthy run with a nic detail, and the accompanying
exit 63 as an unexplained status needing a search through nine call sites.
Two of those days were spent inside that search.

The guest's marker is now **`Q`**. The collision is removed where this repo
owns the byte; `F` on this port now means a fail-closed receipt in both of
its remaining senses, which is coherent.

This also explains why exit 63 became rare exactly when it did. It is an
interrupt-handler failure, and the previous iteration masked interrupts
across the CR3 switch. The same window, the same cause: **the abort and
exit 63 were two faces of interrupts arriving where nothing could service
them.** One triple-faulted because the firmware IDT was still live; the
other reached a Kotoba handler that closed fail. Neither was a coin flip.

Method note, because it generalises. Every step that moved this forward was
a static one -- reading the emitter for the profile maximum, computing which
values can reach the port, enumerating status ranges, grepping for the port
constant. The runs only ever confirmed. The two conclusions that had to be
retracted were both produced by reasoning from a trace.

## exit 63 is the triple fault, caught -- and it predicts a hardware failure

Two logs from the batch after the interrupt mask landed, kept on disk and
re-read rather than re-run. Both exit-63 runs carry exactly one page fault
and it is the last event before exit:

    v=0e e=0011 cpl=0 IP=0038:0000000006af1cee CR2=0000000006af1cee

Identical in both. `e=0011` is present + instruction fetch and `CR2` equals
`RIP` -- the same signature as the triple fault documented above, at a
different firmware address. The seven runs that exited 33 have no page fault
at all.

So **exit 63 and the triple fault are one bug at two stages of treatment.**
Before the mask, an interrupt reached the still-live firmware IDT and there
was no handler that could be fetched, so it tripled. After it, the fault
reaches the guest's own recoverable `#PF` handler, which requires
`CR2 == 0x100000`, sees a firmware address, and fails closed. The mask did
not remove the cause; it converted an unrecoverable machine reset into a
receipt. That is what fail-closed is for, and it is also why the symptom
looked new.

The trace says when: `...D X F`. `X` is the loader resuming after the guest
returned, so the fault happens **after** control is back in the loader --
and the loader's fall-through calls UEFI ConOut to keep the status string on
the panel. ConOut is firmware text, above 2 MiB, and `fill-identity-pd` has
made everything up there NX. `allow-loader-exec` un-NXes the loader's own
page and nothing else, so the loader can run but cannot call the firmware
that loaded it.

**This is not a QEMU artifact.** On the K16 there is no `isa-debug-exit`, so
the same fault ends in the fail-closed halt instead of an exit code -- a
board that stops with `F` and no further output, which is what "the board is
dead again" has looked like. The status string that path exists to print is
the one thing it cannot print.

Three candidate fixes, none applied yet: the loader saves UEFI's CR3 before
calling the guest and restores it before touching firmware; or the guest is
told the firmware text range as it is told the loader's; or the fall-through
stops calling firmware and reports through a port it already owns. The first
is the smallest and is the one that matches the tender's existing shape --
it already re-materialises rdi and r9 every iteration for the same reason.

Still unexplained, and stated as such: runs that exit 33 print `X`, which
means the loader resumed, yet the only writer of 16 is the guest before it
returns. One of those two readings is wrong and I have not established which.

## The ConOut attribution, falsified and then confirmed (2026-09-09)

The section above named the loader's ConOut call as the fault. That was a
hypothesis from a trace, and the previous two of those had to be retracted,
so it was tested before being believed.

**First control: it looked wrong.** A build with the CR3 restore removed and
a marker `O` before the call reached `O` twice in six runs and exited 33 both
times, with no `F`. Read straight, that acquits the call.

**It was the control that was wrong.** `O` says the path was entered. It does
not say the path was left. Adding `K` after the call settled it in one build:

    without the restore   ...X O F   exit 63, twice; K never appears
    with the restore      ...X O K   exit 33, no F in fourteen runs

The call does not return. The instruction fetch faults, reaches the guest's
recoverable `#PF` handler, fails its `CR2 == 0x100000` test, and closes fail
-- the `F` receipt and the `0x1f` it writes, which is exit 63.

The fix is in `amu`: snapshot UEFI's CR3 beside the loader text address and
reload it before the status path touches firmware. Both halves live in the
16-byte slot inside the map window, so nothing about the boot-info ABI moves.

**Both markers stay.** The first control was not merely inconclusive, it
pointed the wrong way, and it did so because it could see a path being
entered and not whether it was left. A marker before a call and a marker
after it are two different measurements; only the pair can distinguish
"never went there" from "went there and never came back".

On the K16 there is no `isa-debug-exit`, so this same fault has been ending
in the fail-closed halt -- a board that stops after `F` with nothing further.
That is what "the board is dead again" has looked like, and the status string
this path exists to print is the one thing it could not print. Unverified on
hardware: the board is not powered, and this is stated as a prediction.

## The tail race has a mechanism: isa-debug-exit does not stop the vCPU

The last thing left unexplained -- runs that exit 33 yet print `X`, the
loader's post-return marker, when the only writer of 16 is the guest before
it returns -- is closed, and it was not a contradiction.

Two measurements, neither of them a trace reading:

**The guest's write is the terminator.** Changing its terminal value from 16
to 21 changed the exit from 33 to 43, three runs for three. Nothing else in
either tree writes a value congruent to 21 mod 128.

**And execution continues past it.** A byte `W` placed immediately before
that write gives, three runs for three:

    P S T C M P R C D W X O K      exit 43

`W` is the last instruction before the `out`, and `X`, `O` and `K` are all
loader bytes emitted after the guest returns. So the exit code is fixed at
the write while the vCPU carries on: the guest returns, the loader runs its
entire post-return path, and the process tears down a moment later with the
code already decided.

That is the mechanism behind the tail race this ADR has been describing as a
symptom since the start. **How far execution gets after the write varies,
which is why the same image ends at `D`, at `X`, or at `X O K`.** The
trailing bytes were never nondeterministic guest behaviour; they are a
footrace with process teardown.

Two things follow that matter beyond this bug:

- **The exit code is trustworthy and the tail is not** -- the opposite of how
  they had been read. The code is written by one instruction at a known point;
  the tail is whatever escaped before teardown.
- **The tender's post-return path IS exercised in QEMU**, just after the
  outcome is fixed. `O` and `K` prove the loader resumes and completes a
  firmware call under the restored CR3. What QEMU still does not exercise is
  re-entry: `r15` is never 250 here, so `:tender-step` is reached once and the
  second `T` never appears. That remains hardware-only evidence.

Method, once more: every step here was a measurement designed to have two
distinguishable outcomes -- change the value and see which code appears, put
a byte before the write and see which side of it the loader's bytes land on.
The readings of the trace alone produced three wrong answers in this file.
