# ADR 0156 — LAN2 (bus3) debug plane: why the single-shot send emitted nothing, and how the census resolves it

Status: accepted (2026-09-06)

## Context

The GMKtec K16 has two RTL8125BG 2.5GbE NICs. bus2/0x02:00.0 carries the PXE
stream profile (wired to the Mac en15 = 10.77.0.1). This ADR is about the
second NIC, bus3/0x03:00.0 (wired to the Mac en8 = 10.10.10.1) as a LAN2 debug
/ control plane.

com-junkawasaki `orgs/kotoba-lang/aiueos`, branch `n2-tcp-stream-tranche1`.

### What was attempted (Phase 1, commit e09e4f1)

A minimal raw-Ethernet UDP :9000 log on bus3: the kernel extends the
low-memory page plan to pages 14..17 (fifteenth..eighteenth-start), allocates
a dedicated 16 KiB `bus3-dma-pages` window, requires `native.debug-link`, and
before entering the resident stream loop runs `debug-init` (rtl/rings-start on
bar-b) plus `debug-send` (one raw UDP frame to Mac en8 10.10.10.1:9000).

### Observed on the physical K16

1. The K16 screen shows "PREFLIGHT RTL8125" and stands still there.
2. The PXE server log shows the latest debug-EFI boot (TFTP bytes=207872 =
   the Phase-1 artifact) reaching ARP_OK -> NIC_40/43/44/45 -> TCP_OK ->
   STREAM_A1 -> 00 45 00 FF 19 52 A2 A3 A4 -> 21, repeated (the bus2 stream
   resident loop), while the screen stays on "PREFLIGHT RTL8125".
3. The Mac en8 never received the bus3 'Z' UDP :9000 frame (socat log empty,
   en8 ARP for 10.10.10.2 showed `(incomplete)`).

The screen freeze and the live bus2 netlog looked like a contradiction. It is
not.

## Analysis (Claude Opus 5, commit 05a3142)

### 1. The screen freeze is normal, not a hang

`kernel/` main has not returned since commit e39c453 made the stream resident.
The k16-preflight loader prints `STATUS XX` only after main returns. With the
stream loop running forever, main never returns, so the loader's status line
is never updated and the panel stays at the last checkpoint it printed
("PREFLIGHT RTL8125"). The kernel is advancing (the bus2 netlog proves it);
the display is simply not refreshed because no code path back from main runs
the loader's status print.

### 2. The Phase-1 bus3 DMA window named memory the kernel does not own

The Amu loader allocates exactly fourteen pages (receipt
`kernel_scratch.pages = 14`, i.e. physical-start .. +57344). `bus3-dma-pages`
pointed at `(- fifteenth-start 4096)` size 16384 — pages 14..17
(+57344 .. +73728) — which is **outside the loader-owned region**. Letting the
RTL8125 DMA into unowned memory is invalid even if `bar-b` decoded. The
Phase-1 single-shot could therefore not be trusted even if it had submitted.

### 3. The debug frame had no IPv4 header checksum

`build-udp-debug-frame` wrote the IPv4 header but left the checksum field
(bytes 24..25) zero. The Mac's `ip_input` drops a frame with a bad IP checksum
before any higher layer (socat on UDP 9000) sees it. So even a perfectly
transmitted frame would never reach the listener. (Claude stored 0x52AC.)

### 4. The Phase-1 send was observably silent by design

`debug-init`/`debug-send` ran inside a `let` whose results nothing observed.
Every failure mode — bar-b zero, MMIO undecoded, mac-valid false,
rings-start fault — looked identical from the outside (no frame, no log).

### 5. (Flagged, pre-existing, unverified) staging/tx-frame/rx-buffer aliasing

`stream-staging` = thirteenth-start = physical-start+49152 =
`rtl-dma-pages + 8192`, which is byte-for-byte the same address as
`stream-tx-frame` **and** as rx-descriptor-0's `rx-buffer-a` target (offset
8192) in the stream's own ring layout. So the staging buffer, the TX frame,
and RX descriptor 0's DMA target are one page. That could be eating received
bytes, which would be interesting given the loop keeps reporting `21`
("window exhausted, peer sent nothing"). Not traced by Claude; pre-existing
either way.

## Decision

1. **Diagnose before wiring DMA.** Replace the Phase-1 single-shot send with a
   read-only **census** emitted over the already-proven bus2 netlog. The census
   is one byte per bus, no PCI write, no MMIO write, no DMA:
   bit0=RTL8125 answers config space, bit1=BAR decoded, bit2=MEM-SPACE-ENABLE,
   bit3=BUS-MASTER-ENABLE, bit4=revision readable, bit5=MAC plausible,
   bit6=PHY link. A qualified NIC reads 0x7F.
   - The kernel emits `AIUEOS_STREAM_B7` (sentinel), then bus3's census, then
     bus2's census (the control; expect 7F) once, before the resident loop.
   - These ride the existing bus2 netlog, so no second wire or reboot beyond
     this one is needed to read them.

2. **Withhold bus3 DMA until it has a loader-owned window.** Do not re-enable
   the bus3 send until the census shows the NIC can DMA AND bus3 has an owned
   window. The cleanest source of an owned 16 KiB window is the K16 stream
   branch (bar-a > 0, so CR3 replacement never runs): pages 4..7 (`pt`,
   `reusable-page`, `frame-page`, `stack-page` = fifth-start..+32768) are
   loader-owned, already zeroed, contiguous 16 KiB, idle for the life of that
   branch. Point bus3-dma-pages at `(- fifth-start 4096)` inside the stream
   branch and delete the pages 14..17 extension. (Raising
   `kernel-scratch-pages` 14->18 touches pe32plus.cljc, the boot verifier,
   kernel.kotoba:389 and two contracts — no benefit here.)

3. **Fix the remaining bus3 send prerequisites** (once census says the NIC can
   DMA): a `pci-write bus 4 (bit-or (bit-and command 65535) 6)` to set
   MME+BME before MMIO, and a `(mmio-load-u16 mmio 108)` PHY link gate before
   submitting.

4. **Investigate the staging/tx-frame/rx-buffer-a aliasing** as a separate
   follow-up: it is a plausible contributor to the persistent `21` (bus2
   stream never sees the peer's SYN-ACK).

## The census answer (read on the K16, 2026-09-06)

The census EFI `810e0523…` booted and the three bytes arrived on the bus2
netlog, once, between `AIUEOS_NATIVE_TCP_OK` and the resident loop's first
`A1`:

```
AIUEOS_STREAM_B7      sentinel
AIUEOS_STREAM_7F      bus3 census
AIUEOS_STREAM_7F      bus2 census (control)
```

Order is `census-b` (bus 3) then `census-a` (bus 2), read from the source, not
inferred from the wire. **bus3 = 0x7F is every bit set**: the 8125 answers
config space, a memory BAR decodes inside the admitted window, MEM-SPACE-ENABLE
and BUS-MASTER-ENABLE are already on, ChipCmd reads back a revision, IDR0..5
holds a plausible unicast MAC, and PHYstatus reports link. The NIC can DMA.
bus2 reads the same, which is what makes the bus3 reading trustworthy rather
than a constant.

So the Phase-1 silence was not the NIC. It was the two faults in §2 and §3
plus the unobservability in §4.

Reading note: `grep` on this machine returns *no match* on `server.log` under a
UTF-8 locale, because the file carries a byte that is not valid UTF-8 and
macOS grep then reports every line as unmatched rather than erroring. `LC_ALL=C
grep` finds the census. A search that could not run and a search that found
nothing returned the same answer.

## Step 1 — the send, with an owned window and every stage observable

1. **Window.** `bus3-dma-pages` is bound inside the stream branch at
   `(kernel-subregion 4096 549755809792 (- fifth-start 4096) 16384)` =
   `fifth-start` .. +32768 = `pt`, `reusable-page`, `frame-page`, `stack-page`.
   The stream branch never replaces CR3 (that is the other arm of the `if`), so
   those four pages are allocated by the loader, zeroed by
   `prepare-owned-pages` / `prepare-extra-pages`, and idle for the life of this
   branch. They do not overlap `rtl-dma-pages` (`eleventh-start` .. +57344),
   `stream-tcb` or `stream-staging`. The pages 14..17 bindings and their five
   guard clauses are deleted; `kernel_scratch.pages` stays 14 and the receipt
   still says so.

2. **Prerequisites.** `rtl/arm-bus-master` and `rtl/link-up` name the two
   things `rtl/qualify` already did inline for bus2, so bus3 can ask for them
   without the whole ARP qualification. `arm-bus-master` writes
   MEM-SPACE|BUS-MASTER and then **reads the register back**, returning 1 only
   if the device reports both — the census says bus3 already has them, so on
   this board the write changes nothing; it exists so a submit never depends on
   firmware having left them on. `link-up` gates on PHYstatus before submitting,
   because a submit into a down PHY leaves the descriptor owned forever, which
   is indistinguishable from a ring fault.

3. **Observability.** This is the fault §4 named, and it is the one that made
   Phase 1 worthless regardless of what the wire did. Every stage now has its
   own code and all of them ride the bus2 netlog:

   | byte | meaning |
   |---|---|
   | `B8` | sentinel: the bus3 attempt starts here |
   | init `0` | ready |
   | init `6` | bar-b never decoded — no MMIO to init |
   | init `9` | the device would not report MEM-SPACE\|BUS-MASTER after the write |
   | init `7` | IDR0..5 is not a plausible unicast MAC |
   | init `2` | ChipCmd revision unreadable |
   | init `8` | PHY reports no link |
   | init `10+n` | `rings-start` refused with n (4 fifo, 1 install) |
   | send `0` | submitted **and** the engine cleared OWN — bytes left the NIC |
   | send `1` | the frame could not be built |
   | send `5` | descriptor still owned, or the wire length was rejected |
   | send `3` | a descriptor store did not read back |
   | send `4` | submitted, but OWN never cleared — the engine is not consuming |
   | send `7` | not attempted, because init refused |

   `debug-send` previously returned **0 both when the frame failed to build and
   when it was submitted** (`rtl/tx-submit` returns 0 on success, and the
   build-failure arm also returned 0), and `debug-send-status` then mapped
   success to 1 and a store fault to 0. That function is deleted rather than
   fixed: nothing called it. This is the workspace's recurring shape — a check
   that could not run returning the same value as a check that ran and found
   nothing — appearing inside the very module written to diagnose.

4. **What the pair of readings discriminates.** bus2 says whether the NIC
   transmitted (`send 0` means the engine consumed the descriptor). en8 says
   whether the Mac accepted it. `send 0` with nothing on en8 would isolate the
   frame contents (checksum, MACs) from the NIC; `send 4` would isolate the
   engine. Neither reading alone can do that, which is why both are taken.

The IPv4 header checksum stays 0x52AC, verified by hand against the header
this module writes: `0x4500 + 0x002B + 0x4011 + 0x0A0A + 0x0A02 + 0x0A0A +
0x0A01 = 0xAD53`, and `~0xAD53 = 0x52AC`. The peer MAC baked into
`store-peer-mac` (3c:18:a0:d5:82:a8) matches the Mac's live en8.

### No automated gate discriminates on this branch

The QEMU smokes are pinned to compiler `13d2f5df`, which now **refuses this
branch's kernel outright** (`:kotoba/target-rejected`, "typed values currently
require …") — measured on the unmodified source as well as the modified one.
Repointed at the `46eeedae` pin the build succeeds but the gate's expected
QEMU exit (33 / marker `MPRCD`) does not match the k16-loader-port loader —
again identically before and after this change. Both directions were measured;
neither gate is a regression signal here, and neither is claimed as one. The
physical K16 is the only instrument this branch has.

## The step-1 boot (K16, 2026-09-06, artifact `730b1293…`)

```
AIUEOS_NATIVE_TCP_OK
AIUEOS_STREAM_B7      sentinel
AIUEOS_STREAM_7F      bus3 census
AIUEOS_STREAM_7F      bus2 census
AIUEOS_STREAM_B8      bus3 attempt
AIUEOS_STREAM_00      debug-init  = ready
AIUEOS_STREAM_00      debug-send  = submitted AND the engine cleared OWN
AIUEOS_STREAM_A1      resident loop resumes
```

and `Z` — the payload byte this module writes — arrived on the Mac's en8
UDP :9000. **LAN2 one-way debug output works end to end**: bus master armed,
ring installed, PHY up, descriptor submitted, OWN cleared, `ip_input`
accepted, listener delivered.

### The listener was the third instrument to fail silently today

The first reading of en8 said *empty*. That reading was void:
`socat -u UDP-RECV:9000 CREATE:<file>` held the datagram and wrote nothing
until the process was killed. A control datagram sent from the Mac to its own
en8 address was also not recorded, which is what exposed it —
`OPEN:<file>,creat,append` records both. **Validate the instrument with a
control before reading a null result as evidence.** This is the same shape as
the `LC_ALL` grep above and the two QEMU gates below: three different tools, in
one session, answering "nothing" when they meant "I did not run".

### A defect the boot did not expose

`build-udp-debug-frame` wrote the **frame** length (43) into the IPv4
**total-length** field, where 29 belongs (20 ip + 8 udp + 1 payload), and
baked a checksum consistent with that wrong value. The Mac delivered it
anyway: the RTL8125 pads every frame to 60 bytes, so 46 bytes of Ethernet
payload arrive and `ip_input` trims to 43 instead of rejecting. That is luck.
It stops being true as soon as the payload passes 17 bytes — i.e. the first
time this plane is asked to carry a real message. Fixed to 29 with checksum
0x52BA (`~(4500+001D+4011+0A0A+0A02+0A0A+0A01)`), and the two lengths are now
separately named so they cannot be confused again.

**A green wire receipt is not a correct frame.** The send byte reports what
the NIC did with the descriptor; it cannot report what the header says.

## What LAN2 can and cannot do today

| | state |
|---|---|
| K16 → Mac, one-way UDP log | **works** (this boot) |
| K16 → Mac, more than one message | not wired — `debug-send` is called once, before the resident loop |
| K16 → Mac, arbitrary text | not wired — the payload is a fixed byte, and there is no integer→ASCII path |
| Mac → K16 control | **wired, one command byte per `stream-resident` cycle** (`debug-tick`, 2026-09-07/08): `P` → `p`; `R` → `r`, then `DB` on bus2 and the 0xCF9 reset; anything else → `?`. Sender: `kbb --backend sci os/aiueos/tools/k16-control.cljk <P\|R>`. **Not yet exercised on the board** (halted in `ud2` since the 47b8c209 run); proven against a loopback sink + fake board only. |

(As first written, 2026-09-06, this row read "not wired at all": `rings-start`
installed an RX descriptor on bus3 but nothing read it. The RX poll, the
positional 4-tuple filter and the closed command decode landed on 2026-09-07;
`R` on 2026-09-08 — owner decision: LAN2 carries debug output *and* control so
bus2 is only PXE plus the stream under test, and nobody presses the power
button.) What still holds: every command the board accepts is authority
crossing into the kernel. `R` is admitted because a platform reset is the one
thing the run already does to itself at its deliberate end (`DE`, 0xCF9 ←
0x06); it grants nothing new, it only lets the Mac choose *when*. Anything
beyond that needs the admission discipline the rest of this OS uses, not a
bigger switch statement. The reset is issued by `stream-resident`, not by
`debug-tick`: the tick answers `r` first (its send waits for TX completion, so
the Mac holds the acknowledgement before the board goes away) and returns
80+n; the resident loop, which owns the bus2 netlog, logs `D9 <80+n> DB` and
then writes 0xCF9. If execution continues the chipset ignored the write and
`DC` says so — `DB` without `DC` is the only shape that means the board went
down.

### Prerequisite on the bus2 side

§5's aliasing is confirmed by arithmetic, and it is narrower and worse than
"could be eating received bytes": `stream-tx-frame` = `rtl-dma-pages + 8192`,
`stream-staging` = `thirteenth-start` = `rtl-dma-pages + 8192`, and the
stream's own `rx-buffer-a-offset` is 8192. All three are one page. Every
netlog byte the resident loop emits is written into RX descriptor 0's DMA
target while the NIC owns it. The loop's persistent `21` (window exhausted,
peer sent nothing) is consistent with that. (`stream-tcb` at
`rtl-dma-pages + 4096` is *not* aliased — the RX ring is at +1024, 1024 bytes
wide, and +4096..+8192 is unused.)

## The A+B boot, and two results that overturn earlier claims

Artifact `8d2d73c1…` (aliasing fix + LAN2 receive path + MAC report) booted.

```
B7 7F 7F              census
B8 00                 bus3 init = ready
DA 70 70 FC 0B B6 31  bus3 MAC = 70:70:fc:0b:b6:31
00                    bus3 send = submitted AND the engine cleared OWN
A1 ... 21             the resident loop, 280 times, then silence
```

### 1. The aliasing was real and is NOT what eats the SYN-ACK

`stream-tx-frame` and `stream-staging` now live on pages 8 and 9, disjoint
from `rx-buffer-a`. The loop still reports `21` — 279 times in this boot.
The hypothesis is refuted. The overlap was genuine and worth removing, but
the persistent "peer sent nothing" has a different cause, still unknown.

### 2. The loop is not resident. It has never been resident.

|  boot | artifact | completed cycles |
|---|---|---|
| 14220.. | `810e0523` census | 278 |
| 17312.. | `730b1293` step 1 | 277 |
| 20369.. | `8d2d73c1` A+B | 280 |

Three artifacts, three boots, the same stop. The kernel is built with
`--fuel 1048576` and the receipt says `"replenishable": false` — one budget
for the whole boot, no top-up (ADR-0034's per-call replenish is emitted by
`package-kernel-object`; this artifact comes from `package-aiueos-boot`).
At roughly 3,760 fuel per cycle that budget buys about 280 cycles.

**A loop designed never to end, under a budget that is spent once, cannot
both be true.** Plan A-2's "the stream never halts the machine" has been
false on every boot since it was written, and nothing looked, because the
symptom is a log that stops rather than an error.

`1048576` is 2^20, which was `max-native-fuel` when the line was written. The
ceiling moved to 2^53-1 on 2026-09-03 (kotoba-kir ADR 0268). **The budget was
never a decision — it was the old maximum, kept after the maximum moved.**

The next boot doubles it to 2097152 and predicts ~556 cycles. If it stops near
280 again the mechanism is something else and the number goes back. It is
raised to be *measured*, not to be a fix; a bigger finite number is still a
finite number, and a genuinely resident loop needs a replenish, not a bigger
bucket.

Raising it required editing five places that each carried the literal (two
`--fuel` flags, the sealed-context check, the receipt and the OK line), and
the policy EDN turned out to be the authority — `--fuel` alone changed
nothing and the build failed naming the old value. The build script now
generates the policy from one variable. This is the same shape the
`excessive-native-fuel-policy` fixture documents: *the fifth place the
ceiling was written down.*

### 3. Retraction: the 'Z' on en8 is not proof

The previous revision recorded 'Z' arriving on en8 as end-to-end proof. **That
claim is withdrawn.** On this boot `debug-send` again returned 0 (submitted,
OWN cleared) and **nothing reached en8** — with a listener validated by a
control datagram immediately before and after. `netstat -I en8` shows 27
packets received in the machine's entire uptime.

The one reading that showed 'Z' came from the listener whose sink was broken,
recovered when that process was killed, so it cannot be timestamped or
attributed to a boot; another session was experimenting on this same wire that
afternoon. One unrepeatable reading from a defective instrument is not
evidence, and it should not have been written down as if it were.

What is established: bus3 census 7F, `debug-init` ready, and the TX engine
clearing OWN. What is NOT established: that any byte left the NIC, or that
bus3 is cabled to en8 at all. `wait-tx-complete` reads the OWN bit and not the
descriptor's error bits, so it cannot tell those apart — and without `tcpdump`
(BPF needs root here) neither can the Mac.

The cheapest test of the wiring costs nothing extra: the Mac's ARP requests
for 10.10.10.2 are broadcasts, so if bus3 is on that wire `debug-poll` sees
them and answers `1` ("not ours"), which the loop logs as `D9 01`. That
requires a live kernel, which is what the fuel change is for.

## The fuel mechanism is confirmed

Budget doubled to 2097152. Predicted ~556 cycles. **Measured 582.**

| budget | cycles | fuel/cycle |
|---|---|---|
| 1048576 | 278, 277, 280 | ~3,760 |
| 2097152 | 582 | ~3,600 |

The count moved with the budget. The loop stops because it runs out of fuel,
and for no other reason. The prediction was made before the reading and the
reading was not adjusted to fit it.

The doubled budget still ran out before the wiring test could be sent, so the
`D9` question is still unanswered: **not measured**, not negative.

The budget is now 1073741824 (2^30) — 512x the original, roughly 143,000
cycles. That number is chosen to outlast a working session, **not** because it
is the maximum: taking the ceiling as the budget is exactly the mistake that
produced 1048576 in the first place. It is a bucket, not a fix. A loop that is
genuinely resident needs a replenish in `package-aiueos-boot` (the receipt
still says `"replenishable": false`), and that is a compiler change, not a
larger literal.

`netstat -I en8` moved 27 -> 34 across the 582-cycle boot. Seven frames is not
nothing and not an explanation; the interface counter cannot say what they
were, and without BPF neither can anything else on this machine. It is
recorded because it is the only en8 evidence that moved, not because it
supports a conclusion.

## Root cause of the persistent `21`: the SYN was overwritten before it was sent

`stream-log` built its UDP/7777 receipt **in `tx-frame`** — it zeroes 62 bytes
of that page, writes a log datagram, and submits it. `stream-connect` builds
the SYN into `tx-frame`, then calls `stream-log` **seven times on the same
page**, and only then submits `tx-frame` as the SYN. What went on the wire was
the last log frame, truncated to `syn-len`. Every cycle. About 363,000 times
in the last boot alone.

### The Mac's own counters are unambiguous

```
netstat -s -p tcp:  0 connection request
                    0 discarded for bad checksum
                    0 discarded because packet too short
netstat -s -p ip:  10 bad header checksums   (whole machine, whole uptime)
lsof -nP -iTCP:8443: the bridge IS listening on 10.77.0.1:8443
bridge.log:         no K16_STREAM_CONNECTED since it started, 2026-09-05
```

Not "saw the SYN and rejected it" — **never received one**. Meanwhile the
netlog UDP from the same NIC, the same submit path and the same MAC helpers
arrives fine, which is what made the frame contents the only variable left.

### This was found once before, and the fix was reverted for a good reason

Commit `18bf9bd` (2026-09-06 00:44) diagnosed exactly this and pointed
`stream-log` at `staging`. Commit `485ed76` reverted it with no message.
The revert was right: **at that time `staging` and `tx-frame` were the same
page** (both `rtl-dma-pages + 8192`), so the fix was a no-op and would have
looked like it did nothing.

So the aliasing fix earlier in this document was not refuted after all — it
was refuted *as an explanation of `21`*, which it is not, and it is *the
precondition* for this fix to be able to work at all. Two separate defects
sharing one page, where removing either alone changes nothing.

### Why no ordering fixes it

`A2` is logged **after `tx-submit-stream` and before `wait-tx-complete-stream`**
— i.e. while the NIC owns the descriptor and is reading the frame. Moving the
seven diagnostics after the submit would still corrupt the SYN mid-DMA. Only a
separate buffer works.

### The fix: one scratch region, three fixed offsets

`stream-scratch` is 12 KiB at `second-start` (`page-table-root`, `pdpt`, `pd` —
contiguous, zeroed by `prepare-owned-pages`, and never installed in this branch
because `prepare-page-tables` is in the CR3 arm). Inside it: **log at +0, tx at
+4096, staging at +8192.**

`stream-connect`, `receive-syn-ack`, `receive-established` and
`stream-resident` now take `scratch` and derive all three, plus `tcb` from
`win + 4096`. Three separately-computed addresses became one region with fixed
offsets, so a future edit cannot quietly point two names at one page without
changing an offset.

That also answers the reason `18bf9bd` gave for not doing this ("a dedicated
netlog page would need a 6th arity and is rejected by the compiler"): `tcb` is
derivable from `win`, which frees the slot. The arity ceiling was real; the
conclusion drawn from it was not.

The seven diagnostics now *read* `tx-frame` and *write* to `log-frame`, so for
the first time they report the actual SYN's ethertype, IHL, IP checksum fold
and TCP checksum rather than the previous log frame's.

**Predicted, before the boot:** `netstat -s -p tcp` "connection request"
becomes non-zero and `bridge.log` gains `K16_STREAM_CONNECTED`. If neither
moves, this diagnosis is wrong and the frame contents are the next suspect —
the diagnostics will then be reading the real SYN and can say so.

## A silent kernel that was a deploy bug, not a code bug

The banner earned its place on its first boot. The panel read
`AIUEOS K16 BUILD 93ead90d392de1f5 42838f3-dirty` — **one artifact behind what
was being served.** Without it the next reading (`0 connection request`) would
have been recorded as "the SYN fix did not work", when the fix had not been on
the machine at all.

That boot then produced **no netlog at all** — not one line — while the
previous boot of a **byte-identical kernel** (`93ead90d`, only the loader
differed) had produced 363,313 cycles. Both artifacts boot correctly under
QEMU, printing ENTER and BUILD and reaching the kernel's `M` marker on the
debug port. And the panel showed ENTER, BUILD and RTL8125, so the loader had
completed everything and called the kernel.

The cause is the deploy, not the code. The PXE server does
`content = selected.read_bytes()` at request time, and the artifact was being
installed with `cp` **onto the live path**, which truncates and rewrites in
place. Both builds are **exactly 211968 bytes** — the two note strings happen
to be the same length, so the layouts match — so a transfer overlapping a
deploy reads a full-length file whose head and tail come from different
builds. Nothing downstream can see that: the size is right, the loader runs,
the banner (near the end of the file) reads from one build while the kernel
(near the start) comes from another.

The deduction, rather than the guess: the panel proves the tail was
`4d75d6bb`; `4d75d6bb`'s kernel is byte-identical to one that had just run
363,313 cycles, so a *pure* `4d75d6bb` would have produced netlog; it produced
none; therefore what ran was not a pure `4d75d6bb`.

`scripts/k16-pxe-deploy.sh` now writes a temporary file beside the target and
`mv`s it. `rename(2)` on one filesystem is atomic: a reader gets the old file
or the new one, never a seam.

**This is the same shape as everything else in this document** — an unmeasured
assumption ("copying a file is atomic") producing a result that looks exactly
like a failure of the thing under test. It is the seventh instance today.

## Why no automated gate discriminates: the CR3 path triple-faults, and always has

Earlier this document recorded that the QEMU smokes do not discriminate and
left it there. They do not discriminate for a *reason*, and the reason is a
real defect:

```
v=0e e=0003  page fault, PRESENT + WRITE   CR2=0x110100  IP=0x11a424
             -> v=0d (#GP) -> v=08 (double) -> Triple fault -> reset
```

The receipt's own `protection` block says `kernel_text 0x101000-0x11bfff` is
**RX** and `kernel_state 0x11c000-0x12efff` is RW-NX. **CR2 `0x110100` is
inside the kernel's own read-only text.** So once `enable-page-protection`
sets CR0.WP, a write into text that had been silently tolerated becomes a
fault — and the #PF handler is installed *later* in the same branch, so there
is nothing to catch it. Double fault, triple fault, reset. With `-no-reboot`
QEMU then exits 0, which is why the gate's "expected 33" never matches and why
the failure has looked like a stale expectation rather than a crash.

Measured across four artifacts spanning the whole of this work — including
`810e0523`, the census build this ADR was originally written about — the
debug port emits exactly `M` (the map marker) and nothing else. Not one of
them reaches `P`, `R`, `C` or `D`. **The CR3 branch has never completed under
QEMU during any of this work.**

The K16 does not take that branch (`bar-a > 0`), which is why the physical
machine has been the only instrument. But it also means the one automated
signal this kernel has was dead the whole time, and "the gate's expected value
is stale" — written in this document a few hours ago — was the wrong reading
of the same evidence. The expectation is fine; the guest crashes.

Next step for that path is to name what writes `0x110100`: the fault IP is
`0x11a424`, both addresses are stable across runs, and the sequence is
deterministic.

## Two silent boots, and a retraction of the explanation for each

Boot of `4d75d6bb` (banner loader, kernel `93ead90d`): silent.
Boot of `f21cdc14` (banner loader, kernel `3b949b08`, SYN fix): silent.
Boot of `cb41be47` (pre-banner loader, kernel `93ead90d`) before them: 363,313
cycles.

Silent means silent: `netstat -I en15` shows **zero packets received in 30
seconds**, twice. The K16 transmits nothing. The panel shows ENTER, BUILD and
RTL8125 — so the loader completed segment copy, `AllocateAnyPages`,
`GetMemoryMap` and the PCI check, and called the kernel. `STATUS` never
appears, so `main` has not returned.

**Retraction 1 — the torn image.** The first silence was attributed to a
non-atomic deploy: `cp` onto the live path while the server was reading it,
with both artifacts exactly 211968 bytes so the seam would be invisible. The
second boot was deployed with `rename(2)` and was silent too. The atomic
deploy is a correct fix and stays; **it was not the explanation.**

**Retraction 2 — the banner loader.** With `93ead90d` failing under the new
loader and succeeding under the old one, the loader looked like the common
factor. It is not: the two `.text` sections were compared instruction by
instruction. The insertion is 26 bytes in the intended place, **all fourteen
subsequent rip displacements are corrected by exactly 26**, the two absolute
addresses the preflight hands the kernel (`context 0x11c000`,
`returnable-entry 0x11bac1`) are unchanged, and the BUILD string's reference
resolves to the right `.data` offset — verified against where the bytes
actually sit in the file. PE section layout is consistent (`.text`
0x21e -> 0x238, `.data` 0x33252 -> 0x332c4, same vaddrs, same `SizeOfImage`,
same file size). **The loader is byte-correct.**

So "the banner is the common factor" was an inference from three data points,
and the code says it is wrong. What else changed between the last working boot
and the first silent one: the machine had just run **363,313 cycles**, roughly
four million frames through bus2 — three orders of magnitude more than any
boot before it.

**Next reboot re-runs the control**, `cb41be47` itself. Two nulls have now been
read off a rig whose baseline was last confirmed before that long run, and the
whole of this document is a record of what happens when a null is read from an
instrument nobody re-checked. If the control is silent, the machine changed and
every artifact reading since is void. If it runs, the variable really is in the
newer artifacts and the bisect continues with the pre-banner build of the SYN
fix (`04aa5988`), which is built and waiting.

## The three silent boots were a dead logger. The machine never stopped.

`netstat -I en15` decided it, and the deciding number was the packet SIZE:

```
delta pkts  = 3,728,295
delta bytes = 230,535,288
average     = 61.8 bytes/packet     <- the netlog frame is 62 bytes
3,728,295 / 12 frames per cycle = 310,691 cycles
```

310,691 against the 310,553 that the last *logged* boot ran. The control
transmitted a full fuel-exhaustion run and **the Mac received every frame**.
Walking the counter backwards, the interval covering the `f21cdc14` boot shows
`+3,728,288` — the same run. Those boots were never silent.

`lsof -nP -iUDP:7777` returns nothing: the PXE server's netlog thread is gone.
The log holds the epitaph at line 4026326 —
`Exception in thread Thread-3 (netlog_server)` — and nothing else, because the
traceback went to stderr and nothing captured it (`grep -c 'File "'` over the
whole 270 MB file: **0**). The process kept serving DHCP and TFTP throughout,
so from outside it looked healthy.

**I caused this.** The receive loop had no exception handling, and raising the
fuel budget to 2^30 raised the netlog from ~3,400 lines per boot to
**3.7 million**. The instrument was fine at the budget it was designed under
and died at the one I chose without asking what it would cost.

Three conclusions rest on those readings and all three are withdrawn:

| conclusion | status |
|---|---|
| the deploy tore the image | withdrawn (retracted once already; still not it) |
| the banner loader broke the boot | withdrawn (and the loader was separately proven byte-correct) |
| the machine degraded: 310k -> 52k -> 0 -> 0 | **withdrawn** — the decline is the logger dying mid-run, not the machine |
| the aliasing is not what eats the SYN-ACK | **stands** — measured at boot 20384, before the logger died |
| fuel determines the cycle count | **stands** — 2^20 gave 277-280 five times, 2^21 gave 582 |

### What replaced the instrument

The PXE server binds UDP 67 and 69 and **cannot be restarted by this user** —
binding any port below 1024 is EPERM here, so killing it would end PXE booting
with no way back. It was left alone. The netlog port is 7777, unprivileged, so
the receiver was rebuilt beside it: `tools/k16-netlog-standalone.py`, which
never dies on a datagram, keeps the exception text, and prints a liveness line
every 10,000 receipts so that a dead receiver and a quiet wire can no longer
produce the same empty file. It was validated with a control datagram before
anything was read from it. The same guard is applied to the server's own loop
for whenever it is next restarted.

### And the budget goes back down

2^30 was chosen to outlast a session. What it actually bought was 3.7 million
log lines per boot, which is what killed the receiver. The SYN fix needs a few
hundred cycles to prove itself, so the next artifact is built at **1048576** —
not because that is a ceiling, but because it is what the instrument can read.
A budget is a choice about the whole rig, not just about the kernel.

## The bus2 stream: from `21` on every cycle to a completed handshake on every cycle

With the netlog instrument rebuilt and the board resetting itself at the end of
each run (0xCF9), iterations cost about two minutes and no hand on a button.
What that bought, in order, each step measured on the K16 before the next:

| # | defect | how it showed | fix | wire after |
|---|---|---|---|---|
| 1 | `stream-log` built its receipt in `tx-frame`, overwriting the SYN between build and submit | Mac never saw a SYN; netlog fine | separate log page in one `scratch` region (log +0, tx +4096, staging +8192) | SYN reaches the Mac (`SYN_RCVD`) |
| 2 | IPv4 checksum summed over the previous cycle's checksum field | fold alternated `FF`/`D4`, field `2B`/`00`, 139 vs 138 | zero the field first | `FF 2B` every cycle |
| 3 | SYN carried seq 0; `receive-syn-ack` wanted ack ISS+1 | offline TCP checksum matched seq 0, not the ISS | `tcb-init` seeds snd-nxt = ISS | TCP checksum byte `8B`→`A8` (= recomputed for ISS) |
| 4 | stream RX ring wrote opts1 @+0 / addr @+8; NIC (RxDescV3) reads addr @+16, opts1 @+28 | poll read a zero OWN forever; `A4` every cycle | rings-start's layout, zeroed descriptors, EOR only on the last | — (masked by 5) |
| 5 | RDSAR written into a running receiver is not latched | still `A4` after 4 | StopReq → FIFO drain → ChipCmd 0 → RDSAR → RE\|TE | frames arrive: `A8` (checksum path reached) |
| 6 | TCP checksum verified over 20 bytes; a macOS SYN-ACK carries 20–24 bytes of options | MAC/IP/ports/ack all passed, every frame fell to 168/96 | TCP length = IPv4 total − 20 | **`K16_STREAM_CONNECTED from 10.77.0.10`** |
| 7 | the retry was a `let` binding: ran before the frame was judged | `A4` then eight `A8` | a call, made only in the not-ours branches, advancing the ring head | clean single verdicts |
| 8 | ESTABLISHED poll 250000 × 8 ≈ 2M calls; a boot has 2^20 fuel, no replenish | `A9 E8 E7` then silence until reset | 8000 per tick, and a note that fuel is the budget | window completes: `E8 … E0 21` |
| 9 | `rcv-wnd` seeded 0 | every data segment out-of-window | 8192 | — |
| 10 | fixed source port 49155 every cycle | cycle N+1's SYN hit the peer's FIN-WAIT-1 for cycle N: `A6`/94 on every cycle after the first | port and ISS move per cycle | **every cycle completes the handshake** (ports 49636, 49637, …; no lingering 8443 states) |
| 11 | the ESTABLISHED window had no 4-tuple check; DHCP/ARP broadcasts were judged as TCP | `F5` on the first frame of every window | ethertype / IHL / proto / addresses / ports, stray = one tick | `F6` never fires — the remaining `F5` frame is ours |

Also in the same run of work: the segment is now parsed rather than assumed
(data offset from byte 46, payload = IPv4 total − 20 − doff, seq from the
header; it used to be `bytes − 54` starting at rcv-nxt, which counted options,
pad and FCS as data and copied from byte 0 of the frame); delivered data is
acknowledged with a real segment (`build-ack` wrote no Ethernet header and no
checksums into the staging page and was never submitted); a peer FIN is
acknowledged and answered with our own FIN\|ACK (result 100 = `0x70` on the
wire). These are landed and not yet exercised: every window so far has ended
on one out-of-window frame followed by an empty window.

### Measured 2026-09-07 11:03 (kernel 47b8c209): no F5, no frame at all

The build with tcp-h1 (rearm + head step before the ACK) booted at 11:03 JST.
Five cycles reached `A9` and the bridge logged all five connections (ports
49632–49636). Every ESTABLISHED window read `E8 F1 E7 F1 … E0 F1 21`: nine
empty polls, then the window expired. No `F5` — the out-of-window verdict is
gone — and no `F7` either, because **nothing arrived**: the bridge was a byte
forwarder to a TLS server (`api.murakumo.cloud:443`), which never speaks first,
and the board's stream never sends. The window was empty by construction
(tcp-h5). Cycle 6 read `A2 A3 A4`: its SYN reused the previous boot's cycle-0
4-tuple (the ISS moved per cycle from a constant base, so every boot used the
same ports) and the Mac's still-ESTABLISHED socket answered with a challenge
ACK. A seventh `A1` and then silence: the run died in `ud2` before `DE` —
cadence 6 did not fit in 2^20 either. The single `FC` on the wire was a MAC
byte inside the `DA` block (`70 70 FC 0B B6 31`), not a checksum verdict; the
DA channel put raw bytes on the sentinel wire (fixed below).

### Open at this revision

Kernel `f039f387` (cadence 4, otherwise 47b8c209) is served and unread; the
debug bridge that greets and closes with RST is live. Prediction for the next
boot: `A9 F7 F8` (greeting admitted and staged), a data ACK, `FA`/`0x70` when
the RST arrives, `DE` after four cycles and a self-reset through 0xCF9. Behind
it, two more images are built and held: `599e64a8` (129 tautological store
checks rewritten to READ-BACK or sequencing; `DA <byte>` pairs) and `f6af155d`
(tcp-h15: ISS salted per boot from `kernel-rdtsc`, TCB slot 19). They are read
one at a time, in that order.

### Instruments, and the two that were dead

- `netstat -s -p tcp` on this Mac reports **zero for everything**, including a
  connection made from this machine that the bridge logged at that moment.
  Every "0 connection request" recorded above came from it. Dead; do not use.
- The bridge is `kbb --backend sci os/aiueos/tools/k16-bridge.cljk --mode debug` on
  10.77.0.1:8443 (since 2026-09-07 11:25 JST; it replaced the Python forwarder
  `k16-bridge.py`, kept as `--mode forward`). On connect it logs
  `K16_STREAM_CONNECTED from <ip>:<port>` (the rig check's contract line),
  sends one `K16_BRIDGE_HELLO nnnn <iso>` greeting, logs any bytes back as
  hex, and after `--hold-ms` (1000) closes with RST (`resetAndDestroy`) so the
  Mac holds no state for the 4-tuple. Loopback proof: greeting received, 14 RX
  bytes logged, client sees ECONNRESET. `netstat -an -p tcp | grep 8443` shows
  the peer's state and is live; `netstat -s` is not.
- The netlog is `tools/k16-netlog-standalone.py` on 10.77.0.1:7777; the PXE
  server's own receiver thread is dead and the process cannot be restarted by
  this user (UDP 67/69 need root). Validate with a control datagram before
  reading a null.
- The LAN2 control sender is `kbb --backend sci os/aiueos/tools/k16-control.cljk <P|R>`
  (2026-09-08): one datagram 10.10.10.1 → 10.10.10.2:9000, then it watches the
  bus3 sink file (`/tmp/k16-bus3-en8.log`) **from the offset it had when the
  datagram left** — a line already in the file cannot satisfy it — for one
  `K16_BUS3_RX from=10.10.10.2:… bytes=1` line, and prints
  `CONTROL\t<cmd>\t<answer|timeout>` (exit 0 answered / 1 timeout / 2
  could-not-send). Proven on loopback against `k16-bus3-sink.cljs` and a
  fake board: `P`→`p`, `R`→`r`, `X`→`?` exit 0; with the board gone and the
  same sink file still holding those answers, exit 1 `timeout` (the stale
  lines were not read); `--from` an address this host does not own, exit 2.
  The board round trip is **not measured** (board halted). Written in nbb
  because kbb hosts no UDP send (E14; re-measured 2026-09-08: `lib/kbb` is
  browse edn env fs git proc str) — a migration candidate, not a precedent.

### Wire bytes (one table — collisions cost a whole iteration today)

`A1` SYN built · `A2` submitted · `A3` TX complete · `A4` SYN-ACK window
expired · `A6` ports/ack mismatch → 94 · `A7` IPv4 checksum → 93 · `A8` TCP
checksum → 96 · `A9` handshake complete · `AE` retransmit budget gone · `AF`
build failed · `B0` submit failed · `B7` census sentinel · `B8` bus3 sentinel ·
`D9` bus3 event · `DA` one bus3 MAC byte follows (emitted before **each** of
the six MAC bytes: `DA m0 DA m1 … DA m5`, 12 datagrams; after a `DA` the reader
consumes exactly one byte whatever its value — it can be `FC`, `B6` or `DA`.
Until 2026-09-07 it was one `DA` + six positional bytes, and a MAC byte `FC`
was read as the `FC` checksum verdict) · `DB` bus3 `R` received and `r`
answered, 0xCF9 reset follows (2026-09-08) · `DC` that reset returned — the
chipset ignored it, the cycle continues · `DE` run end → reset · `E0–E8`
ESTABLISHED window entry with ticks remaining · `F1` empty poll · `F2` bad
descriptor · `F3` duplicate · `F4` queue full · `F5` out-of-window (+4 bytes
of inputs) · `F6` not ours · `F7` admitted · `F8` staged · `F9` delivered ·
`0x0C+result` cycle result (`21` window expired, `6A` 94, `6F` 99, `70` 100).
The first instrumentation used `B0`, `B6`, `B7`, `B8` and was unreadable by
construction. The byte after `D9` is `debug-tick`'s value: `01` not ours, `02`
RX ring dead, `40+n` `P` answered, `50+n` `R` answered, `60+n` unknown
answered, n = send status. On bus3 itself (UDP 9000, its own channel in
`wire-bytes.edn`): `Z` hello, `p`, `r`, `?`. The registry
`os/aiueos/native/wire-bytes.edn` is the one table; this paragraph is its
prose, checked by `kbb --backend sci os/aiueos/tools/verify-wire-bytes.cljk`.

## The rig check: every instrument echoes a nonce before it is read (2026-09-07)

Four instruments went silent in two days and each silence was read as the
board's (the dead netlog thread, the unflushed socat sink, grep returning
nothing, the local UDP probe that "was not delivered"). The instrument's null
and the board's null had the same shape every time. `tools/k16-rig-check.cljs`
(nbb, no new .sh or .py) gives each instrument a control it must echo, tagged
with a fresh nonce so that a stale log cannot satisfy it, and prints one line
per instrument: `INSTRUMENT<TAB>name<TAB>PASS|SLOW|FAIL|UNMEASURED<TAB>evidence`.
Exit 0 = every control came back; 1 = a control did not (the line names it and
why); 2 = something could not be measured at all (a log path that does not
exist is not a failed instrument, it is a question that was not asked). 2 wins
over 1. `SLOW` means the nonce came back after the 2 s reading budget but
inside an 8 s grace window: the instrument is validated, the budget is not.

| instrument | control | must appear as |
|---|---|---|
| netlog | UDP `K16_RIG_CTRL_<nonce>` → 10.77.0.1:7777 | `AIUEOS_NETLOG_RX from=10.77.0.1:… message=K16_RIG_CTRL_<nonce>` in netlog.log |
| bridge | TCP connect → 10.77.0.1:8443, closed at once | `K16_STREAM_CONNECTED from <our addr:port>` in bridge.log (netstat -an -p tcp as fallback) |
| pxe-dhcp | DHCPDISCOVER from MAC `02:52:49:<nonce>` → :67 | `AIUEOS_PXE_DHCP_IGNORED mac=02:52:49:…` (the server offers nothing to a foreign MAC) |
| pxe-tftp | RRQ for `k16-rig-ctrl-<nonce>` → :69 | `AIUEOS_PXE_TFTP_REJECT … file=k16-rig-ctrl-<nonce>` (only the boot file is served) |
| bus3-sink | UDP `K16_RIG_CTRL_<nonce>` → 10.10.10.1:9000 | the nonce in the sink named by the receiver's own argv (`k16-bus3-sink.cljs --sink <path>`, where it appears as the `hex=` of the datagram; socat's `OPEN:<path>` form is still recognised) |
| pxe-process, served-image, bus2-if, bus3-if | none (passive) | pid + log mtime; sha256 + size + the UTF-16 `K16 BUILD` note; `inet` present |

The board is not an instrument. It gets one `BOARD last-seen` line and is
never a failure: PXE log lines carry no clock, so the bound comes from the
mtime of any log whose newest line is the board's. Because the check's own
controls push that line off the end of every log, the tightest bound ever
measured is carried in `/private/tmp/aiueos-k16-pxe/rig-check-receipt.edn`
and the line reports an interval.

### Three things the check measured that were not known before it ran

- **`grep` on server.log is blind without `-a`, in any locale.** `grep` on
  this Mac is ugrep 7.8.4; server.log holds 4.0 million of the board's
  NUL-padded netlog frames from before the in-process receiver died, so the
  file is classified binary and every pattern matches nothing. With `-a`,
  442 `AIUEOS_PXE_TFTP_RRQ` lines. The check never shells out to grep; it
  reads bytes and decodes latin1, and prints `nul-bytes=present(grep needs -a)`
  on the pxe-process line so the next reader does not rediscover this.
- **Local UDP to 10.77.0.1 is delivered — slowly.** Every control datagram sent
  to 10.77.0.1:7777/:67/:69 over nine runs was recorded, and recorded with the
  source `from=10.77.0.1:<ephemeral>`. Latency at load average 113–128 was
  300–1600 ms; one run missed the 2 s window on all three UDP instruments and
  every one of those datagrams was in the log when looked for afterwards. A
  burst of five datagrams 200 ms apart was recorded as one block ~1.1 s after
  the first send, none dropped: the wait is the receiver process waiting to be
  scheduled, not the wire. So the 2026-09-06 "not delivered" reading (rank-01)
  was, as far as this measurement can say, a reading taken inside the latency.
  Whether the in-process receiver's `IP_BOUND_IF` socket behaved differently
  on 09-06 was not tested — that thread is dead and cannot be probed; the
  DHCP and TFTP sockets, which carry the same `IP_BOUND_IF en15`, did receive
  the local controls today.
- **The bus3 sink was unreadable from the moment it was unlinked.** socat
  pid 30661 (`UDP-RECV:9000 … OPEN:/tmp/k16-bus3-en8.log`) was alive and bound,
  and `lsof` showed fd 6 open for write on that path — but the path did not
  exist on disk. Datagrams were being appended to an inode nobody could open.
  The check reported `bus3-sink FAIL` for this on every run; the earlier claim
  that the listener is "validated before and after each reading" had been
  false since the file was removed. The coordinator restarted socat at 11:20
  JST; the sink below replaced it at 11:43 JST.

### The bus3 sink opens its file by name, so it cannot hold a dead inode (2026-09-07)

`tools/k16-bus3-sink.cljs` (nbb; rig-h2 of rank-02) replaces the socat
listener. socat opened the sink once and kept the fd, which is exactly the
state the rig check catches; the new sink never keeps the file open. Every
datagram is `fs.appendFileSync` — open by name, append, close — so an unlink
between two datagrams costs the file's history and nothing else: the next
datagram recreates the path, and the file that exists on disk is always the
file receiving receipts. One line per datagram, `K16_BUS3_RX from=<ip>:<port>
bytes=<n> hex=<hex> t=<iso>`, plus `K16_BUS3_SINK_READY` on start (also to
the sink, so the file exists from the first second the socket is bound),
`K16_BUS3_SINK_ALIVE received=<n> write-failures=<f>` every `--liveness-s`
(default 300) and `K16_BUS3_SINK_STOP` on a signal — a dead sink and a quiet
wire no longer look the same, the netlog receiver's rule. It refuses to start
(exit 2) when the sink directory is missing (`reason=sink-dir-missing`) or
the address cannot be bound (`reason=bind-failed code=EADDRINUSE|…`), measured
for all three. Proof on a scratch port, 2026-09-07 02:38Z: datagram one landed
in inode 2046095454; `rm sink.log`; datagram two recreated the path as inode
2046095479 holding `K16_BUS3_RX … hex=4b31365f50524f4f465f74776f0a`; SIGTERM
wrote the STOP line and exited 0. The rig check now recognises both receiver
shapes and, for the nbb one, treats an absent file as recoverable: it sends
the control anyway and PASSes with "(sink was absent before the control; the
receiver recreated it by name)" — measured, alongside FAIL for a stopped sink
and PASS for the socat shape. First live run after the swap (02:43Z, load
24.8): `bus3-sink PASS control K16_RIG_CTRL_7ef03b5f -> 10.10.10.1:9000
recorded after 105ms ; process=nbb pid 17394`, `SUMMARY pass=9 … exit=0`.
Process discovery requires the command's first token to be the interpreter:
a `zsh -c '… kbb --backend sci k16-bus3-sink.cljk --sink $S/x'` wrapper carries the same
substring and was picked first during this work, with an unexpanded `$S`.

### Measured output

Live rig, 2026-09-07 02:13:53Z, load 128 (abridged; evidence columns cut):

```
INSTRUMENT  bus2-if       PASS  en15 inet 10.77.0.1 status: active
INSTRUMENT  bus3-if       PASS  en8 inet 10.10.10.1 status: active
INSTRUMENT  pxe-process   PASS  pid 11960 since Sat Sep 5 09:39:28 2026 ; bytes=270032435 nul-bytes=present(grep needs -a)
INSTRUMENT  served-image  PASS  sha256=3170dcd9… bytes=224256 build=utf16le:K16 BUILD 47b8c20985da0d0f 7713901-dirty ; last board RRQ served this size
INSTRUMENT  bus3-sink     FAIL  sink /tmp/k16-bus3-en8.log does not exist on disk while the receiver is alive -- its fd points at an unlinked inode
INSTRUMENT  bridge        PASS  connected from 10.77.0.1:56273 ; logged after 506ms as: K16_STREAM_CONNECTED from 10.77.0.1:56273
INSTRUMENT  netlog        PASS  control K16_RIG_CTRL_89ddf0cb sent to 10.77.0.1:7777 recorded after 710ms as: AIUEOS_NETLOG_RX from=10.77.0.1:61246 message=K16_RIG_CTRL_89ddf0cb
INSTRUMENT  pxe-dhcp      PASS  DHCPDISCOVER from 02:52:49:70:6c:95 -> 10.77.0.1:67 logged after 1221ms as: AIUEOS_PXE_DHCP_IGNORED mac=02:52:49:70:6c:95
INSTRUMENT  pxe-tftp      PASS  RRQ k16-rig-ctrl-f805267d -> 10.77.0.1:69 logged after 1325ms as: AIUEOS_PXE_TFTP_REJECT from=10.77.0.1:55849 file=k16-rig-ctrl-f805267d
SUMMARY     pass=8 slow=0 fail=1 unmeasured=0 exit=1 failed=bus3-sink
```

`BOARD last-seen between 2026-09-07T02:03:22.950Z and 2026-09-07T02:12:55.701Z`
— the board booted the 224256-byte `47b8c209…` image at 02:03Z (11:03 JST):
`bridge.log` ended with `K16_STREAM_CONNECTED from 10.77.0.10:49636` and
netlog.log with `AIUEOS_STREAM_45` at that minute, and the last TFTP RRQ in
server.log served exactly 224256 bytes.

Broken on purpose, `--netlog-port 7778`, same rig one minute later:

```
INSTRUMENT  pxe-tftp  SLOW  RRQ k16-rig-ctrl-8a5df637 -> 10.77.0.1:69 logged after 2028ms as: AIUEOS_PXE_TFTP_REJECT …
INSTRUMENT  netlog    FAIL  control K16_RIG_CTRL_b704864c sent to 10.77.0.1:7778 NOT recorded in /private/tmp/aiueos-k16-pxe/netlog.log within 10000ms (never arrived, or receiver not scheduled) ; process=pid 45443 … socket=not-bound
SUMMARY     pass=6 slow=1 fail=2 unmeasured=0 exit=1 failed=netlog,bus3-sink
```

It fails for the reason it names (`socket=not-bound` on 7778), and the `SLOW`
line is the 28 ms by which a 2 s reader would have called TFTP dead.
`--bridge-port 8444` exits 1 with `connect ECONNREFUSED`; `--bridge-log
/nonexistent` exits 2 with `UNMEASURED`, not 1 — a missing log is not a dead
bridge.

## The forwarder never spoke; the bridge now greets and closes with RST (2026-09-07)

Three changes on `k16-stream-20260906` after the 11:03 reading, each measured
off the board where the board could not yet measure it:

| change | why | measured |
|---|---|---|
| `k16-bridge.cljs` debug mode (greeting, RX log, RST after 1 s) | the forwarder to a TLS server never sends first, so every window was empty; and its ESTABLISHED sockets outlived the boot and challenged the next boot's SYN | loopback: greeting received, RX logged, ECONNRESET after the hold; `k16-rig-check` 9/9 PASS after the swap |
| `debug-run-cycles` 6 → 4 | 5 completed cycles + 1 failed handshake exhausted 2^20; no `DE` | fits by construction; the board says |
| tcp-h15: ISS = base + (salt + cycles)·65536, salt drawn once per boot from `kernel-rdtsc` into TCB slot 19 (tcb-init leaves slots 17 and 19 alone) | same ports every boot → challenge ACK from the previous boot's socket | decisive test is two boots with disjoint port sets in bridge.log; built as `f6af155d` |
| 129 tautological store checks → READ-BACK or sequencing (E8, PR #292/#295); `DA <byte>` pairs | `kernel-store-*` returns its operand, so `(= (store …) v)` could not fail; a MAC byte read as `FC` | `verify-store-tautology` 129 → 0, `verify-wire-bytes` 66 emissions / 39 entries / 0 findings; kernel builds bit-identical twice; built as `599e64a8` |
| boot build re-says the kernel verifier's OK line or refuses | the line went to `/dev/null`, so a skipped verification printed the same three lines as a passed one | `AIUEOS_KOTOBA_NATIVE_KERNEL_OK … fuel=1048576` surfaced |

Landed in the toolchain the same day, reaching the board only after amu's
kotoba-native pin advances (sibling PR amu#857) and the K16 build's amu
(`/private/tmp/amu-5cec` @ 3c6d035) is re-pinned: kotoba-native#153 (context
slots in the RW page, no absolute `0x1101xx` stores), #155 (vector 6 writes
`'U'` to 0xE9 on fuel exhaustion — QEMU `"DU"`/59 vs control `"D"`/33), #156 +
#162 and five sibling repos (gmir/kir/sema/lang/verifier) admitting
`kernel-undefined-opcode-handler-address` so the kernel can install gate 6.
Until then a fuel death on the board is still inferred from a missing `DE`.

## bus3 speaks ARP, because nothing else could reach it (2026-09-08)

`arp -an` said `10.10.10.2 (incomplete)` on en8 for as long as the plane has
existed, so every Mac→board datagram — including the `P` ping and the new `R`
reboot command — died in the Mac's own stack before reaching the wire. The
module answered UDP and nothing else; a debug plane that can only be spoken to
by a peer that already knows its MAC is not reachable.

`debug_link.kotoba` now:

- asks for **10.10.10.1** once, at the end of `debug-init` (broadcast ARP
  request). A request addressed to the Mac is what makes a BSD stack record the
  sender; a gratuitous announcement for our own address only refreshes an entry
  that already exists, which is exactly the case that was missing. `debug-init`
  returns `16+n` when the ring is up but that request did not go out — the
  outbound half still works, so it is not a refusal to start, but it must not
  read as ready either.
- answers **ARP requests for 10.10.10.2** inside `debug-poll`, before the RX
  descriptor is re-armed (the reply is built from that buffer, and a re-arm
  hands it back to the NIC). `debug-tick` returns `16+n`, which the kernel logs
  after the `D9` sentinel like every other bus3 event.

Measured on this revision: `verify-store-tautology` 234 store forms / FINDINGS
0, `verify-wire-bytes` 70 emissions / 42 entries / FINDINGS 0, kernel builds
`AIUEOS_KOTOBA_NATIVE_KERNEL_OK … fuel=1048576`, QEMU smoke `MPRCD` / 33.
**Not yet measured on the board**: whether `arp -an` resolves and whether the
`P`/`R` round trip completes.

### The outbound half has never been seen either

`debug-init` reports ready and `debug-send` reports 0 — "the descriptor was
submitted AND the engine cleared OWN", i.e. bytes left the NIC — on every boot,
and the Mac's sink has received **two** datagrams in 21 hours, both of them the
rig check's own loopback controls from 10.10.10.1. The destination MAC in the
frame is correct (`3c:18:a0:d5:82:a8`, en8's own address, and the IPv4 header
checksum 0x52BA verifies), so the frame that leaves is addressed to a listener
that is up. The one `Z` per boot goes out immediately after `rings-start` has
reset the chip, which is the worst moment on a link that has just renegotiated.
The ARP request above is a second frame at the same moment; if neither is ever
seen while the ping reply (sent seconds later, in response to a packet that
arrived) is, the answer is link timing, not addressing.

## bus3 is not on en8's wire, and that is the whole story (2026-09-08)

Two silences, one cause, found by asking the PXE server what it hears:

```
AIUEOS_PXE_DHCP_RX      mac=70:70:fc:0b:b6:31 arch=7 vendor='PXEClient:...'
AIUEOS_PXE_DHCP_IGNORED mac=70:70:fc:0b:b6:31 expected=70:70:fc:0b:b6:32
```

`70:70:fc:0b:b6:31` is the board's SECOND NIC — bus3, the debug plane. Its DHCP
broadcasts are arriving at a socket the server binds with `IP_BOUND_IF` to
**en15**, the PXE wire. So bus3 is cabled to en15's segment, not to en8.

Everything follows:

- **board → Mac was never deliverable.** The frames are addressed to
  `3c:18:a0:d5:82:a8`, which is **en8's** MAC. On en15's wire that is neither
  en15's address (`80:69:1a:17:4f:15`) nor broadcast, so en15's NIC drops them
  before any IP stack sees them. `debug-send` reporting 0 was true: the bytes
  did leave the NIC.
- **Mac → board was never deliverable.** `10.10.10.0/24` is en8's, so the Mac's
  ARP for `10.10.10.2` goes out en8, where nothing answers. The ARP responder
  added earlier today is correct and still cannot help on that wire.
- The `Z` recorded on en8 in the Phase-1 census was measured when the cable
  was somewhere else. A cabling fact is not a property of the code, and this
  ADR carried it as one for two days.

### And it has now stopped the loop

With bus3's link up, the firmware tries to netboot from it. The server accepts
one MAC (`PXE_EXPECTED_MAC`, bus2's), so every bus3 attempt is ignored and the
board no longer reaches bus2: **0 boots and 0 TFTP in 150 s**, where the loop
had been running at ~1.2 boots/min since 09:02. The last image it fetched is
`fd0a0030` (236544 bytes); `efc5d540`, deployed 09:29, has never been served.

### The plane no longer depends on knowing which socket the cable is in

The baked-in peer MAC is gone. Unsolicited bus3 frames (the boot `Z`, the ARP
request) go to **broadcast**: every NIC on whatever segment bus3 is attached to
accepts them, and the Mac's stack delivers a datagram addressed to one of its
own IPs whichever interface it arrived on. Answers to commands go back to the
MAC the request came from — `debug-poll` copies it out of the request before
re-arming the descriptor, which is the only moment it exists. So the plane is
correct on either wire, and swapping cables can no longer silently disable it.

`verify-wire-bytes` earned its keep in the same commit: renaming the answer path
to `answer-byte` made three registered bytes (`p`, `r`, `?`) unreachable from
the scanner and it said so — `never-emitted`, one line each — instead of going
quiet. The registry's `:primitives` table now names both emitters.

Taken: the PXE server now accepts a LIST of client MACs and was restarted as
`AIUEOS_PXE_EXPECTED_MAC=70:70:fc:0b:b6:32,70:70:fc:0b:b6:31`
(`AIUEOS_PXE_NETLOG_PORT=7797` so it cannot compete with the standalone receiver
that owns 7777). It now answers the second NIC: `DHCP_OFFER mac=…b6:31
address=10.77.0.10`.

**And "root-only, never restart it" was wrong.** Measured: this user can bind
privileged UDP ports — a free one binds, and 67 returned `EADDRINUSE`, not
`EACCES`. The restart needed no sudo. That claim had stood in this ADR unmeasured
since the plane was built, and it shaped a day of work around an instrument
nobody was allowed to touch.

The board still does not boot. It answers the offer with another DISCOVER —
`arch=65535 vendor='MSFT 5.0'`, a plain DHCP client rather than the `PXEClient`
/ `HTTPClient` requests it sent minutes earlier — a few at a time, then goes
quiet for minutes. Both interface counters stay at zero between those bursts, so
it is not retrying anything on either wire. **It needs one power cycle**, and
the loop that exists to make the button unnecessary is what put the button back:
bringing bus3's link up is ours.

After the power cycle, whichever NIC the firmware picks now gets an offer, so
this particular stall cannot recur. What is still unmeasured — and what the
first boot will answer — is which interface the second NIC is actually on:
watch `en8` vs `en15` `Ipkts` across one boot. If the offers to `…b6:31` are
going out `en15` while that NIC listens on `en8`, the server must reply on the
interface the request arrived on, and that is the next fix.

## What bus3 is, measured until nothing was left to guess (2026-09-08)

Six measurements, each one removing a candidate, in the order they were taken:

| measured | result | rules out |
|---|---|---|
| `debug-init` / `debug-send` receipts | `B8 00`, `dbg-sent 00` | the ring is installed, the engine consumed every frame |
| Mac→board broadcast, **en8**, 199 datagrams over 5 boots | no `D9` | the board's RX is not seeing that wire |
| Mac→board broadcast, **en15**, 199 datagrams over 5 boots | no `D9` | nor that one |
| greeting to `10.10.10.1` **and** to `255.255.255.255` | both report sent, neither arrives | the ip_input rule about a unicast address in a broadcast frame |
| **MAC loopback self-test** (TxConfig 17\|18) | **0 — the frame came back** | the descriptors, the DMA addresses and BOTH engines are correct |
| `PHYstatus` on the wire (`DD 00 DD 93`) | **0x0093 = link up, 1000 Mbps, full duplex** | a PHY that had not finished negotiating after the reset |

The loopback is the one that matters: a frame handed back inside the MAC proves
every part of this module that we own. And 0x0093 proves the port has a live
gigabit link — a link needs a partner, so bus3 is plugged into *something*.

**What is left is physical.** That something carries nothing to or from this
Mac: neither the board's frames (broadcast, so no address can be wrong) nor the
Mac's (broadcast, on both of its interfaces). The one contrary datum — DHCP
requests bearing bus3's MAC reaching the PXE server — is a request the firmware
*composed* with that MAC, and says nothing about which port it left by.

So the ask is at the cable, not in the code: **the K16's second Ethernet port is
connected to something that is not the Mac's en8.** Everything else is ready and
measured — the kernel answers ARP and broadcasts its greeting, `debug-tick`
answers `P` and `R`, the sink listens on the wildcard so it will hear either
shape on either interface, and the PXE server accepts both NICs so the board can
boot from whichever port has a wire.

## LAN2 works. It was one transposed decimal literal. (2026-09-08)

```
(def k16-debug-ip 168493058)    ; 0x0A0A0A02
```

`0x0A0A0A02` is **168430082**. `168493058` is **10.11.0.2**. The peer constant
was wrong the same way (10.11.0.1), and the two baked header checksums were
computed from the addresses in the *comments*, so the frames and their checksums
could never agree. Every datagram this plane sent since it was written carried a
source address on a network that does not exist and was dropped by the Mac in
`ip_input`; every ARP request asked for 10.11.0.1, which nothing answers.

The frames were always arriving. `netstat -s -p ip` had been counting them the
whole time — **bad header checksums rose by exactly two per boot**, the two
greetings — and nobody had looked, because the board's own receipts all said
success and the Mac's sink said nothing, and neither side is where the drop is
recorded.

What found it: emitting the built IPv4 header on the bus2 netlog as `DD <byte>`
pairs.

```
45 00 00 1D 00 00 00 00 40 11 66 C5 0A 0B 00 02 FF FF FF FF
                                     ^^^^^^^^^^^ 10.11.0.2
stored checksum 0x66C5 · computed over those bytes 0x70C4
```

### Measured after the fix

| | before | after |
|---|---|---|
| `netstat -s -p ip` bad header checksums | +2 per boot | **+0** |
| bus3 greeting in the Mac's sink | never, in the plane's whole history | `from=10.10.10.2:9000 bytes=1 hex=42` — **every boot** |
| `arp -an` | `10.10.10.2 (incomplete)` | **`10.10.10.2 at 70:70:fc:b:b6:31 on en8`** |
| `P` → | nothing | **`hex=70` (`p`)**, netlog `D9 40` |
| `R` → | nothing | **`hex=72` (`r`)**, netlog `DB`, and the board reboots |

So LAN2 now carries what the owner asked for on 2026-09-08: debug output and
control, including reboot, on the second NIC — while bus2 carries PXE and the
stream experiment. The button is not in the loop for either plane.

### What the day cost, and what it is worth writing down

Six correct measurements were spent ruling out things that were never wrong —
the cabling (twice), the destination MAC, the IP shape, the rings, the DMA, the
PHY — and each of them produced a real improvement that stays: the plane now
speaks ARP, broadcasts what it starts, answers whoever asked, refuses to confuse
"polled, nothing there" with "never polled", and carries a MAC-loopback
self-test. But the defect was one digit, in a constant with the right value
written beside it in a comment.

The general lesson is not "check your constants". It is that **the drop was
counted on the third machine** — not by the sender, not by the receiver's
application, but by the receiving kernel's statistics, which neither end of a
two-sided debugging session thinks to read. `netstat -s` is the first place to
look the moment "it says it sent and nothing arrived", and it cost a day to
remember that.

## Status of the artifacts

- Commit `e09e4f1` (Phase 1 — bus3 single-shot) is superseded by commit
  `05a3142` for the census/window strategy. `05a3142` drops the unowned-page
  bus3-dma-pages binding and adds the census.
- Build on commit `05a3142`: `AIUEOS_KOTOBA_NATIVE_BOOT_OK no-c no-crt
  no-linker imports=0`, byte-identical reproducible, `boot 810e0523…`,
  207872 bytes, k16-preflight on.
- The census boot RAN on the K16 and answered `B7 7F 7F` (above). The serve
  dir's previous file hashed `810e0523…`, which confirms independently that
  the census EFI is what booted.
- Step 1 build: `AIUEOS_KOTOBA_NATIVE_BOOT_OK no-c no-crt no-linker
  imports=0`, byte-identical reproducible across two packagings,
  `boot 730b1293d930acd7030139d206c69b5bd1b54c1000c5bd5a437ed77b16f8bb80`,
  207872 bytes, k16-preflight on, `kernel_scratch.pages = 14`. Staged to
  `/tmp/aiueos-k16-pxe/BOOTX64.EFI`; the census EFI is kept beside it as
  `BOOTX64.CENSUS-810e0523.EFI`.
- Step 1 RAN (owner power-cycled the K16): `B7 7F 7F B8 00 00` on bus2 and
  `Z` on en8. The one-way LAN2 debug output is operational.
- Step 2 build (IPv4 total-length fix): `AIUEOS_KOTOBA_NATIVE_BOOT_OK no-c
  no-crt no-linker imports=0`, byte-identical reproducible,
  `boot c078201e7b1c3ee2e45a3de2a31e38f79054aa7e1a47e3b4e6c66fb114a8abf5`,
  207872 bytes, k16-preflight on. Staged; `BOOTX64.STEP1-730b1293.EFI` and
  `BOOTX64.CENSUS-810e0523.EFI` are kept beside it. **Not yet run** — it needs
  a power cycle, and nothing observable is expected to change, because the
  defect it fixes was masked by Ethernet padding at this payload size.
- Served since 2026-09-07 11:3x: `f039f387404fd48d…` (224256 bytes, kernel
  `dca9d47c…`, panel `AIUEOS K16 BUILD dca9d47c578b7f3b 964da2e`), kept beside
  the previous `BOOTX64.PREV-47b8c209.EFI`. Built twice bit-identically. Held
  in the session scratchpad, not served: `599e64a8…` (236544 bytes, note
  `079587e`) and `f6af155d…` (236544 bytes, note `d3a1466`). **None of the
  three has booted yet**; the board has been in `ud2` since the 47b8c209 run.
- The listener is `kbb --backend sci os/aiueos/tools/k16-bus3-sink.cljk` (pid 17394 since
  2026-09-07 11:43 JST, `nohup … >> /tmp/k16-bus3-sink.out`), writing
  `/tmp/k16-bus3-en8.log` by name on every datagram. It replaced `socat -u
  UDP-RECV:9000,reuseaddr OPEN:/tmp/k16-bus3-en8.log,creat,append`, whose
  single long-lived fd made every receipt unreadable once the file was
  unlinked (2026-09-07, pid 30661). `k16-rig-check.cljs` validates it with a
  control datagram before and after each reading; the socat shape is still
  recognised, so a rollback to it is measured rather than UNMEASURED. `tcpdump` remains unavailable (BPF needs root),
  so a frame the Mac drops in `ip_input` is still invisible; the bus2 send byte
  is what separates that case from a NIC that never transmitted.

## Consequences

- The screen "PREFLIGHT RTL8125" standing still must not be read as a hang.
- The original Phase-1 bus3 DMA (unowned window) was invalid; the census-first
  approach replaces it.
- bus2's `21` (peer sent nothing) deserves its own investigation into the
  aliasing of staging / tx-frame / rx-buffer-a.
- Honest ceiling: bus3 debug is not operational until the census reports the
  NIC can DMA and a loader-owned window backs it.