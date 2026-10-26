# aiueos native-driver foundation

This directory contains host-testable, freestanding admission and planning logic
for a bounded first pass over common x86_64 desktop hardware:

- `nvme`: NVMe PCI/BAR/CAP validation, queue geometry, Identify, and a read plan
  limited to direct PRP1/PRP2 transfers (no PRP lists).
- `xhci`: xHCI PCI/capability/extended-capability/port validation, ring admission,
  and USB HID boot-keyboard endpoint/report/event planning.
- `ethernet`: PCI inventory and explicit matching for Intel I225/I226 and Realtek
  RTL8125/RTL8126 families.

These modules do not touch PCI configuration space or MMIO. They do not bind to
the existing kernel yet. The Ethernet match is inventory evidence only: it does
not implement register access, PHY setup, DMA rings, interrupts, or packet I/O.
Every DMA plan requires a translated DMA window so callers cannot silently run a
bus-mastering device against unrestricted physical memory.

Run the local compile and test smoke with:

```sh
os/aiueos/native-drivers/smoke.sh
```
