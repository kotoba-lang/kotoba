# Native kernel layout v2 and user-v4 (2026-10-26)

The [receipt](receipt.json) records the exact Mac selfhost compiler, the
35-module locked source graph, the reproduced kernel ELF and EFI, native
GPT/FAT16 media, and private-QMP QEMU result. No Linux, JVM, Node or C compiler
ran in the native build path. The new kernel retains entry 0x101000, places RX
text before the 2 MiB file boundary, and places data at physical 0x300000.
Its user pages are at 0x320000 and 0x321000. The Amu user-v4 ELF and slot-v3
use those same addresses.

The Mac Amu F1 and F2 compiler containers were byte identical. That final
compiler reproduced the kernel ELF, user ELF, slot and EFI used by the QEMU
run. Its packager also rejects a short RW region. The native media
builder independently read back the 8 MiB GPT/FAT16 image and passed its ten
format refusal cases. Two QEMU boots from that image saved Goal `awai a`,
restored its visible text in [Itonami](restored-goal.png), and exercised the
[choice screen](approval.png) with synthetic keys. Denial did not run the
user code. Acceptance reached CPL3 and returned token `i` (105) through the
user-originated syscall. A one-byte changed slot was refused before CPL3.
QMP used private stdio, with no VNC listener, password or NIC.

After the selected Amu core and CDCI pins were repaired, the new signed Mac
compiler independently rebuilt the same 35-module AIUEOS source. Its kernel
ELF, user ELF, slot and EFI matched the QEMU-tested image byte for byte; the
[reproduction receipt](core-repin-reproduction.json) records the new compiler
identity and four output hashes. This establishes byte identity with the
earlier VM observation, without claiming another QEMU or hardware run.

The versioned packager accepted kernel-v1 with slot-v2 and kernel-v2 with
slot-v3. It refused both mixed pairs, a changed user-v4 ELF entry, and a
kernel-v2 RW address changed to 0x301000, and a shortened RW segment. On the
original 31-module source,
the new Amu compiler reproduced the prior kernel-v1 ELF and EFI SHA-256 values
exactly.

This qualifies a VM layout and fixed local-model request path. The new
LLM component validation is connected to the live Goal, but general model
execution, wire-11, agent loop, release admission and physical hardware
qualification remain separate. Synthetic keys do not prove human consent.
