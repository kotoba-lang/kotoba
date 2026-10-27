# Itonami Goal save, cold restore and CPL3 without a human login (2026-10-26)

The [Mac native build receipt](build.json) binds the 31-module Kotoba kernel,
AIUF font and AIUP v2 user ELF slot in one EFI. Kernel SHA-256 is
`13c6f51d98531eeda418948ad2873269ae791a5f73499186a07d1bf64e82427a`;
EFI SHA-256 is
`b71770aa66c1f2c233fa7071454a51f556351269c2f9bc6ba239e7de7a91e366`.
The new profile enables both the marked local-draft store and the Goal to
user-v2 handoff. The original RAM-only Goal and draft-only profiles remain
separate.

The [unattended QMP receipt](debug-summary.json) used two fresh QEMU processes.
The first typed `awai debug` in Itonami and committed generation 1 with F5 to
an output-owned 64 KiB marked scratch disk. The second cold-booted the same
EFI and disk, restored the Goal, captured its [visible guest screen](restored-goal.png),
then sent Enter. The pinned user ELF read the restored Goal in CPL3 and
returned `10`. The disk bytes did not change during the CPL3 read. QMP was a
private standard I/O pipe with no VNC listener, password or NIC; no human
keypress or Screen Sharing sign-in was used.

Repeat from this checkout using the matching Mac native build directory:

```sh
python3 os/aiueos/scripts/debug-native-user-v2-durable-unattended.py "$BUILD" \
  --goal 'awai debug'
```

The script verifies build and source hashes, creates a new private output
directory each time, and only attaches its own scratch disk. Synthetic QMP
input is diagnostic input; it is not trusted approval for an external service.
The saved draft contains Goal text only. D2 workspace state, a signed head,
fresh operation approval, actual model/tool effects, release and physical
hardware qualification remain open.
