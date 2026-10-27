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

## Root cause of the earlier withdrawn attempt (same day, corrected)

The attempt trapped (#UD) before the first frame. The cause is the **size operand of the memory intrinsic exceeding
its tier maximum**, not the region being a function parameter. (This README first said the opposite: "a store applied
directly to a region passed as a function parameter traps". That was a wrong explanation of a correct bisect and is
withdrawn.)

* Each kernel memory intrinsic has a tier maximum for its size operand: 512 for `kernel-load-u8`/`kernel-store-u8` and
  the other plain forms, 4096 for `-4k`, 16384 for `-16k`, 65536 for `-64k` (`km-maximum`, kotoba-lang/amu
  `seed/86-aiueos-kernel-runtime.kotoba`). The emitted access starts with `cmp rcx, max; ja trap`, then checks a non-null
  base, index < size and enough room for the access width; every failing check is a `ud2`.
* The attempt wrote `(kernel-store-u8 ctx 8192 at v)`: size 8192 > 512, so every such store traps. The compiler accepts
  it: its compile-time check only requires the size to equal the region's extent, and never compares it with the tier
  maximum (filed as JUN-483).
* Controls, same program with only the intrinsic changed, in the guest: `(kernel-store-u8 ctx 8192 at v)` compiles and
  traps before the first frame (dump at the trap: `48 81 f9 00 02 00 00`, `cmp rcx, 0x200`, then `ja` and `ud2`; RCX =
  0x2000, RDI = the first index); `(kernel-store-u8-16k ctx 8192 at v)` on the same parameter region compiles and runs
  (16k maximum 16384 >= 8192); `(kernel-store-u8 ctx 512 at v)` on the 8192-byte region is refused at compile time with
  E7106 (size and extent differ, the check that does exist).
* The one-byte `kernel-subregion` idiom used in this slice, `(kernel-store-u8 (kernel-subregion ctx 8192 at 1) 1 0 v)`,
  works because it makes the size 1 (at most 512 and equal to the subregion's extent). A direct tiered store would work
  too. Nothing in the failure depended on the region being a parameter.

It was not the SHA-256 object: with the module reachable the guest decides all four vectors. The compile error
"region extent source unknown, caller aiueos-sha256" is a different, static check: an exported function that no call
site reaches has no known extent for its region parameters (extents are solved from the call sites; a constant extent is
encoded as 2^32 + n and a parameter-relative one as 2^33 + slot, `seed/74-x86_64-aiueos-object.kotoba`), and call sites that
disagree on the extent are refused. It appears when the admission module is imported but never called.
`aiueos.cid-v1-admit` also had to exist under `kotoba/aiueos/cid_v1_admit.kotoba` for the native source path; that file is a
byte-identical copy of `kotoba/cid-v1-admit.kotoba`.

Limits: QEMU TCG only; diagnostic. Source change and built candidate with a QEMU result; not deployed.
