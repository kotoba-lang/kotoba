# ADR 0038: VEX prefixes are built once, and this evidence is encodings only

- Status: accepted
- Date: 2026-09-02

## Context

Before this change nothing in `kotoba.native.machine-ir` emitted a VEX prefix:
`0xc4` and `0xc5` occurred only as the second and third bytes of
`add rsp, imm32`. There is no YMM register anywhere, no FMA, and no packed
operation of any width. The f32 surface does not exist on native at all, and
f64 exists only as scalar SSE2 bounced through hardcoded `xmm0`/`xmm1`.

The K16 acceptance condition that motivates this work — "f32/SIMD/AVX2 emitted
by Amu (fused dequant+dot kernels, not a C matvec called from Kotoba)" — needs
an emitter for a quantized dot product. That emitter needs about twenty
distinct instruction encodings before it needs anything else.

Every existing encoder in this file builds its REX byte inline. That is right
for a one-byte prefix carrying three bits. It does not carry over to VEX, where
the same three bits are **inverted**, live in one of two different bytes
depending on which of the two prefix lengths is used, and share those bytes
with the opcode map, the vector length, an implied legacy prefix and a fourth
register operand. Inline construction at twenty sites is twenty chances to get
one bit backwards, and a backwards bit is not a compile error — it is a
different, valid instruction that runs.

## Decision

Add `vex2`, `vex3` and a `vex` chooser as the single place VEX prefix bits are
assembled, plus `x86-vex-rr` / `x86-vex-rm` producing whole instructions over a
closed `x86-avx-forms` table, `x86-sse-rr` for the one legacy form needed, and
`x86-vzeroupper`. Add 61 byte goldens.

`vex` picks the two-byte form exactly when X, B and W are clear and the opcode
map is 0F, which is what an assembler does. Both encodings of a qualifying
prefix decode identically, so this is not a correctness question; it is a
question of whether the emitted bytes match every published encoding, and they
should.

Memory operands go through one `vex-memory-operand` builder that owns the three
ModRM/SIB rules that are not free choices: a base whose low three bits are 101
(RBP, R13) always carries a displacement, because `mod=00 rm=101` **is** the
RIP-relative form in 64-bit mode; a base whose low three bits are 100 (RSP,
R12) always emits a SIB byte, because that value **is** the SIB escape; and RSP
is refused as an index, because SIB index 100 with X clear **means** "no index"
and would silently drop the operand.

This ADR adds no MC encoding, no GMIR operation and no KIR operator. Nothing
selects these bytes. They are landed alone so that they can be read against the
SDM before anything depends on them.

### Register and clobber discipline for the first consumer

Recorded here because the encoders cannot enforce it:

- **R9 is the context register** and must survive any sequence.
- **R10 and R11 are the scratch pair** the kernel-memory and privileged
  sequences in this file already borrow; a VEX sequence may use them freely.
- **All sixteen XMM/YMM registers are scratch**, because no allocator in this
  repository allocates one. `kotoba-mir` has no vector register class.
- **Any other general register must be pushed and popped**, exactly as
  `x86-quotient` does for RAX/RDX/RCX and `x86-privileged` does for RBX.
  `mir/saved-registers` is a syntactic `tree-seq` over the MIR map, so a
  register a sequence touches without naming is invisible to it.
- **`vzeroupper` before any return or call-out.** A sequence that has written a
  YMM register leaves the upper 128 bits dirty, and every subsequent
  legacy-SSE instruction in the process then pays a state-transition penalty —
  which on this kernel means every f64 operation `x86-f64-binary` emits.

## Evidence, and its exact limit

Each of the 61 goldens was produced by this encoder and then **disassembled**
by an independent assembler:

```
llvm-mc --triple=x86_64-unknown-linux-gnu --disassemble --output-asm-variant=1
```

(Homebrew LLVM 22.1.7.) All 61 decoded to the instruction the golden's label
names. Three examples:

```
0xc4,0x21,0x7c,0x10,0x4c,0x98,0x40  ->  vmovups ymm9, ymmword ptr [rax + 4*r11 + 64]
0xc4,0xc1,0x35,0x71,0xd2,0x08       ->  vpsrlw ymm9, ymm10, 8
0xc4,0x43,0x7d,0x19,0xd1,0x00       ->  vextractf128 xmm9, ymm10, 0
```

The check runs in the disassembly direction on purpose. LLVM's **assembler**
commutes the operands of commutative VEX instructions when that lets it use the
shorter prefix: `vaddps ymm8, ymm0, ymm15` assembles to `c5 04 58 c0`, which is
`vaddps ymm8, ymm15, ymm0`. This encoder does not commute and emits
`c4 41 7c 58 c7`. Both are the same operation. Assembling the labels and
diffing the bytes would have reported a bug that is not there.

**This is encodings-only evidence, and nothing more.** The machine this was
written on is an Apple M4; Rosetta exposes no AVX. Not one of these
instructions has been executed. A green suite here says the bytes are the ones
the SDM publishes; it says nothing about what they compute. Execution belongs
to QEMU TCG `-cpu max` or to K16 on real hardware, and until one of those has
run, no claim about SIMD *behaviour* may cite this ADR.

The goldens were shown to discriminate, twice, by breaking the encoder:

- Removing the inversion of the R bit in the three-byte first byte turned 36 of
  the 61 red, all with `0xc1` where `0x41` was published.
- Removing the RBP/R13 `mod=00` rule turned exactly 3 red — and the wrong bytes
  it produced (`c5 fc 10 05`) are a RIP-relative load, a different instruction
  reading a different address.

## Consequences

- The first `kernel-dot-f32` emitter writes operand maps, not prefix bits.
- Adding an instruction is one row in `x86-avx-forms` plus one golden.
- `x86-register-code` is unchanged. RSP and RBP are added to a separate
  `vex-address-register-code` used only for addressing, so widening what can be
  addressed does not widen what can be written.
- Nothing in `x86-reciprocal-cache-safe-encodings` or
  `x86-straight-line-encodings` changes, because this ADR adds no MC encoding
  for those closed sets to classify. When a consumer does add one, it must be
  considered for both, and it will not qualify for the first: a VEX sequence
  that borrows R10 invalidates a cached reciprocal.
- `vzeroupper` is emitted by nothing yet. The first sequence that writes YMM
  owes one.
