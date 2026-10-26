# ADR-0023 — PCI configuration space moves out of C

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0015 (the honest C boundary); root ADR-2608060100 (`kernel-in-*`)

## Context

The owner asked why aiueos needs C at all, and directed the work at compiling
the whole OS memory-safely in Kotoba.

The answer was narrower than "kernels need C". A zero-C boot path already
existed and was enforced; the existing C was already *decision-free* (every
judgement — crypto verification, admission, capability planning, dispatch — was
already a Kotoba object). What kept the C was one missing primitive: the kernel
target had `kernel-out-u8`/`kernel-out-u32` and **no port read**, and PCI
configuration space is a write to 0xCF8 followed by a **read** of 0xCFC. With
write-only port I/O, PCI enumeration could not be expressed in Kotoba at all —
and enumeration is the root of every driver.

Root ADR-2608060100 added `kernel-in-u8`/`kernel-in-u32`. This is the first use.

## Decision

**Move PCI configuration access into Kotoba.** `config_read`/`config_write` in
`kernel/pci.c` become thin `uint8_t` wrappers over
`kotoba_aiueos_pci_config_read` / `_write`; the port arithmetic, the `out`, and
the `in` all move to `kotoba/pci-config-{read,write}.kotoba`. The inline asm
`out32`/`in32` helpers and the `PCI_CONFIG_ADDRESS`/`PCI_CONFIG_DATA` defines
are deleted — `pci.c` no longer contains a port-I/O instruction or a port
number.

This is the first **mechanism** to move, not another decision. It is also where
the mechanism/decision line stops being a slogan: the input-domain check moved
with it.

**Out-of-domain calls do no port I/O at all** (read returns `0xFFFFFFFF`, write
returns 0). The rationale is aliasing, not tidiness: only the offset is masked,
so an over-wide field *carries into its neighbour* — `dev 32` sets bit 16 and
reads bus 1; `fn 8` sets bit 11 and reads device 1. An unchecked write would
mutate a device that was never named. `0xFFFFFFFF` is the bus's own "nothing
here", which `aiueos_pci_enumerate` already tests for, so the refusal lands in a
path callers have.

## Consequences

- **`AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4`** with enumeration driven by
  Kotoba, and every device downstream still found: virtio-net, IPv4 and TCP all
  still pass, and the full gate exits 0. This is a loud test by construction —
  if the Kotoba address word were wrong, enumeration would find nothing and the
  entire device stack would collapse.

- This is also the **first execution of `kernel-in`**. ADR-2608060100 could only
  claim correct encoding and admission; 8192 config reads per boot now execute
  it for real.

- **A latent fuel bug was found and fixed, in already-landed work.** Every
  function prologue decrements a fuel counter and traps on `ud2` at zero, and
  only objects in `kotoba-native`'s `bounded-memory?` set get a replenish in
  their wrapper. The IPv4 and TCP objects were not in that set.

  **Correction (2026-08-06).** This ADR originally said those objects "worked
  anyway, by accident — riding another object's replenish, because catalog
  admission calls `aiueos-sha256` and sets the shared counter to 10,000,000".
  That explanation is **wrong**, and the wrong model is the dangerous part: it
  makes a per-object budget look like it gets topped up by its neighbours, which
  makes every future budget argument wrong in the unsafe direction.

  Measured by linking three objects and disassembling their wrappers: each
  object's `lea …,%r9` resolves to a *distinct* `.data` context — 0x100728,
  0x100778, 0x1007c8, eighty bytes apart — and each carries its own `512` at
  offset 8. `linker.ld` concatenates `*(.data .data.*)` with no ICF, so this
  holds in the real build. **The counter is per-object.** An object outside the
  set gets 512 invocations *of itself* for the whole boot and cannot ride
  anything.

  So IPv4/TCP were not being rescued; they simply never exceeded their own 512,
  because every frame they saw was small (a 42-byte ARP reply, a ~98-byte ICMP
  echo). A full 1500-byte frame is ~750 recursive calls and **would** have
  trapped. The fix was necessary — for a different reason than first written.

  The frame-walkers now sit in the 4096 tier rather than 1024, and PCI in 1024:
  a checksum over a 1500-byte payload is ~750 calls at one fuel apiece, and
  `tcp-segment-valid` runs two of them.

- **It also explained the X25519 fault, now confirmed.** That object was not in
  the replenish set either, and needs ~4.8 million operations against its own
  512. Giving it RSA's 250,000,000 tier made it pass on target:
  `AIUEOS_X25519_OK rfc7748-base-point 32-bytes`, all 32 bytes compared against
  the RFC 7748 vector with `kotoba_aiueos_digest_equal`. The earlier
  `AIUEOS_EXCEPTION_FAIL unexpected-vector` was `ud2` — vector 6, which the
  kernel only expects from its own final probe.

- **The C is not gone.** `pci.c` still owns BAR mapping, virtqueue setup, DMA
  page handling and every driver. The next primitive is runtime-established MMIO
  regions: a bounded load must NAME a region, so a BAR address discovered at
  runtime still cannot be expressed. After that, interrupt entry, MSR access and
  `lgdt`/`lidt`.
