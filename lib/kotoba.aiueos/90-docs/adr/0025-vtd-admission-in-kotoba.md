# ADR-0025 — VT-d admission moves out of C; the last kernel file with no decision in Kotoba

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0015, ADR-0023 (PCI config), ADR-0024 (ACPI admission)

## Context

`vtd.c` was the last kernel file with **zero** decisions moved out. One of them
is security-relevant:

```c
uint32_t iotlb = (uint32_t)((ecap >> 8) & 0x3ffU) * 16U + 8U;
if (iotlb < 8 || iotlb > 0xff8) { vtd_error = 5; return 0; }
write64(iotlb, ...);
```

That offset is **derived from a hardware-reported ECAP field** and then used to
address the 4 KiB MMIO register window. Deriving an offset from untrusted input
and bounding it is a judgement, not a register write.

## Decision

Move all three decisions — DMAR topology, capability admission, and the IOTLB
offset derivation — into one Kotoba object returning a single packed plan, so
the caller commits to one admitted decision rather than recombining parts
decided against different inputs. Register writes and table construction stay C.

**The object is called twice, and that is not redundancy.** CAP and ECAP are
MMIO reads that do not exist until the register window is mapped, and mapping it
is what the topology decision authorises. So: once pre-map with the topology
only (answering ABSENT / topology-admitted / refuse), once post-read with the
registers. The second call re-decides topology and conjoins it into the
admitted bit, so nothing acted upon is carried over from the first.

## Consequences

- **`AIUEOS_VTD_OK tes=1 root-context-slpt domain=1 aperture=128MiB`**, with
  `AIUEOS_DMA_POLICY_OK dmar=validated dma=vtd-isolated` and
  `AIUEOS_VTD_IR_OK … remappable-msix` downstream. The interrupt-remapping
  evidence is the strong part: it only appears if the ECAP bit test *and* the
  derived IOTLB offset were both right, since a wrong offset writes the wrong
  register.

- **Masking before dividing is load-bearing, and the naive form is a live bug.**
  `(ecap >> 8) & 0x3ff` cannot be written `(bit-and (quot ecap 256) 1023)`:
  `quot` truncates toward zero where `>>` floors, and the C masks *after*
  shifting so sign-extended high bits are discarded rather than folded down.
  Measured against the C rather than argued:

  | ecap | C | mask-first | divide-first |
  |---|---|---|---|
  | `0x800000000000500a` | 80 | 80 | **81** — wrong register, still in bounds |
  | `0xffffffffffffffff` | 1023 | 1023 | **0** → offset 8, **admitted where C refuses** |

  The second row is the one that matters: a hardware value with the high bit set
  would have turned a refusal into an admission.

- **A behaviour change, not a pure refactor**: the IOTLB bound is now checked
  *before* any register write, where the C checked it after RTADDR/SRTP/CCMD. A
  machine that would have been refused is now refused without its root-table
  pointer being set. `vtd_error = 5` becomes unreachable; `main.c` names only
  codes 3, 4, 6–9, so no diagnostic is lost.

- **A correction to this work's own brief.** It described CAP bit 10 as "legacy
  root/context format". Per the VT-d spec, CAP 12:8 is SAGAW and bit 10 is
  SAGAW[2] = 48-bit AGAW / 4-level tables — consistent with the C's
  `1ULL << (8 + 2)`, with the code building `sl_pml4`, and with `AW=2` in every
  context entry. Legacy-versus-scalable is ECAP.SMTS, not CAP. The test is bit 10
  either way, so nothing behavioural turned on the mistake.

- **An open question is now closed by measurement.** QEMU's CAP/ECAP values are
  recorded nowhere in this tree, so whether `-device intel-iommu` reports 48-bit
  AGAW was inferred rather than known — and if it reported 39-bit, this kernel
  had been silently refusing VT-d all along. The DMAR boot admits and enables
  translation, so it reports bit 10.

- Fuel: 1 unit per invocation, counted from two `decq 0x8(%r9)` sites in the
  disassembly, called twice per boot on the BSP only. Correctly outside
  `bounded-memory?`.

- **Every kernel C file now has at least one decision in Kotoba.** What remains
  in C is mechanism: register writes, page-table construction, DMA pages,
  virtqueues, the ISR stubs, and the drivers.
