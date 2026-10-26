# Native DMA region contracts

Status: engineering ARM native compilation and bounded QEMU execution.
Native x86/controller adoption, live ABI, release media and desktop/input
qualification remain open under JUN-31.

The full kernel keeps all15 locked modules and all functions. The native
compiler resolves fixed and explicit base/length contracts over the complete
call graph, including rooted mutual recursion. It rejects unseeded cycles,
forged or computed bases, mismatching lengths and non-identity parameter
rebindings. Namespace exports remain linker interfaces. They do not grant
kernel ABI authority.

The bus3 DMA region is always the owned region. Pass readiness separately;
do not replace a region with0 when a NIC is unavailable. Retained diagnostics
without boot callers declare explicit base/length pairs and narrow them
before executing their recursive bodies. No diagnostic or dependency is
removed to obtain admission.

## RX layout

| Resource | Owned pages or offsets | Extent |
| --- | --- | --- |
| TCP DMA window | pages10..13 | 16384 bytes |
| RX descriptor buffers | offsets8192,10240,12288,14336 | 2048 bytes each |
| CPU RX snapshot | page14 | 4096 bytes |
| Stream log/TX/staging | pages1..3 in the NIC branch | separate from snapshot |

The former fourth RX frame used offset14336 and length4096, crossing the
DMA window by2048 bytes. Each source is now a checked2048-byte subregion.
`snapshot-rx-frame` copies exactly the received bytes into page14 after
zeroing that page with readback. The existing frame parsers consume that
4096-byte snapshot. Index, byte count and source/destination overlap are
checked before changing the snapshot. Invalid requests preserve it.

Region selection chooses a numeric offset, then constructs one subregion.
A branch that returns different pointers is not made into a region root.
Descriptor ownership/rearm order is unchanged; the CPU snapshots after the
NIC releases the descriptor and before it is rearmed.

## Evidence boundary

`dma-snapshot-probe.kotoba` retains the entire kernel graph plus its real
vector-6 callback. It executes the actual snapshot implementation without
executing the kernel boot entry. Its ten checks cover every byte of all
four buffers, short-packet zeroing and invalid index/size/overlap requests.
The QEMU observer independently reads the sealed scratch base, ten receipt
words and all4096 snapshot bytes. A different valid image returning42 is
rejected because it has no DMA receipt.

This functional gate checks bounded remaining fuel and explicitly does not
claim exact fuel parity. Existing exact-fuel gates retain their defaults.
The compiler itself still requires full self-rebuild and all24 runtime
checks, actual native x86/controller execution and consistent public/root
pins before adoption. QEMU TCG is emulation; it is not physical RTL8125
qualification, complete OS boot, GPT media, desktop or input acceptance.
