# ADR-0147 — The Qwen3.5 forward pass gets its first three objects

Status: accepted
Date: 2026-09-02
Relates to: ADR-0131 (K16 pure-native profile), ADR-0145 (GGUF admission
objects), ADR-0136 (the GGUF admission runs on a CPU), ADR-0030 (one exported
symbol per object), kotoba-native #113, kotoba-kir ADR 0238.

## Decision

The arithmetic under `matvec_range` (`kernel/qwen35_infer.c:344`) becomes three
Kotoba kernel objects:

| object | export | bytes | fuel tier |
|---|---|---|---|
| `qwen35-dequant-row.kotoba` | `kotoba_aiueos_qwen35_dequant_row` | 8,176 | 16,777,216 |
| `qwen35-dot-f32.kotoba` | `kotoba_aiueos_qwen35_dot_f32` | 2,608 | 4,194,304 |
| `qwen35-matvec.kotoba` | `kotoba_aiueos_qwen35_matvec` | 12,512 | 250,000,000 |

Three rather than one because a kernel object exports one symbol and cannot
call another (ADR-0030), and because the C has three seams a caller can want
separately. **The third inlines the other two**, so the three are three copies
of one piece of arithmetic; their contracts drive all three from the same
oracle-derived bytes, so a divergence between them is a vector mismatch rather
than something to be discovered in the model path.

## The accumulation tree is the contract, and the C has two of them

`dot_scalar` (:234) keeps four accumulators stepped four apart and reduces
`(s0+s1)+(s2+s3)`. `dot_avx2` (:272) keeps the same four lanes but reduces them
**left to right**, so the two compute different values for every count of eight
or more, and the C picks between them at runtime on `qwen_vector_bits`. The
object reproduces `dot_scalar`, and says so in its contract, because "matches
the C" is not a statement anyone could check while the C has two answers.

## What is NOT ported, and it is the majority of the model

F32, Q8_0, Q4_K and Q6_K — 490 of the artifact's 866 tensors. The four IQ types
that **dominate** it (IQ3_XXS 120, IQ3_S 106, IQ4_XS 45, IQ2_S 35 = 306
tensors) decode through codebook grids that `qwen35_quant_tables.inc` holds as
static const data, and this dialect has no rodata and no bytes literal to put
one in. Those types stay in the C, so **the K16 model still runs its dominant
matvecs in C**. That is not a schedule item this ADR is deferring; it is a
missing language facility, and the stream that adds one (`bytes-literal`)
unblocks it.

## One arena, one plan

`kernel-subregion` requires its base to be a parameter, a literal or
`kernel-boot-info`, so weights, input, output and row scratch would need four
bases and four lengths against a five-argument ABI. The caller puts all four in
one region and describes them in a 96-byte plan; an *offset* may be computed.
The offsets are 64-bit because the model mapping is 10,934,860,704 bytes and a
u32 slot would silently truncate every tensor past 4 GiB.

The plan carries a **row range**, and that is what makes the fuel bound finite.
A single K16 matvec is 17,408 rows of 5,120 — 89 million multiply-accumulates,
which no fuel tier bounds — so the object refuses more than 2,097,152 elements
of work per call and the caller chunks. It is also how the C's SMP split is
expressed: `matvec` hands the AP `[split, output_count)` and keeps
`[0, split)`.

## Evidence

**On the CPU.** `AIUEOS_QWEN35_KOTOBA_PARITY=1 os/aiueos/scripts/smoke-qemu-uefi.sh`
compiles `kernel/qwen35_{quant,infer}.c` and links the three objects, and
`kernel/main.c` runs `aiueos_qwen35_kotoba_parity_selftest` beside the X25519
and TLS self-tests, after the kernel owns its own IDT. Every comparison is on
**bit patterns**, not printed floats:

```
QWEN-PARITY dequant ok
QWEN-PARITY dot ok
QWEN-PARITY matvec ok
...
AIUEOS_UEFI_SMOKE_OK
```

Shown red: an object with Q6_K's scale index changed from `(quot l 16)` to
`(quot l 8)` — one wrong scale, nothing else — recompiled and linked through
`AIUEOS_KOTOBA_QWEN35_DEQUANT_OBJECT`, produces `QWEN-PARITY dequant mismatch`
and stops the boot.

This is a **separate build flag from `AIUEOS_QWEN38_MODEL_HANDOFF`**, and the
reason is measured: the handoff makes the UEFI loader demand a
10,934,860,704-byte mapping and refuse the boot without one
(`AIUEOS_LOADER_FAIL qwen38-model-admission code=121`). The comparison needs no
model — it is bit-equality of the arithmetic over synthetic inputs, which is
exactly the property that survives having no weights.

**In the interpreter.** `contracts/qwen35-{dequant-row,dot-f32,matvec}-v1.edn`
through `os/aiueos/scripts/verify-admissions.cljk`: 58 vectors, 10 memory
assertions, every reachable reason code observed (`-6..0`, `-11..0`, and the
dot product's four out-of-i32 refusals). The expected bytes come from an
independent ClojureScript re-derivation of the C over `Float32Array`, so every
rounding in an expectation is a real binary32 rounding. Shown red: flipping one
nibble of one expected output byte in `:q6-k-256` reports
`memory mismatch :region :row :vector :q6-k-256`.

**Bytes.** `qualification/jvm-free-object-parity-qwen35-kernels.edn`:
`SCANNED 3 MATCH 3 DIFFERS 0 COULD-NOT-RUN 0 FAILED 0 REACHED-A-JVM 0`, and the
three digests are the committed `.o`s.

## What this does not claim

- **The C is unchanged.** `qwen35_infer.c` gained the self-test and nothing
  else; `matvec_range`, `dot_scalar` and `tensor_row` still run every model
  matvec. Nothing has been flipped to call the objects yet. That is stage 4's
  decision and needs `evaluate_token` first.
- **`kernel-dot-f32` is not used.** kotoba-gmir ADR 0010's SIMD primitive has
  the same accumulation tree and agrees with `dot_scalar` exactly when the
  element count is a multiple of eight — which every Qwen3.5 dimension is. It
  is not wired because its AVX2 arm is still blocked on CR4/XCR0 setup that
  another stream is adding, so today it would buy the scalar arm and a tail
  that differs for `count mod 8` in 4..7. The contract's vectors at counts
  4..7 and 12..15 pin that boundary so the swap-in cannot be made silently.
- **The fuel tiers were measured in the KIR interpreter, then executed once.**
  The bisected fits are `3n+6`, `19n+5` and 22-per-element; the QEMU run is the
  first execution on hardware and it returned. One execution at one size is not
  a bound.
- **No SMP.** The plan's row range is what an SMP split would use; nothing
  splits yet.
