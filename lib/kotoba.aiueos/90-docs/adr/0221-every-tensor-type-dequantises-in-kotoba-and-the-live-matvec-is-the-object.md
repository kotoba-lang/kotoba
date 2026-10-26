# ADR-0221 — every tensor type dequantises in Kotoba, and the live matvec is the object

- Status: accepted
- Date: 2026-09-16
- Wave 3 of ADR-0220's programme; stage 1 of its inference cutover. Extends
  ADR-0147 (the first three forward-pass objects) and ADR-0148. Owner
  direction: "kernel C を全て kotoba に", "next".

## What changed

**1. The dequantiser decodes all fifteen of the artifact's tensor types.**
ADR-0147's `qwen35-dequant-row` decoded four (F32, Q8_0, Q4_K, Q6_K) and
said why the other eleven stayed in C: they decode through codebook grids,
"and this dialect has no rodata and no bytes literal to put one in". It has
one now — `bytes-literal`, the boot-lit facility the UEFI loader modules
use — so the grids are literals and the dominant types of the shipping
model (IQ3_XXS 120 tensors, IQ3_S 106, IQ4_XS 45, IQ2_S 35, IQ2_XXS 24, …)
decode in Kotoba. The arithmetic of every type lives ONCE, in
`aiueos.lib.qwen35-dequant-core`; `qwen35-dequant-row` and `qwen35-matvec`
both require it through the project route, and the second copy the matvec
object used to carry is gone.

Two facts of the language shaped the grids:

- A program's string literals are capped at 64 KiB of UTF-8 and the hex of
  the nine raw tables is ~70 KiB. Every byte of the four IQ2/IQ1 grids takes
  one of THREE values (measured: {8, 25, 43}; {0, 1, 255}) and every byte
  of the two IQ3 grids one of eight, so `aiueos.lib.qwen35-grids` holds
  2-bit and 4-bit codes (9.3 KiB, 18.6 KiB of hex) and the accessor maps a
  code back to the C's value. The packing was round-tripped against every
  byte of every table before the literals were written.
- A function on the kernel target returns a word, never a float value, so
  every helper that computes a binary32 hands back its bit pattern.

**2. The live matvec is the Kotoba object.** `matvec_range` in
`qwen35_infer.c` now packs a 96-byte plan and calls
`kotoba_aiueos_qwen35_matvec` over one arena — the identity-mapped address
space from page 1 to the 64 GiB model identity limit, every offset an
address minus 4096 — in row chunks of `2,097,152 / cols` (409 rows of an
EMBED-wide tensor, 120 of an FFN-wide one), because the object caps one
call's work so its fuel bound does not move with the tensor. The BSP/AP
split under `AIUEOS_QWEN35_SMP` is unchanged: each half calls with its own
row range and scratch. `tensor_row` (the token embedding and output rows)
calls the dequant object. The C `matvec_range_c` and
`aiueos_qwen35_dequantize_row` stay as the REFERENCE: the parity self-test
compares the objects against them on the CPU, and
`-DAIUEOS_QWEN35_C_REFERENCE_MATVEC` makes them the forward pass again for
exactly two builds — the host smokes (a macOS/arm64 host cannot link a
kernel object) and parity profiles 2–4 (which link only their own stage's
objects to fit the low region). They leave when the K16 has measured the
object's token rate.

## Evidence

- **Contracts, from the C's own answers.** `qwen35-dequant-row-v1.edn`: 38
  vectors — every type, one and two blocks, random block bytes with FINITE
  NORMAL fp16 scales (a NaN would be canonicalised by the oracle host), run
  through the compiled C's `aiueos_qwen35_dequantize_row` and recorded bit
  for bit; 30 rows compared, every refusal reason observed.
  `qwen35-matvec-v1.edn`: 30 vectors, eight IQ/K-type tensors against the
  C's own `matvec_range` (the file included whole into the harness so the
  static reference is the one that ran). Both went red for the named vector
  with one grid decoder broken (`iq3s-value` ×2 → ×3: `:iq3-s-256`).
- **The oracle needed two things it did not have.** Its frontend pins
  (`nbb.edn`'s gitlibs paths; `deps.edn`'s `:verify-admissions`) were 244
  kotoba-sema commits behind amu's and did not admit `bytes-literal` as a
  region root — advanced to amu d7189340's lock. And the interpreter had no
  answer for a literal's address at all ("a place in an image that does not
  exist"): osaho #94 places each `bytes-literal` past the caller's memory
  image when one is supplied, 8-aligned, so a grid read is the same bounded
  load it is on the machine. Without an image the refusal stands.
- **Fuel.** Bisected per type in the oracle over 512-element rows: every
  type passes at 16,384 or 32,768 (IQ1_M, IQ2_XXS), i.e. ≤ 64 fuel per
  element against the dequant tier's 16,777,216 (65,536 elements: ≤ 4.2M)
  and the matvec tier's 250,000,000 (2,097,152 elements: ≤ 134M).
- **On the CPU.** `AIUEOS_QWEN35_KOTOBA_PARITY=1 smoke-qemu-uefi.sh`:
  `QWEN-PARITY dequant ok`, `dot ok`, `matvec ok` over all fifteen types
  (`qwen_parity_types` extended from four), and `QWEN-PARITY dequant
  mismatch` with the same grid decoder broken. The default profile and
  parity profiles 2, 3 and 4 boot to `AIUEOS_UEFI_SMOKE_OK` with the live
  path flipped (2–4 on the C reference, as above). Objects reproduce at amu
  d7189340 (`:cfree-wave-3-native`); contracts in `:cfree-wave-3-contracts`
  and on the oracle's default list.
- **The image did not fit.** With the two objects grown (8,192 → 39,896 and
  12,520 → 44,576 bytes) on top of wave 2, the production node profile
  linked `aiueos_low_end = 0x209000` against the 0x1f4000 limit. ~110 KiB
  of scratch that only ever held zeroes-then-data moved from `.bss` to
  `.high_bss` (the TLS transcript/record buffers, the tensor-table plan,
  the recovery ELF, the TCP scratch), and `main.c` now zeroes `.high_bss`
  at entry so a buffer keeps the zero-initialised semantics it had. The
  profile links at 0x1ee000 — 24 KiB of headroom. **That is the next
  structural limit**: the loader admits exactly two PT_LOAD segments
  (`uefi/elf.kotoba`), so Kotoba text cannot yet go above 2 MiB; the next
  wave either teaches the loader a third R+X segment or moves the paging
  structures out of the low region.

## What this does not do

- No K16 run. The object's token rate is unmeasured; the C reference stays
  until it is. Expect it lower: the object is a scalar four-accumulator loop
  where the C was AVX2.
- Norm/activation, attention and the recurrent step went live afterwards
  (ADR-0222 stage B item 6); `rope_heads` still needs a sine/cosine
  decision (ADR-0220).
- `qwen35_quant.c` is still compiled: it is the reference and its
  `aiueos_qwen35_quant_row_bytes` table is the marshalling's row arithmetic.
- The amu checkout at `orgs/kotoba-lang/amu` carries a local commit that is
  not on main (a bot's "jit-cosientist tick" note) and 198 untracked files;
  the attestation used a worktree at the pinned d7189340 instead. Not mine
  to clean.
