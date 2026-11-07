# Canonical Linux-static SHA-256 computation source

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_sha256.kotoba` emits a private SHA-256
register-IR routine through the companion canonical assembler's instruction
constructor. The same IR covers x86_64 and AArch64. The emitted routine has
no calls, syscalls, FFI, host crypto or runtime collection helpers.

This is a source candidate, not an available capability provider. No generator,
assembler, hash operation, compiler build or generated artifact was executed.
No test was added or run. Native admission, Definition CIDs, emitted bytes,
positive/refusal behavior and digest correctness remain unqualified.

Source SHA-256:
`12b34f6037fea08bb1b85f51624b4d36e05f1a83efe0a995a9a0552b6bbed5ef`.

## Computation and provenance

The algorithm follows [FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf),
sections 4.1.2, 4.2.2, 5.1.1, 5.3.3 and 6.2.2: 32-bit words, 64 schedule
entries and rounds per block, big-endian block parsing and bit length,
padding, chaining and final digest. This is no NIST validation claim.

The existing wire-3 contract is recorded in Amu `tools/kexe_loader.c` at
`7872d10f587a2d4a0b92bc124037915e34c0cf26`: hash the admitted request bytes
and return 64 lowercase hexadecimal characters. Its source was read as
migration inventory; no C code was imported, built or run. Literal inventory
matched all 64 round constants and eight initial words against that source.

The routine traverses all message blocks and synthesizes the final padding
bytes into one reusable block. It does not copy the whole input or restrict
the contract to a short-message subset. Its byte-length bound is
`0..2305843009213693951`, keeping the message below 2^64 bits; the actual
mapped string window, profile and resource admission may impose tighter bounds.

Unsigned 32-bit values occupy i64 words. Rotation and accumulation mask to
32 bits using logical shifts. In particular, x86's sign-extending imm32 AND
cannot implement a `0xffffffff` mask. XOR uses `(d | s) & ~(d & s)` because
the current register IR has no XOR instruction. The 64 constants occupy a
512-byte little-endian data table after the return, addressed through a label.

## Exported generator API

| Export | Result |
| --- | --- |
| `routine []` | The complete typed instruction list, including alignment, entry, private labels, return and constant table |
| `entry-label []` | `:ls.sha256/entry` |
| `workspace-bytes []` | 816 |
| `digest-offset []` | 672 |
| `digest-bytes []` | 64 |

Append `routine` once to an image. Its labels are private to that image;
duplicate insertion must be refused by the assembler. The owning packager
still has to connect this list and account for its text/data and workspace.

## Private machine ABI

Arguments use the existing Linux-static IR aliases:

- `ctx`: unused incoming context argument.
- `a1`: start of a private, mapped, writable, 16-byte-aligned 816-byte workspace.
- `a2`: start of the admitted, stable input byte span; may be zero for empty input.
- `a3`: byte length.

The result in `ret` is `workspace+672`, pointing to exactly 64 lowercase
hexadecimal bytes without a NUL terminator, or zero for a preflight refusal.
This pointer is an internal host-mechanism value, never a guest string handle.
The output remains valid until this workspace is reused or released.

The routine preserves `s0..s4` and AArch64 LR. It clobbers `ctx`, `a1..a4`
and `t0..t3`; on x86 `t3` also aliases `gctx`. The caller must save/reload
any live caller-saved context. Scratch avoids `t4..t8`, which alias the
persistent `s0..s4` registers on x86. AArch64 immediate encoding may also
use its assembler-reserved x17 scratch. Stack space is required for five
preserved registers and LR, with the assembler's per-ISA push/pop convention.

Preflight rejects nonpositive/misaligned/overflowing workspace addresses,
negative input addresses or lengths, excessive bit length, overflowing input
end, nonempty null input and overlap of the input/workspace intervals. It
returns zero before input/workspace memory access; prologue stack saves still
occur. These arithmetic checks cannot establish that memory is mapped or owned.
The trusted caller must admit the entire input and workspace first and prevent
concurrent mutation or reuse. Failed preflight does not produce a digest.

| Workspace byte range | Contents |
| --- | --- |
| 0..511 | 64 message-schedule words, eight bytes each |
| 512..575 | Eight chaining words |
| 576..639 | Eight working words |
| 640..655 | T1 and T2 |
| 656..671 | Reserved |
| 672..735 | 64-byte lowercase hex result |
| 736..743 | Big-endian 64-bit message bit length |
| 744..807 | Reusable block; first 32 bytes later hold the raw digest |
| 808..815 | Alignment padding |

Every schedule, chaining, working and block word is initialized before use.
The raw digest and hexadecimal output occupy disjoint ranges. No secret is
introduced by hashing; these bytes are not a capability grant or seal verdict.

## Missing capability integration

The current owning static profile has no wire-3 handler. The companion
[C1/C3 gate candidate](linux-static-capability-port.md) now supplies the grant,
kind, request/result handle and pool-interning source path, and the planner
conditionally allocates its workspace. Neither has been generated or executed.
Keep the owning profile unchanged until this complete native chain is integrated
and qualified:

1. Admit the sealed grant bit and request/result kinds using the owning C1
   decisions. Hash's public/pure classification does not waive its grant bit.
2. Resolve and validate the request's UTF-8 string handle and its actual mapped
   code/pool byte window. No unchecked guest address may reach this routine.
3. Allocate/admit a private disjoint workspace, account for the message-size
   dependent computation and applicable profile resources, and bind the raw ABI.
4. Copy/intern the 64 result bytes into the bounded, metered string pool and
   return a validated string handle. Propagate allocation and named refusals;
   returning the raw pointer or request itself is not a substitute.
5. Bind the owning C3 dispatch and profile/admission entry together, then
   qualify the whole native provider and canonical artifact seal-verifier path.

The labels C1/C3 above name the existing native decision/dispatch layers;
they do not refer to a C language implementation requirement. This computation
does not replace those authority layers. Do not enable a catalog/profile entry
early, bypass the real seal check, inject an always-valid verifier, or claim a
host-computed digest as native qualification.

Static review covered delimiter balance, own-call arities after structural
thread expansion, known source call heads, constants, register alias use,
workspace offsets and the source-level block/round/hex dataflow. No generated
IR, machine bytes or digest was observed. The remaining full packager/runtime,
native provider binding and self-rebuild closure stay open under JUN-200/202.
