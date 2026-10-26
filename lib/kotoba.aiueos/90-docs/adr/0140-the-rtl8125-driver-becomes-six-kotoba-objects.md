# ADR-0140: The RTL8125 driver becomes six Kotoba objects, and a software model executes them

## Status

Accepted (2026-09-02)

## Context

`kernel/rtl8125.c` is 306 lines of C and `rtl8125.h` is 105 more. It is the only
way a diskless K16 node reaches anything: PXE hands the firmware-initialised NIC
over, this driver replaces the DMA rings, and everything above it -- ARP, DHCP,
TCP, TLS, the Murakumo worker -- travels through one transmit and one receive
descriptor it owns.

ADR-0015 draws the C boundary at MECHANISM. By that rule most of this file was
already on the wrong side of it. Which silicon revision this is, which receive
configuration word that revision wants, whether a MAC address may be used as a
station address, what makes a completed receive descriptor acceptable, in what
order the OWN bit and the doorbell become visible -- none of those is mechanism.
They are the decisions that determine which frames this machine accepts and
whether a frame that was handed to the hardware is ever sent.

The first K16 acceptance condition is that PCI/MMIO/DMA are emitted directly by
Amu rather than delegated to C. The port-I/O half of that landed with
`pci-config-read` / `pci-config-write`; the memory-mapped half needed widths and
barriers that did not exist. They exist now: `kernel-load-*`/`kernel-store-*` at
u8/u16/u32/u64 across four window tiers, `kernel-fence-load`/`-store`/`-full`,
and `kernel-rdtsc`.

## Decision

Six Kotoba objects, registered in kotoba-native's `kernel-object-entries`
(kotoba-native#118, both `elf64.clj` and `elf64.cljc`):

| object | arity | what it owns in `rtl8125.c` |
|---|---|---|
| `aiueos-rtl8125-identify` | 4 | `revision_from_txcfg` :130-138, `mac_valid` :146-150, the MAC assembly at :224-227 |
| `aiueos-rtl8125-link-up` | 2 | `aiueos_rtl8125_link_up` :254-257 |
| `aiueos-rtl8125-ring-build` | 5 | the descriptor stores of `rings_restart` :181-188, and all of `rx_rearm` :298-306 |
| `aiueos-rtl8125-program` | 5 | the MMIO half of `rings_restart` :169-202, including the FIFO drain |
| `aiueos-rtl8125-tx-submit` | 5 | `aiueos_rtl8125_tx_submit` :259-274 |
| `aiueos-rtl8125-rx-poll` | 2 | `aiueos_rtl8125_rx_poll` :282-296 |

Plus one shared module, `os/aiueos/kotoba/aiueos/lib/rtl8125_regs.kotoba`
(`mmio-ok`, `desc-ok`, `revision-of`, `receive-config`) -- the second import a
kernel object has made since amu#742 removed the refusal, after
`aiueos.lib.sha256-core`.

### Six objects, and the reason is not only the one-symbol rule

The qualification rows already say that a kernel object exports one symbol,
cannot call another, and takes at most five arguments. The reason that is
specific to a DRIVER is **region provenance**: `kernel-load-*` and
`kernel-store-*` take a literal, `kernel-boot-info` or an ARGUMENT as their
base, and nothing else. A port that kept device state in one struct and read the
BAR address back out of it could not be written at all -- the load would be
based on a computed value and the compiler refuses it.

So the BAR window, each descriptor and each frame address arrive as their own
argument, and the shape of the driver follows from that rather than from the
shape of the C. `struct aiueos_rtl8125_io`, the six-function-pointer vtable the
C reached its device through, has no counterpart: an object is handed the base.

### `aiueos-rtl8125-program`'s last argument is a phase and a revision at once

`rings_restart` runs stop -> drain -> clear -> BUILD THE DESCRIPTORS -> program
-> enable in one function, because it can call `bytes_zero` in the middle. An
object cannot call another object, so the caller has to interleave, and to
interleave it needs two entries.

Two entries need either two symbols or one argument that says which. The
argument that says which was already there: the program phase needs the
revision, the stop phase does not, and `revision-of` never returns 0. So
`revision = 0` is the stop phase and 1..4 is the program phase.

Building the rings before the stop, to avoid the two-phase call, is not the same
program. On a restart the ring registers still point at these descriptors and
the engine may still be running; rewriting a descriptor's address while the
hardware owns it is how a frame lands in a buffer the kernel has handed on.

### The drain has two bounds, and neither is value-scaled

The C spins a literal 300,000 times reading MCUCMD (:171-178). The port keeps
that budget -- so the two agree on when they give up, and so the object's cost
is closed form: 300,020 charged calls at the worst shape, which is what the
10,000,000 fuel tier is computed from -- and ADDS a `kernel-rdtsc` deadline of
2,000,000,000 ticks, because a spin count is not a timeout. The deadline can
only make the loop end earlier, so it does not move the fuel bound.

Both bounds are literals. A bound taken from an argument would make the fuel
bound a function of the caller, and a fuel bound that depends on the caller is
not a bound.

Measured from the emitted object: the drain is a `jmp` back-edge, not a `call`
(tail-self-recursion), so 300,000 iterations cost no stack. Each iteration
decrements the fuel word, so the tier is what actually bounds it.

### Return conventions are deliberately not uniform

Four objects are zero-is-success carrying the C's own
`enum aiueos_rtl8125_result` unchanged. `link-up` is a boolean, because the C
returned `int` and every call site is `if (!link_up(...))`. `rx-poll` returns a
NON-NEGATIVE frame length (FCS already subtracted, zero = still device-owned) or
a NEGATIVE reason: a length and a reason cannot share a non-negative value
space, and there is no room for the `uint32_t *` out-parameter the C used.

## How this was verified

### The KIR oracle can execute two of the six, and refuses the other four

`os/aiueos/contracts/rtl8125-identify-v1.edn` (11 vectors, 11 memory
assertions, all four reason codes) and `rtl8125-link-up-v1.edn` (6 vectors, 6
memory assertions, both verdicts) run under
`os/aiueos/scripts/verify-admissions.cljk` with no JVM, against a 4,096-byte
software model of the BAR seeded from the fixture
`os/aiueos/tests/rtl8125_handoff_model.c`:23-25 already uses.

The other four carry `kernel-fence-load` / `kernel-fence-store` /
`kernel-rdtsc`, and `kotoba.kir` refuses those with
`:kernel-privileged-unavailable` -- deliberately, and its own comment says why:
a barrier orders memory operations against a machine the interpreter is not
running on, and an oracle that executes one operation at a time would be
answering "the barrier worked" from something that never had the problem. That
is the right refusal. It still leaves four objects with no host-side evidence,
which is what the QEMU model is for.

Advancing the `:verify-admissions` alias was necessary and is part of this
change: at the pins it carried, `kotoba.compiler.frontend` had no entry for the
three operations at all, so `sema/analyze` refused the whole module with
`operation has no admitted type signature` and four objects could not be
LOWERED, let alone executed. `kotoba-sema` is now pinned to the SHA amu names at
the tip these objects are compiled with, so the frontend that admits a program
in the runner is the frontend that admitted the `.o`.

### QEMU has no RTL8125, so both implementations run against a model of one

`aiueos_rtl8125_kotoba_selftest` in `kernel/rtl8125.c` seeds 4,096 bytes of
memory so each register read returns what an RTL8125B returns at that point,
runs `aiueos_rtl8125_takeover` against it through an io vtable, records the
register file and both descriptors, re-seeds, runs the six objects, and compares
every byte. It then compares transmit submission, the TX_BUSY refusal, three
receive-completion cases, the rearm, and the FIFO-drain refusal.

Measured 2026-09-02 under `scripts/smoke-qemu-uefi.sh` (QEMU + OVMF), on the
serial console:

```
NIC-PARITY ok rtl8125 identify link-up ring-build program tx-submit rx-poll
```

That is the emitted x86-64 machine code executing, not an interpreter.

**Both directions shown, not asserted:**

| break | result |
|---|---|
| `receive-config` 8125B word `0x41000c0a` -> `0x41000c0b` | `NIC-PARITY mismatch stage=10 offset=68` -- offset 68 is 0x44, RGE_RXCFG |
| `stop-and-drain` clears RGE_CMD BEFORE draining instead of after | `NIC-PARITY mismatch stage=32 offset=0` -- the ordering assertion |
| `revision-of` 8125B constant off by one (oracle) | `:vector :rtl8125b-identified, :expected 0, :actual 2` |
| `mac-valid` multicast clause removed (oracle) | `:vector :multicast-mac-refused, :expected 3, :actual 0` |
| `identify` writes the MAC at out+4 instead of out+8 (oracle) | `:region :out` with both byte vectors printed |
| `link-up` masks bit 0 instead of bit 1 (oracle) | `:vector :link-bit-clear-with-other-bits-set, :expected 0, :actual 1` |

The object restored from backup recompiles to the same sha256
(`d2ad5895f0afe64c…` for `rtl8125-program.o`), so the breaks were the only
difference.

### What a memory model cannot see, said plainly

A memory model has no time in it, so the ORDER of two writes is invisible
whenever both survive to the end. Three things recover part of that and none
recovers all of it:

* The FIFO-drain stage seeds MCUCMD so the engine never reports empty. Both
  implementations must then return FIFO_TIMEOUT and must leave RGE_CMD at
  `0x8c` -- STOP set, not cleared. That is an ordering assertion, and it is the
  one the second break above fired.
* The TX_BUSY stage submits twice; the second must refuse, which is only true if
  the first set OWN before the doorbell.
* The store fences are checked as EMITTED BYTES rather than here --
  `rtl8125-ring-build.o` carries four `sfence` and `rtl8125-tx-submit.o` two
  plus one `lfence`. A fence writes no memory, so no memory comparison can ever
  see one.

### The pinned table, measured against the C while the C still exists

The self-test also checks the register file against a written-out table of the
21 fixed bytes, the four ring-address registers, both descriptors, and
"everything else is zero". It is checked against BOTH the C's result and the
objects' result in this commit, so on the day the C bodies delegate to these
objects -- when the parity comparison would become a comparison of one
implementation with itself -- the table is a claim that was measured against the
C rather than transcribed from the Kotoba.

## The C is flipped

`kernel/rtl8125.c`'s public API is unchanged and every body is now a call into
an object. What is left in C is the two things an object cannot do: hold the
struct (which pointers and physical addresses this device is using), and
sequence one object after another, which `rings_restart` needs because a kernel
object cannot call another one.

Measured, code lines only -- comments and blanks stripped:

| | before | after |
|---|---|---|
| `kernel/rtl8125.c` driver + ARP helpers | 262 | 182 |
| the six objects + the shared module | 0 | 182 |
| `kernel/rtl8125.c` parity self-test | 0 | 246 |

**The file got bigger, not smaller, and that is worth saying plainly.** The
driver lost 80 lines (-31%) -- twenty-five register `#define`s, the revision
table, the receive-configuration table, `mac_valid`, the MAC assembly, the FIFO
drain loop, every descriptor store, and the release and acquire fences -- and a
246-line self-test moved in. The self-test ships in every UEFI profile. It is
not a decision and it is not driver code, but it is C in the image, and the
honest accounting is 262 lines of driver replaced by 182 lines of driver and
182 lines of Kotoba, with 246 lines of evidence beside them.

`RGE_DESC_OWN` and `RGE_DESC_EOR` survive: `tx_complete` still reads the OWN
bit (one bit of one word with no decision in it, so it did not earn a seventh
export name) and the pinned table names both.

### What the flip cost elsewhere

* **The host model test could no longer link.** `smoke-rtl8125-handoff.sh`
  builds `rtl8125.c` with a HOST compiler, and a Kotoba kernel object is an
  `x86_64-aiueos-kernel-v1` ELF that an arm64 host cannot link. The driver and
  its self-test are now behind `#ifndef AIUEOS_RTL8125_ARP_ONLY`, which that
  script defines and no kernel build does; the model test keeps the two ARP
  helpers, which are still ordinary C. The register/descriptor half of it is
  gone, and the coverage it had is what `NIC-PARITY` covers -- against the
  emitted machine code rather than against a host recompilation of the source.
* **`native_pxe_test.clj` grepped `rtl8125.c` for `RGE_RX_SOF` / `RGE_RX_EOF`.**
  Those constants are named in `rtl8125-rx-poll.kotoba` now. The test reads that
  file for those two markers instead, because grepping the C for a constant it
  no longer uses is a marker that stays green by accident.

### The parity self-test changed shape, and the reason matters

Until the flip it ran the C driver and the objects against two copies of the
same seed and compared every byte. That comparison is gone, and not because it
stopped passing -- it stopped meaning anything, because `takeover` now calls the
same objects and the comparison would be between one implementation and itself.

What replaces it is the pinned table, which was written before the flip and
checked against the REAL C driver in the same boot. Everything else survives
unchanged in kind, because none of it was ever a C-versus-Kotoba comparison: a
submission that must set OWN before the doorbell, a second submission that must
therefore refuse, four receive-completion verdicts, a rearm, a FIFO that never
drains, and three argument refusals.

Both directions shown on the flipped build:
`receive-config` 0x41000c0a -> 0x41000c0b produces
`NIC-PARITY mismatch stage=36 offset=68`, and restoring it recompiles
`rtl8125-program.o` to the same sha256 and returns `NIC-PARITY ok`.

## What is NOT done

* **`kernel/pci.c`'s RTL8125 section is untouched.** The six MMIO accessors
  (`rtl_mmio_read8`/`write32` and their siblings, :3935-3952) are now dead: the
  driver no longer calls the vtable it fills in. They are left in place because
  the header still declares the vtable and `io_valid` still requires it, and
  removing them means touching a 5,400-line file three other streams are
  editing concurrently. The frame builders above them (`rtl8125_build_direct_arp`
  and the UDP/TCP/TLS path) are a different job.
* **Nothing has run this on real RTL8125 silicon.** The physical qualification
  path in `pci.c` calls the same public API, so the K16 nodes would exercise the
  objects the next time one boots -- but no such boot has happened, and a
  software model of a device is not the device. The register sequence, the
  descriptor layouts and the FIFO drain are transcriptions cross-checked against
  a fixture; the first real proof is a K16 node completing its ARP exchange.
* **No live network exchange.** QEMU models no RTL8125, and this change does not
  port the virtio-net path (`pci.c`:3792) to Kotoba, so there is no DHCP or ARP
  round trip behind these objects. The physical qualification on the K16 nodes
  is unchanged in shape and now runs these objects the next time it boots.
* **Four of the six have no host-side oracle**, for the reason above. If
  `kotoba.kir` ever grows a mode that models barriers as no-ops, the four
  contracts are worth writing then.
* **`tx_complete` and `io_valid` stay in C.** The first is `!(command & OWN)`
  and the second is a null check over a vtable the objects do not use.
* **The frames in the self-test are 64 bytes**, not
  `AIUEOS_RTL8125_FRAME_CAPACITY`: nothing reads them, only their addresses
  matter, and 4 KiB of `.bss` for a buffer nothing touches is 4 KiB the kernel
  does not have.
