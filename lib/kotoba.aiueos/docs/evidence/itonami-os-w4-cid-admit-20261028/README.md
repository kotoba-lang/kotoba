# Itonami OS W4 slice: the guest decides that bytes are the content a CID names (2026-10-28)

`--profile cid` boots `cid-entry.kotoba`: before the desktop starts, the kernel runs the shipped
`aiueos.cid-v1-admit` (ADR-0128: SHA-256 over the block, compared with the CID's digest) on four vectors
and leaves the codes in browser-context words 100..103 (marker word 99 = 0x43494431, written last).
The block is "abc"; its raw CIDv1 is `01 55 12 20` + sha256("abc"). The QEMU gate reads the words after
the first completed frame and asserts `[0, 8, 4, 3]`:

| vector | code |
| -- | -- |
| the block as is | 0 (admitted) |
| one block byte changed | 8 (digest mismatch) |
| multihash code 0x12 changed to 0x13 | 4 |
| codec 0x55 changed to 0x56 (not permitted) | 3 |

Evidence: `native-cid-qemu.json` (QEMU TCG, Apple Silicon, no network, no input), built with the Amu
checkout's pinned root alone (signed compiler `9d023d99...`); kernel/EFI reproduced; 32 modules. The
three refusals are the negative controls: a kernel that always admitted, or never decided, fails.
A build variant whose marker constant was wrong was refused by the gate ("self-test did not finish").
The consent and desktop profiles are unchanged by this slice (same digests as before).

What this is not: no `ipfs://` URL is opened. The desktop has no network and no scheme handler, so this
proves the kernel can decide the match, not that a URL was fetched or shown. The block is a 3-byte
constant, not fetched data. Only the 12288-byte bound of the admission object is exercised at 3 bytes.

## Root cause of the earlier withdrawn attempt (same day)

The attempt trapped (#UD) before the first frame. The trap was the bounds-checked `kernel-store-u8`
applied directly to a region passed as a function parameter (`(kernel-store-u8 ctx 8192 at v)`):
the same store through a one-byte `kernel-subregion` (`(kernel-store-u8 (kernel-subregion ctx 8192 at 1) 1 0 v)`,
the idiom `put-word` and `put-result` already use) works. A bisect isolated it: marker stores only: passes;
adding byte stores through the parameter region: no first frame; through a subregion: passes. It was not
the SHA-256 object: with the module reachable the guest decides all four vectors. (The compile error
"region extent source unknown, caller aiueos-sha256" appears only when the admission module is imported
but never called.) `aiueos.cid-v1-admit` also had to exist under `kotoba/aiueos/cid_v1_admit.kotoba`
for the native source path; that file is a byte-identical copy of `kotoba/cid-v1-admit.kotoba`.

Limits: QEMU TCG only; diagnostic. Source change and built candidate with a QEMU result; not deployed.
