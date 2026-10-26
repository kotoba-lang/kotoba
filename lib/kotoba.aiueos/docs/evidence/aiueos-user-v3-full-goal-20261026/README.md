# AIUEOS user-v3 full Goal envelope (2026-10-26)

This is a source-bound diagnostic VM candidate. The Amu user-v3 ELF places
the complete 1–51 byte Goal in a 104-byte version-2 syscall 5 envelope. The
AIUEOS host checks its length, every byte against the displayed Goal, the
allowed alphabet, and zero padding after consuming the one-use local choice.
The admitted ELF is pinned by SHA-256
`108174e896008ac4b523450acd57d16b2b37ba3eb31f6b21d3ad3874344ca4ec`.

The [kernel build](build.json) used 31 locked Kotoba modules and reproduced
the kernel ELF and EFI with Mac native Amu F2. The [native media](media.json)
is the matching 8 MiB GPT/FAT16 image. The private-QMP observations are
[six-byte Goal](qemu-short.json) and [51-byte Goal](qemu-max.json), with
controller [short](debug-short.json) and [maximum](debug-max.json) receipts.
Both runs started two fresh QEMU processes from that media, committed and
restored the Goal, denied one synthetic choice, then used a synthetic `y` to
enter CPL3 and return token 111 through syscall 5. The observer read back
the complete request envelope and pinned user code. An independent third boot
refused a one-byte-modified user slot at CPL0. The short run captured the
[restored Goal](restored-goal.png) and [choice screen](approval.png).

No VNC listener, password, NIC, host model service, Linux, JVM, or Node was
used in this gate. Synthetic QMP keys verify guest branching; they do not
prove trusted human consent. The model still emits one token from a fixed
local transition table. Canonical `:llm/generate`, a real Itonami agent turn
loop, D2 workspace restore, release admission, and physical hardware remain
separate open gates. The unchanged final-character model result does not
establish that the whole Goal influences inference; this slice binds the
request bytes to the displayed Goal.
