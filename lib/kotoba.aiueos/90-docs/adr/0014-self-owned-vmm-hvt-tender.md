# ADR-0014 — Self-owned VMM ("hvt tender"): owning the hypervisor side of aiueos virtualization

- Status: **accepted** — 2026-07-17 owner decision; option C **V0 landed
  2026-07-17** (`aiueos.hvt`, verified on real KVM — see "V0 — landed" below),
  options B/D stay live until the V2 checkpoint
- Date: 2026-07-17 (proposed and accepted same day)
- Deciders: Jun Kawasaki
- Scope-out origin: ADR-0011 Phase 1 ("a separate, multi-week project-scale
  ADR of its own — not attempted in this pass"). This is that ADR.

## Context

### 1. Every virtualization path in this stack today *consumes* an external VMM

`aiueos.vm` plans and launches **QEMU** (`accel=hvf` on macOS, `kvm:tcg` on
Linux). ADR-0008/0011/0013 all use QEMU as the boot-evidence oracle; ADR-0013's
release gates say "successful QEMU boot is the minimum evidence." ADR-0010's
`computer:vm` surface names a **Parallels/QEMU microVM** backing — still future
work, and also a consumer. A 2026-07-17 workspace-wide search confirms nothing
in `kotoba-lang` or `cloud-itonami` implements the monitor side of
virtualization: we boot *inside* VMs; nothing of ours *hosts* one.

### 2. The vocabulary and the named gap

Superproject ADR-2607022400 (accepted 2026-07-02) adopted the Solo5 split:
**tender** = the deliberately non-sandboxed native mediator (`hvt`
hardware-virtualized, `spt` seccomp-sandboxed); **guest** = aiueos wasm
components. It flagged the actual `hvt` tender as unstarted. ADR-0011 Phase 0
delivered the *hosted-Linux* tender (PID 1 + VFIO); its Phase 1 explicitly
deferred the hardware-virtualized piece — "a minimal native boot stub (CPU mode
setup, memory map, hypervisor-guest trap handling)" — to a project-scale ADR.
ADR-0013 then settled the **guest** side: aiueos owns the bootable product,
`kotoba-lang/compiler` owns freestanding targets, bare-metal kernel Phases 1–6
are underway. The **host/VMM** side remains the only undesigned layer.

### 3. Precision: "hypervisor 自作" means the tender/VMM, not a type-1 hypervisor

In the Solo5 framing the *hypervisor* is the OS's virtualization facility —
Linux **KVM** (`/dev/kvm`), macOS **Hypervisor.framework** (HVF). The *tender*
is the small userspace VMM that creates the VM, maps guest RAM, loads the guest
image, runs vcpus, and services exits. Parallels Desktop and VMware Fusion on
modern macOS are exactly this shape (userspace monitors over Apple's
hypervisor APIs). What is on the table here is a **self-owned tender/VMM**
riding KVM/HVF — never a from-scratch type-1 hypervisor (firm non-goal, §
Non-goals).

### 4. Constraints inherited from the superproject (owner rules)

- **No new Rust/C crates** to fill app-level gaps (owner rule 2026-07-10).
  ADR-0011 already noted the one arguable exception: *adopting* upstream
  Solo5's existing `hvt` (consuming a public, minimal C substrate, not
  authoring one).
- **Runtime priority** kotoba wasm > clojurewasm > ClojureScript > nbb, with
  JVM as a last-resort *compat layer* for hardware access. The established
  precedent is `aiueos.vfio`: raw `ioctl`/`mmap` from Clojure via
  `java.lang.foreign` (FFM) — "clj on clj."
- New scripts/harnesses are nbb `.cljs`, never `.sh`/`.mjs` (owner rules
  2026-07-14 / ADR-2607100100 M2).

### 5. What a minimal VMM actually is (scope reality check)

Open the facility (`/dev/kvm` ioctls: `KVM_CREATE_VM`,
`KVM_SET_USER_MEMORY_REGION`, `KVM_CREATE_VCPU`, mmap'd `kvm_run`, `KVM_RUN`;
HVF: `hv_vm_create`/`hv_vm_map`/`hv_vcpu_run`), map guest RAM, load the guest
image, set initial vcpu state (or run firmware), then loop servicing exits —
PIO/MMIO (the virtio transport), halt/shutdown, IRQ injection. The guest-side
entry contract (load ELF/PE, long-mode setup, boot-info handoff) is precisely
ADR-0011's deferred "native boot stub." Note the symmetry dividend: the
portable virtio *protocol* logic ADR-0011 ported to CLJC (queue layout,
descriptor validation) is the same logic a device model needs — one codebase
can drive both the guest and the host side of the queue.

## Options

**A. Status quo — QEMU only.** Zero new code; battle-tested device models;
but the largest possible TCB for the job, an external binary dependency, no
ownership of the layer ADR-2607022400 named, and `computer:vm` (ADR-0010)
stays hostage to Parallels/QEMU availability.

**B. Adopt upstream Solo5 `hvt`.** Existing, minimal, public C tender —
consuming, not authoring, native code (the carve-out ADR-0011 pre-argued).
But: Solo5 defines its *own* guest boot/hypercall ABI, which is not the
ADR-0013 kernel's UEFI/BIOS entry contract — making the aiueos kernel a Solo5
guest, or teaching `hvt` to direct-load our kernel, is C authorship in all but
name. Upstream `hvt` targets Linux/KVM and the BSD `vmm` APIs; no maintained
macOS/HVF backend as of this writing.

**C. Self-authored FFM tender — `aiueos.hvt` (Clojure, JVM-FFM).** The
`aiueos.vfio` technique applied one layer down: FFM downcalls against
`/dev/kvm` first (Linux), HVF later. Pros: satisfies the no-new-Rust/C rule
outright; plan-as-data + exit-log receipts fall out of the existing aiueos
discipline (`aiueos.vm` plans, ADR-0001 audit); virtio protocol logic is
already in CLJC. Cons: a JVM sits in the vcpu exit loop — acceptable for boot
gates and `computer:vm` interactive fidelity, not yet argued for production
I/O paths; macOS HVF requires the `com.apple.security.hypervisor` entitlement
codesigned onto the JVM binary (a real operational wrinkle — Linux-first);
greenfield systems code with all that implies.

**D. Compiler-emitted native tender.** Once `kotoba-lang/compiler` freestanding
targets (ADR-0013) mature, a native *userspace* target is strictly smaller
than a kernel target; the tender could eventually be kotoba-emitted. Farthest
out; not startable today.

## Decision (accepted 2026-07-17)

Phased, Linux/KVM-first, with option C as the spike vehicle and B/D as
checkpointed alternatives:

- **V0 — KVM spike (`aiueos.hvt`, JVM-FFM):** boot a minimal test guest (a
  few hundred bytes of long-mode code writing to the serial port) via
  `/dev/kvm`; then direct-load the ADR-0013 kernel image, implementing the
  boot-info handoff as data. Gate: the tender boots the same image QEMU boots
  and produces the same first-N serial bytes, with a run receipt.
- **V1 — device model:** virtio-console + virtio-blk backed by the ADR-0011
  CLJC virtio protocol logic (host side of the same queues). Gate: ADR-0008's
  block/console smoke passes under `aiueos.hvt` as it does under QEMU.
- **V2 — checkpoint:** measure V1 against adopting Solo5 (B) and the compiler
  trajectory (D); decide whether to proceed to a macOS/HVF backend and whether
  ADR-0010's `computer:vm` backing rides `aiueos.hvt` or stays
  Parallels/QEMU. QEMU remains the CI evidence oracle for ADR-0013 gates
  until the tender demonstrably reproduces them.

Verification harnesses are nbb `.cljs`; every phase lands with plan-as-data,
run receipts, and audit events (no screenshot-only or file-shaped evidence,
per ADR-0013's own standard).

### V0 — landed 2026-07-17

`src/aiueos/hvt.cljk` implements the option-C tender; `test/aiueos/hvt_test.cljk`
unit-tests the pure parts (ioctl-number encoding, kvm_run/memory-region struct
offsets, the aarch64 PC core-reg id `0x6030000000100040`, the fixed guest
program) on any JVM host; `scripts/hvt-smoke.cljk` (nbb) is the live gate.

Verified end-to-end on a **real** `/dev/kvm` (Apple M4 → Lima `vz`
nested-virtualization → aarch64 Ubuntu 26.04). The VMM creates a VM, maps 2 MiB
of guest RAM at GPA 0, loads a 10-word aarch64 guest, inits the vcpu
(`KVM_ARM_PREFERRED_TARGET` → `KVM_ARM_VCPU_INIT`), sets PC via
`KVM_SET_ONE_REG`, and runs the `KVM_RUN` loop. The guest writes `HI\n`
byte-by-byte to an MMIO serial port — each `strb` traps out as
`KVM_EXIT_MMIO`, reconstructed by the tender — then writes a poweroff MMIO port
for a controlled halt. Run receipt:

```edn
{:api-version 12 :serial "HI\n" :serial-ok? true
 :exits [{:reason :mmio :phys-addr 0x9000000 :char \H}
         {:reason :mmio :phys-addr 0x9000000 :char \I}
         {:reason :mmio :phys-addr 0x9000000 :char \newline}
         {:reason :poweroff :phys-addr 0x9000008}]
 :shutdown? true :halt :mmio-poweroff :steps 4}
```

Gate met: the self-owned VMM boots a guest, serial appears via MMIO traps to
the tender, and it halts cleanly — no QEMU in the path.

One finding worth recording: PSCI SYSTEM_OFF (`hvc #0` with `0x84000008`) did
**not** raise a `KVM_EXIT_SYSTEM_EVENT` for this bare, MMU-off, no-vector-table
guest — the `hvc` returned into the guest, which then spun with `KVM_RUN`
blocking in-kernel (confirmed by `strace`: three `KVM_RUN`s returned for the
serial writes, the fourth blocked). V0 therefore halts via an MMIO poweroff
port (the shape kvmtool/QEMU test devices use), which rides the exit path
already proven working. A real PSCI clean shutdown moves to V1, where the
guest is the ADR-0013 kernel (which sets up its own EL1 vector table and can
issue PSCI properly), not this hand-written stub.

### V1 progress — 2026-07-17 (two hard findings)

Work continued toward V1's next items (real PSCI SYSTEM_OFF; ADR-0013 kernel
direct-load). Two constraints were established empirically and shape the
remaining V1 path.

**Finding 1 — kernel direct-load needs an x86_64 KVM host, which the dev
machine is not.** The ADR-0013 native kernel (`os/aiueos/kernel/`) is
**x86_64-only**: AT&T x86 assembly (`%rsp`/`%rip`, `entry.S`), Intel VT-d
(`vtd.c`), `BOOTX64.EFI`, and its smoke path is `qemu-system-x86_64 -machine
q35 -cpu max` under **TCG** (emulation). KVM is arch-native — an **aarch64**
host (Apple M4 → Lima) can only run **aarch64** guests, so it cannot boot the
x86_64 kernel under `aiueos.hvt`. Direct-loading the real kernel therefore
needs an x86_64 machine with `/dev/kvm` (a native x86 Linux box or an
x86_64-KVM cloud instance). The tender's ELF-load + boot-info-handoff logic is
arch-independent and can be authored now; only the live gate is gated on
x86 hardware. (An `aarch64-aiueos-kernel` target is named as future work in
ADR-0013 but not yet built; when it exists, this same aarch64 KVM host boots
it directly.)

**Finding 2 — PSCI SYSTEM_OFF does not fire for a hand-written bare guest**
(initial, partially-wrong hypothesis; corrected below). First observed via
`aiueos.hvt/guest-program-psci` (serial `HI\n` → `hvc #0` with `0x84000008` →
poweroff fall-through): the guest emits the three serial bytes, then `KVM_RUN`
blocks in-kernel at the `hvc`, reaching **neither** a `KVM_EXIT_SYSTEM_EVENT`
**nor** the fall-through poweroff. The first pass guessed KVM was injecting an
exception the vector-table-less guest spun on, and that the `KVM_ARM_VCPU_PSCI_0_2`
feature bit was counterproductive because "this KVM already defaults to PSCI
0.2+." A later pass **disproved both parts of that guess** — see the correction.

Landed this pass (verified on the aarch64 KVM host): `spike` parametrized over
a guest program (`{:program …}`), the PSCI diagnostic guest + its
encoding/feature-bit unit tests (`aiueos.hvt-test`: 7 tests / 41 assertions,
all green on any JVM host), a `kbb -M:hvt psci` diagnostic entry (documented
as intentionally blocking — run under `timeout`), and `KVM_ARM_VCPU_INIT`
return-code checking. The default (poweroff) path and `scripts/hvt-smoke.cljk`
gate remain green. (Repo-wide `kbb -M:test` is 279 tests / 802 assertions;
the single error is a pre-existing `decide-subprocess-smoke-test` shelling to
`kbb -M:decide` on the host — untouched by this change and unrelated to `hvt`.)

### V1 progress — 2026-07-17 (ELF64 direct-loader, the arch-independent half)

Finding 1 above blocks booting the *x86_64* ADR-0013 kernel on this aarch64
host, but the **loader itself is arch-independent and is now built and verified
end-to-end** — the reusable half of "direct-load the kernel image."

- **Pure ELF64 parser** (`parse-elf64` / `rd-le` / `elf-load-range`, testable on
  any JVM host): validates the magic/`EI_CLASS`/`EI_DATA`, reads `e_machine`/
  `e_entry`/`e_phoff`/`e_phentsize`/`e_phnum`, and returns the PT_LOAD segments
  (`{:offset :vaddr :filesz :memsz}`) plus the page-aligned load window.
- **`spike` generalized via `boot-plan`**: accepts `{:elf-bytes <byte[]>}` as an
  alternative to `{:program …}`. It maps guest RAM at the ELF's load base (an
  **arbitrary** GPA — the fixture links at `0x40000000`, exercising the
  non-zero-base path the raw-word guest never did), copies each PT_LOAD segment
  to its `vaddr`, and sets PC = `e_entry`.
- **Real fixture, not synthetic**: `resources/hvt/guest-aarch64.elf` is a genuine
  `ld`-produced aarch64 ELF (source `guest-aarch64.S` + `guest-aarch64.ld`,
  reproducible via `scripts/build-hvt-guest.cljk` — nbb, `--build-id=none -s`
  for a byte-deterministic blob, SHA pinned). It writes `HI\n` to the serial
  MMIO port then the poweroff port, same as the raw guest.

Verified on real KVM: `kbb -M:hvt elf resources/hvt/guest-aarch64.elf` boots
the ELF and returns `{:serial "HI\n" :serial-ok? true :shutdown? true :steps 4}`.
`scripts/hvt-smoke.cljk` now gates **both** cases (raw-word V0 + ELF V1) and the
reproducibility build passes byte-identical. `aiueos.hvt-test` is 11 tests / 57
assertions (adds `rd-le`, `elf-load-range`, a bad-magic rejection, and a parse
of the real fixture). What remains for the kernel path is purely the x86_64 KVM
host (Finding 1) and the kernel's own boot-info/entry contract; the ELF-loading
mechanism is done.

### V1 progress — 2026-07-17 (virtio-mmio device model, transport handshake)

The tender now **presents an emulated device to the guest**, not just serial
and poweroff ports — the first reuse of `aiueos.virtio`'s host-side logic
("direct-load the ADR-0013 kernel image" and "a virtio device model reusing
`aiueos.virtio`" are the two open V1 items; this is the second).

- **MMIO *read* emulation**: `service-mmio!` now also decodes the full
  little-endian write value, and the loop answers guest MMIO *reads* by writing
  the device's register value back into `kvm_run.mmio.data` before re-entering
  `KVM_RUN` (`set-mmio-data!`). Previously the tender only observed writes
  (serial/poweroff); a device the guest can *probe* needs reads.
- **`virtio-console` device model** (`virtio-console-read`/`-write`, pure and
  host-tested): a register state machine over `aiueos.virtio/mmio-reg` +
  `mmio-magic`/`mmio-version-2`/`device-type-id`/`device-status-bit`/
  `features-version-1`. It answers the identity registers (magic `0x74726976`,
  version 2, device-id 3 = console, `VIRTIO_F_VERSION_1` offered), tracks the
  feature selectors and the device `status`, and returns `status` on read so
  the driver's FEATURES_OK-stuck check passes. The guest drives it through a
  virtio-mmio register window at GPA `0x0a000000` (unbacked → every access
  traps to the tender).
- **Real driver guest** `resources/hvt/guest-virtio-aarch64.S` → `.elf`
  (loaded by the V1 ELF loader): probes magic/version/device-id, runs the
  `ACKNOWLEDGE → DRIVER → (feature offer/accept) → FEATURES_OK → DRIVER_OK`
  handshake, and emits `HI\n` **only** if every step succeeds (else `E`) — so a
  receipt serial of exactly `HI\n` is a self-verifying proof the whole
  transport handshake ran. Reproducible byte-identical via
  `scripts/build-hvt-guest.cljk` (now builds both guests, SHA-pinned).

Verified on real KVM: the 21-step trace shows 17 virtio register accesses
(3 identity reads, the status/feature writes, the FEATURES_OK read-back, and
DRIVER_OK) then the `HI\n`+poweroff, returning `{:serial "HI\n" :serial-ok?
true :virtio-status 15 :shutdown? true}` (`0xf` = DRIVER_OK). `hvt-smoke.cljs`
now gates all three cases (raw / ELF / virtio); `aiueos.hvt-test` is 14 tests /
75 assertions (adds the window predicate, device-read identity/feature, and the
status-handshake read-back).

**Scope line**: this is the virtio-mmio *transport* (registers + status +
feature negotiation). The **virtqueue data path** — avail/used rings and
descriptor-chain DMA, where `aiueos.virtio/split-queue-layout`/`*-ring`/
`validate-descriptor-chain` and reading guest RAM come in — is the next
milestone (#110). Queue-config register writes are already tracked in the
device state, unacted-on, ready for it.

### V1 progress — 2026-07-17 (virtqueue data path — a guest transmits through the split queue)

The device now moves **data**, not just handshake registers: a guest driver
sets up a split virtqueue in guest RAM and transmits `HI\n` through the
virtio-console transmitq; the tender reads the ring + descriptor chain out of
guest RAM and pulls the bytes. This completes the virtio device model and is
the first time the tender reads/writes **guest RAM**.

- **Guest-RAM access** in the tender: `gram-rd` (a `gpa -> byte` accessor over
  the mapped `ram` segment) and `gram-set-le!` (write N little-endian bytes to
  a GPA). The KVM loop passes `ram`/`ram-gpa` into the notify handler.
- **Pure split-queue servicing** (`read-descriptor` / `walk-descriptor-chain` /
  `virtqueue-plan`, host-tested with synthetic RAM): parses 16-byte descriptors,
  walks `next`-chains collecting the device-*readable* buffers (skipping
  device-writable/receive buffers via `aiueos.virtio/desc-flag`), and returns a
  plan — the emitted bytes, the used-ring elements `{:slot :id :len}`, and the
  new used/avail indices — for the FFM side to apply. `process-virtqueue!` runs
  the plan against real guest RAM and writes the used ring back.
- **Per-queue config**: `virtio-console-write` now routes the queue-address
  registers (`QueueDesc/Driver/Device` low+high, `QueueNum`) into the selected
  queue's sub-map keyed by `QueueSel`; `queue-config` resolves the 64-bit ring
  addresses on notify.
- **A stack for C guests**: the tender now sets SP (core reg `0x3E`) to the top
  of the guest RAM window, so the driver guest could be written in freestanding
  C (`guest-virtqueue-aarch64.c`) rather than hand assembly — the virtqueue
  setup is far clearer in C. Built via `scripts/build-hvt-guest.cljk` (now
  handles both `as` and `gcc`; the C guest's SHA is pinned for gcc 15).
- **Two-way RAM coherency confirmed**: the guest writes the rings/buffer with
  its MMU off (non-cacheable), the tender reads them (`emitted "HI\n"`), the
  tender writes the used ring, and the guest reads the completion back — both
  directions coherent on this KVM (the earlier dcache worry did not materialize;
  KVM's stage-2 flush-on-fault handles it).

Verified on real KVM (31-step trace): transport handshake, queue-1 setup
(desc/avail/used addresses, `QueueReady`), one `NOTIFY` where the tender emits
`HI\n` pulled from the transmit buffer via the descriptor, then the guest — on
seeing the used-ring completion — confirms on the plain serial port and halts.
Receipt: `{:console "HI\n"` (data through the virtqueue) `:serial "HI\n"` (guest
saw completion) `:virtio-status 15 :shutdown? true}`. `hvt-smoke.cljs` now gates
four cases (raw / ELF / virtio transport / virtqueue), the virtqueue one
asserting `:console`; `aiueos.hvt-test` is 17 tests / 87 assertions (adds
per-queue config, descriptor-chain walk incl. writable-buffer skip, and
transmit servicing on synthetic RAM).

One instructive bug: gcc `-O2` first emitted the guest's serial write as a
**post-index** `strb w,[x],#1` — an MMIO store whose access has no decodable
instruction syndrome on aarch64, so `KVM_RUN` failed `ENOSYS`. Writing each byte
to the single serial-register address (as a data port is used, and as the asm
guests already did) restored a plain `strb w,[x]` KVM can emulate. Recorded
because it will recur for any C guest doing MMIO through advancing pointers.

With this, the two open V1 items — kernel direct-load and the virtio device
model — are both substantially delivered: the ELF loader boots real images
(kernel-specific boot waits only on x86_64 KVM hardware, Finding 1), and the
virtio-console device now does transport **and** a full virtqueue transmit.

### V1 progress — 2026-07-17 (virtqueue receiveq — the device→guest direction)

The console is now **bidirectional**: the mirror of the transmit path. On a
receiveq notify (queue 0, per the virtio-console port-0 layout) the device
*fills* the driver's buffers instead of reading them — exercising the
device-**writable** descriptors the transmit path deliberately skipped.

- **Pure receive servicing** (`walk-writable-chain` / `fill-targets` /
  `virtqueue-rx-plan`, host-tested): walks the chain collecting device-writable
  `{:addr :len}` targets (WRITE flag set), spreads the input across them up to
  capacity, and returns the guest-RAM byte writes plus the used-ring completion
  carrying the count written. `process-virtqueue-rx!` applies the buffer writes
  and the used ring back to guest RAM.
- **Queue routing**: the notify handler dispatches by queue index — queue 1
  (transmitq) reads into `:console` (prior milestone), queue 0 (receiveq)
  delivers `virtio-console-rx-input` (`"HI\n"`, the stand-in for host→guest
  console input) into the driver's writable buffer.
- **Real receive guest** `guest-virtqueue-rx-aarch64.c` → `.elf`: posts one
  device-writable buffer on queue 0, notifies, polls the used ring, reads the
  delivered length, and echoes the received bytes to the serial port —
  reproducible byte-identical (`build-hvt-guest.cljs` now builds four guests).

Verified on real KVM (31-step trace): handshake → receiveq setup → one `NOTIFY`
where the tender writes `HI\n` into the guest's buffer and completes it → the
guest reads it back and echoes `HI\n` to serial → halt. `hvt-smoke.cljs` now
gates five cases (raw / ELF / transport / tx / rx); `aiueos.hvt-test` is 20
tests / 100 assertions (adds the writable-chain walk, `fill-targets`, and
receive servicing incl. capacity truncation). The virtio-console device model
is now complete in both directions.

### V1 progress — 2026-07-17 (PSCI finding, corrected with return-code evidence)

A focused probe pass **corrected Finding 2**. The earlier explanation (KVM
injects an exception; the vcpu already has PSCI 0.2+) was wrong on both counts.
By reading the `hvc` return value in `x0` (a minimal guest: `hvc #0` then
`strb w0,[serial]`, so the receipt's first serial byte is the low byte of the
PSCI return code) the actual behavior is now pinned down:

- **KVM does not implement the standard PSCI function IDs on this environment.**
  `PSCI_VERSION` (`0x84000000`), `SYSTEM_OFF` (`0x84000008`), `SYSTEM_RESET`
  (`0x84000009`), and `CPU_OFF` (`0x84000002`) **all** return `0xFFFFFFFF`
  (`PSCI_RET_NOT_SUPPORTED`, low byte `0xff`) and **resume** the guest. So the
  `hvc` does *not* shut the VM down and does *not* raise `KVM_EXIT_SYSTEM_EVENT`
  — it returns NOT_SUPPORTED and the guest runs on. (The original "block" was
  just the bare guest running into zeros after that resume; a guest with a
  poweroff instruction after the `hvc` halts cleanly in 1 step.)
- **The `KVM_ARM_VCPU_PSCI_0_2` feature bit does not fix it, and has a side
  effect.** With the bit set, `KVM_ARM_VCPU_INIT` succeeds but leaves the **boot
  vcpu in `MP_STATE_STOPPED` (5)** — so `KVM_RUN` blocks (that was the earlier
  "regression before any serial", now explained). Forcing `MP_STATE_RUNNABLE`
  via `KVM_SET_MP_STATE` unblocks it, but `SYSTEM_OFF`/`PSCI_VERSION` **still**
  return NOT_SUPPORTED. So the feature bit changes vcpu power state, not PSCI
  support, on this KVM.

**Corrected conclusion**: a clean PSCI `SYSTEM_OFF` shutdown-exit is
**unavailable on this KVM environment** (Linux/KVM inside the Lima VM), not
because the guest lacks EL1 vectors, but because KVM answers every PSCI call
`NOT_SUPPORTED`. The MMIO poweroff port remains the correct, working halt
mechanism for V0/V1. (A real x86_64 or a different aarch64 KVM may implement
PSCI; that is the same hardware/environment gate as Finding 1, not a design
gap.) One unresolved curiosity: a `hvc` that follows prior MMIO exits spins
in-guest rather than resuming like a fresh `hvc` — noted, not load-bearing,
since PSCI is NOT_SUPPORTED either way.

Landed: `KVM_GET_MP_STATE`/`KVM_SET_MP_STATE` ioctls + `mp-state` constants
(real vcpu power-state control — infrastructure for SMP later) and a
`:psci-0-2?` spike option (sets the feature bit and forces the vcpu RUNNABLE;
a documented diagnostic, off by default). `aiueos.hvt-test` is 18 tests / 92
assertions (adds the MP_STATE ioctl numbers and the SP core-reg id).

### V1 progress — 2026-07-17 (kotoba-first guest: written in Kotoba, not asm/C)

The earlier guests were AArch64 asm/C, with the reasoning "kotoba can't target
this arch." That was **wrong** — `kotoba-lang/compiler` already has an AArch64
backend; it only lacked a *bare-metal kernel* target. Rather than accept asm/C,
the guest is now written in the **Kotoba language** and compiled to a
freestanding AArch64 ELF, matching the repo's kotoba-first rule and the
`.kotoba`-native ADR-0013 kernel.

- **Compiler** (`kotoba-lang/compiler`, merged `e5e278a`): a new
  `aarch64-aiueos-kernel-v1` target (mirrors `x86_64-aiueos-kernel-v1`) —
  `kernel-store-u8`/`load-u8` bounded MMIO intrinsics in the AArch64 backend, an
  `EM_AARCH64` ELF packager with an AArch64 entry-shim (sets the hidden `x7`
  fuel/capability context, calls `main`, parks), and the verifier admitting the
  kernel intrinsics for the target. Full compiler suite 187 tests / 3050
  assertions green; x86_64 codegen unchanged (the three `os/aiueos` native build
  scripts' pinned compiler SHA advanced to `e5e278a`, output byte-identical).
- **Guest** `resources/hvt/guest-serial.kotoba` → `guest-serial.elf`
  (reproducible via `scripts/build-hvt-kotoba-guest.cljk`): a `(defn main …)`
  that writes `HI\n` to the serial MMIO port then the poweroff port. Because
  Kotoba is pure, ordered side effects thread each store's return value into the
  next store's index (`(- token value)` = 0) so none are dead-code-eliminated.
- **Tender fix (load-bearing bug):** the guest boots at **EL1h**, so it uses
  **SP_EL1**; the tender was setting **SP_EL0** (`user_pt_regs.sp`, core-reg
  `0x3E`), which a stack-using guest never sees — its first `str x29,[sp]` faulted
  and the vcpu spun. Fixed to set SP_EL1 (core-reg `0x44`). This was latent: the
  asm/C guests were leaf functions with no frame; the compiled Kotoba prologue
  pushes fp/lr immediately. (Also recorded: the AArch64 MMIO access must use
  base-register addressing — register-offset `[x1,x3]` leaves ESR `ISV=0` so KVM
  cannot emulate the device store — fixed in the compiler intrinsic.)

Verified on real KVM: `kbb -M:hvt elf resources/hvt/guest-serial.elf` boots
the Kotoba-compiled AArch64 guest and returns `{:serial "HI\n" :serial-ok? true
:shutdown? true :halt :mmio-poweroff}`. The guest path is now kotoba-first; the
remaining asm/C guests (virtio transport/tx/rx) can migrate to `.kotoba` on this
foundation as follow-up.

### V1 progress — 2026-07-17 (Kotoba virtio probe: u32 MMIO in Kotoba)

Migrating the virtio guests to Kotoba needs **32-bit** MMIO — virtio-mmio
registers are `u32`, and the byte intrinsics can't drive them. So the compiler
(`kotoba-lang/compiler`, merged `82543fa`) gained `kernel-load-u32` /
`kernel-store-u32` bounded-MMIO intrinsics on the AArch64 kernel backend (same
discipline as the byte ops, but the 4-byte access must fit: `index+4 ≤ length`).

`resources/hvt/guest-virtio-probe.kotoba` → `.elf` is the first Kotoba guest to
touch the **emulated virtio-console device** (reusing `aiueos.virtio`'s register
map): it reads `MagicValue` (`u32`), and on `0x74726976` writes `Status = 0xf`
(`u32`) and reads it back (`u32`), emitting `HI\n` iff both the magic and the
status round-trip hold. Verified on real KVM (trace: `virtio READ reg 0x0 ->
0x74726976`, `virtio WRITE/READ reg 0x70 = 0xf`, then `HI\n` + poweroff;
receipt `:serial "HI\n" :serial-ok? true`). `hvt-smoke.cljs` now gates **7
cases**; the compiler suite is 187 tests / 3058 assertions.

Noted for follow-up: the compiler **inlines `let` bindings** (no CSE), so a
binding referenced twice re-evaluates its expression — for a side-effecting MMIO
op that means a duplicated access (the probe's status write/read runs twice,
harmless because idempotent). A guest where duplication matters must reference
each binding once, or the compiler needs binding materialization. And the full
virtio *transport handshake / virtqueue* guests (feature negotiation, ring DMA)
remain to migrate — they need this same u32 path plus ordered non-idempotent
sequencing.

### V1 progress — 2026-07-17 (`do` sequencing → full virtio handshake in Kotoba)

The sequencing blocker above is resolved. The compiler (`kotoba-lang/compiler`,
merged `6d14f1a`) gained a **`do` form**: evaluate each subexpression in order,
discard all but the last. Unlike `let` (which inlines/substitutes, so a
side-effecting binding used 0 times is DCE-dropped and one used >1 times is
duplicated), `do` runs each subexpression's side effects **exactly once, in
order** — the missing primitive for MMIO sequencing. Added across desugar /
validate / verifier / IR oracle / all four backends (aarch64+x86_64 emit each
and keep the last result; wasm drops all but last; cljs → Clojure `do`).

With it, the **entire virtio-mmio transport handshake is now written in Kotoba**:
`resources/hvt/guest-virtio-handshake.kotoba` → `.elf` probes magic/version/
device-id (u32 reads), then `do`-sequences reset → `ACKNOWLEDGE` → `DRIVER` →
feature negotiate (sel 0/1, read offered, write accepted) → `FEATURES_OK` → a
`Status` read-back check → `DRIVER_OK`, emitting `HI\n` iff the whole handshake
holds (else `E`). It also exercises a **kernel-mode function call** (an
`emit-ok` helper). Verified on real KVM — the 21-step trace is **identical to
the asm/C virtio guest** (each store runs exactly once, in order), receipt
`{:serial "HI\n" :serial-ok? true :virtio-status 15 :shutdown? true}` (`0xf` =
DRIVER_OK). `hvt-smoke.cljs` now gates **8 cases**; the compiler suite is 188
tests / 3062 assertions.

This makes the virtio *transport* fully kotoba-first (the asm `guest-virtio`
guest is now redundant, kept as a cross-check). The **virtqueue** guests
(tx/rx, ring DMA) still use C; migrating them needs the same `do`/u32 path plus
guest-RAM struct writes, which the byte/u32 store intrinsics already cover — a
mechanical follow-up.

### V1 progress — 2026-07-17 (virtqueue tx/rx migrated to Kotoba — the guest path is fully kotoba-first)

The mechanical follow-up above is done: `resources/hvt/guest-virtqueue-tx.kotoba`
and `guest-virtqueue-rx.kotoba` are direct ports of `guest-virtqueue-aarch64.c`
and `guest-virtqueue-rx-aarch64.c`, needing no new compiler primitives —
`kernel-store-u32`/`kernel-load-u32`/`kernel-store-u8`/`kernel-load-u8` plus
`do` cover the whole split-virtqueue setup (descriptor table, avail ring, used
ring) in guest RAM.

- **Sub-u32 struct fields packed via arithmetic, not bit-ops** (this language
  has none): a descriptor's `flags`(u16)+`next`(u16) at one u32-aligned offset
  is written as `flags + next*65536`; an avail/used ring's `flags`(u16)+
  `idx`(u16) likewise. Reading the used-ring completion back uses
  `(quot value 65536)` to recover the high half — exact since these values are
  small and non-negative. The `u64` descriptor `addr` is two `u32` stores (low
  at `+0`, high `+4` = `0`, since every guest-RAM address here fits in 32 bits).
- **No polling loop needed**: the tender's virtqueue emulation is synchronous —
  the `QueueNotify` MMIO write itself services the queue (reads the ring,
  fills/drains the buffer, writes the used ring) before the guest resumes — so
  a single post-notify read of the used-ring index proves completion; no
  `loop`/`recur` or retry count required.
- **Reused RAM layout**: `desc@0x110000 avail@0x120000 used@0x130000
  buf@0x140000`, all inside the tender's 2 MiB window past the loaded ELF's own
  text/context.

Verified on real KVM: both guests' 25-step traces are **structurally identical**
to their C counterparts (handshake → queue config → one `NOTIFY` → serial
confirmation → poweroff). TX: `{:console "HI\n" :serial "HI\n" :serial-ok?
true}` (bytes pulled from the guest's transmit buffer through the descriptor).
RX: `{:serial "HI\n" :serial-ok? true}` (the guest echoes what the tender wrote
into its receive buffer). `hvt-smoke.cljs` now gates **10 cases**; both ELF
fixtures reproducible byte-identical.

**The entire hvt guest path is now written in Kotoba** — serial, u32 MMIO
device probing, the full virtio-mmio transport handshake, and both virtqueue
directions. The original asm/C guests (`guest-virtio-aarch64.S`,
`guest-virtqueue-aarch64.c`, `guest-virtqueue-rx-aarch64.c`) are kept as an
independent cross-check of the tender's emulation, not deleted — they still
pass and still gate in `hvt-smoke.cljs`, but they are no longer the reference
implementation for anything.

## Non-goals (firm)

- No from-scratch type-1 hypervisor; we always ride KVM/HVF.
- No general-purpose desktop virtualization product (no Windows/macOS guests,
  no GUI VM manager) — the guests are aiueos images and `computer:vm` QA VMs.
- No removal of QEMU from CI evidence gates in this ADR's lifetime.

## Consequences

- (+) Closes the last undesigned layer of ADR-2607022400's vocabulary: tender
  (`hvt`) becomes ours, guest is already ours (ADR-0013), the protocol between
  them is already CLJC (ADR-0011).
- (+) `computer:vm` (ADR-0010) gains a self-owned, audited backing path
  instead of depending on Parallels licensing or QEMU's full device zoo.
- (+) The no-new-Rust/C rule is honored without a waiver (option C), while B
  remains available under the "consume upstream substrate" carve-out if the
  spike loses.
- (−) A JVM inside the vcpu exit loop is unproven for anything beyond boot
  gates; the ADR deliberately defers production I/O claims to V2 measurement.
- (−) macOS/HVF (the actual daily-driver host) is deferred behind the
  entitlement/codesigning question; until then macOS keeps using QEMU+HVF.
- (−) This is TCB code by definition (the tender is the one deliberately
  non-sandboxed layer) and must be reviewed as such, like the ADR-0010
  provider backings and Phase-7 MMIO/DMA adapters.

## Decision gate

As proposed, this ADR was escalated for owner judgment per the 2026-07-10
owner rule (gaps the sanctioned runtimes cannot obviously fill are not
self-granted). Accepting it means: option C V0 may start (Linux/KVM, JVM-FFM,
receipts required); options B/D stay live until the V2 checkpoint. Rejecting
it means: option A stands, and `computer:vm` proceeds against Parallels/QEMU
when scheduled.

**Outcome — accepted by owner, 2026-07-17.** Option C V0 is authorized;
tracked as kotoba-lang/aiueos#110. Practical note recorded there: V0 needs a
Linux/KVM host — the primary dev machine is macOS, whose HVF backend is
deliberately deferred to V2, so the spike runs on a Linux VM or remote Linux
host with `/dev/kvm`.

## References

- ADR-0008 (bootable image + virtio guest drivers), ADR-0010 (`computer:vm`
  backing, increment 4 ⏳), ADR-0011 (Phase 1 scope-out; CLJC virtio protocol
  port; `aiueos.vfio` FFM precedent), ADR-0013 (guest-side ownership, release
  gates, compiler freestanding mandate).
- Superproject `90-docs/adr/2607022400-kototama-unikernel-tender-runtime-vocabulary.md`
  (tender/guest split, `hvt`/`spt`, Solo5 survey).
- Linux `Documentation/virt/kvm/api.rst`; Apple Hypervisor.framework
  (`hv_vm_create` et al., `com.apple.security.hypervisor` entitlement);
  Solo5 `docs/architecture.md` (`hvt` tender).
