# Full native graph migration candidate

The source changes preserve all15 kernel /27 live modules and all5 immutable
external owners. Boot header/map accesses use v5 bounds; scratch pages and
windows come from the sealed loader allocation. Descriptor TX/RX pages use
explicit4KiB subregions and the4KiB instructions. No physical integer is
accepted as a region root. The retired firmware-type MMIO constructor was
not adopted; the candidate calls the currently missing PCI constructor.

The current graphs both refuse E2101 at kernel-pci-mmio in rtl8125 with no
artifact. Six source-lock corruptions per graph refuse E6015. The retained
compiler is the corrected full36 native ARM F2, SHA256717f7d15582dcf18...;
these receipts are diagnostics, not native CDCI, x86 qualification or boot.

The13 arena write status predicates now compare integer status explicitly
to1. In an earlier source graph this advanced native frontend checking to
missing kernel-value-provider-queue. The current complete live graph stops
first at PCI. No queue, capability/domain ABI, full kernel runtime, media,
rendered desktop or input qualification is claimed. Follow the ledger and
native-pci-resource-handoff.md in dependency order.
