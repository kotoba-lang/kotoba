# ADR 0078: the fuel ceiling was an immediate width

Status: accepted. Date: 2026-09-03.

## Context

A kernel object's wrapper replenishes its own fuel before calling the Kotoba
entry:

```
4c 8d 0d <disp32>        lea r9,[rip+.data]      (relocated)
49 c7 41 08 <imm32>      mov qword [r9+8], imm32  <- the replenish
48 83 ec 08              sub rsp,8
e8 <disp32>              call <entry>
48 83 c4 08              add rsp,8
c3                       ret
```

The immediate is 32 bits and the CPU sign-extends it, so the largest budget
this could write was **2,147,483,647**. That number was never a decision. It is
the width of a field, and the tier table beside it made it invisible by holding
**hand-encoded byte vectors** with the decimal value in a trailing comment:

```clojure
sha-region-fuel? [0x49 0xc7 0x41 0x08 0xff 0xff 0xff 0x7f] ; 2,147,483,647 (8.8x)
```

There is no shape in that line that says "and this is the most it can be".

It became an argument anyway, twice:

- **aiueos ADR-0142** capped `sha256-region` at a 1 MiB window and gave this as
  the reason — *"the replenish immediate is 32 bits so 2,147,483,647 is the
  largest tier ANY object can have, which at 14,894/block pays for 8.80 MiB"*.
- **aiueos ADR-0175** (QWEN-KERNELS-2) concluded `evaluate_token` **cannot be
  one Kotoba object**: the output projection alone is 248,320 × 5,120 MACs
  ≈ 27,970,764,800 fuel, thirteen times the ceiling. The forward pass stayed
  with C calling each object in turn.

**The ABI never had that limit.** `kexe_context_v4`'s `fuel` is a `uint64_t`,
the charge is `cmp qword [r9+8],0` / `dec qword [r9+8]`, and both image
packagers (`package-kernel`, `package-kernel-aarch64`) have always written the
budget as `(le (artifact-fuel artifact) 8)` — eight data bytes, admitting up to
`Long/MAX_VALUE`. AArch64 has no replenish immediate at all: `package-kernel-object`
is x86-64 only, so there is no object route there to have one in.

## Decision

**Two forms, chosen by the tier and by nothing else.**

```
fuel <= 2147483647    49 c7 41 08 <imm32>              8 bytes  (unchanged)
fuel >  2147483647    49 ba <imm64>   movabs r10,imm64  10 bytes
                      4d 89 51 08     mov [r9+8],r10     4 bytes
```

Verified against `clang -masm=intel`, not asserted from a manual.

`r10` rather than a saved register, and this was checked rather than assumed:
the wrapper runs **before** the call, so the only live values are the SysV
argument registers rdi/rsi/rdx/rcx/r8 — which pass straight through, and are
why an object's arity ceiling is five and not six, r9 being spent on the
context — and r9 itself, loaded two instructions earlier.
`kotoba.native.x86-64/emit-function` refuses a sixth parameter by name, and the
callee's own prologue writes r10 and r11 before reading either.

**The tier table now holds numbers.** `replenish-bytes` picks the encoding.
Every number in it still fits the narrow form, so **no shipped object's bytes
move** — proven, not asserted: `test/kotoba/native/fuel64_object_digests.edn`
is the SHA-256 of all 108 packaged objects taken at `452422f5`, the commit
before this change, and `every-shipped-objects-bytes` re-derives all 108.

### The line is signed, and the encoder will not say so

`kotoba.object.elf64/little-endian` at width 4 admits the whole **unsigned**
range below 2^32. A tier of 3,000,000,000 would therefore encode without
complaint and land in the context as **−1,294,967,296**. `cmp qword [r9+8],0`
reads that as "has fuel" and `dec` walks it *further* from zero: the object
would never trap on fuel again. Hence `<= 2147483647` in `replenish-bytes`
rather than deferring to what the encoder accepts, and
`the-line-is-signed` pins 2,147,483,648 as the first wide value.

### The ceiling is 2^53−1, and it is decided in `kotoba.kir`

`max-object-fuel` restates `kotoba.kir/max-fuel` rather than requiring it: this
namespace does not depend on the interpreter and should not start, because
`kotoba.compiler.nbb.native-package` would then load the whole evaluator for one
integer. The two literals are compared in amu, which is the only classpath that
holds both (`kotoba.compiler.fuel64-ceiling-test`).

Not 2^63−1, which the instruction and the qword could carry: the KIR oracle's
counter is a double on Node, and measured 2026-09-03, `x - 1 === x` is already
true at 2^53+4. kotoba-kir ADR 0268 has the argument.

### The wide form is in the production table, not only in a test

`aiueos-fuel-wide-probe` (arity 1, tier 4,300,000,000) is a probe and
deliberately not a workload. A second encoding that only a test ever reaches is
a second encoding nobody has shipped. Its low 32 bits are **5,032,704** — what
a truncating encoder would have written — so a caller can spend between the two
and tell the encodings apart on a real CPU. aiueos ADR-0195 is that run.

### The interrupt entry stays imm32, and now says so

`interrupt-abi/entry-bytes` did **not** widen. Its size is load-bearing in a way
the wrapper's is not: `entry-stride` is 128, and
`context-displacement-offset` / `call-displacement-offset` / `entry-size` are
hand-counted from the instruction widths, including a literal
`8 ; mov qword [r9+8], imm32`. A wide form there would move every gate in the
entry region.

What changed is that it **refuses** rather than wraps. `le32` is
`(mod n 4294967296)` on purpose — RIP displacements are negative — so a fuel of
exactly 2^32 wrote **four zero bytes**: the entry would replenish to zero, the
callee's first charge would find zero and `ud2`, and every interrupt on the
machine would take vector 6. A silent truncation in the one value that means
"how much work may happen" produces a fault that reads as a body bug, in a body
that is correct. Now: `:isr-entry-fuel-exceeds-imm32`.

## Consequences

- `evaluate_token`'s ≈2.8×10^10 is four orders of magnitude inside the new
  ceiling. **That says the road is open; it does not say the object exists.**
  ADR-0175's other findings stand.
- aiueos ADR-0142's 1 MiB `sha256-region` window no longer follows from the
  encoding. Whether to raise it is a separate measurement (at 14,894 fuel per
  64-byte block, the new ceiling pays for about 36 TiB, which is not a
  recommendation — it is past every other bound in that object).
- A tier near the ceiling on an object the kernel calls with interrupts
  disabled is a **hang**, not a bound. The ceiling is what the mechanism may
  carry. The tiers stay measured by execution with a stated margin.

## Evidence

| what | where |
|---|---|
| both forms, byte for byte | `fuel64_test.clj/the-two-replenish-forms` |
| the signed line | `the-line-is-signed` |
| refusals, by reason literal | `a-tier-outside-the-admitted-range-is-refused-by-name` |
| **no shipped object moved** | `every-shipped-objects-bytes`, 108 rows, `SCANNED 108` |
| the wide form reaches the production table | `the-wide-form-is-reachable-from-the-production-table` |
| the ISR refusal | `interrupt-entry-refuses-a-fuel-it-would-truncate` |
| the image word was always 64-bit, both architectures | `the-image-context-word-was-always-64-bit` |
| **the portable twin emits the same bytes** | `elf64_portable_test.cljc`, on nbb |

Break/unbreak, each with the failure named:

| break | what went red |
|---|---|
| the line becomes unsigned (`<= 4294967295`) | `the-two-replenish-forms`, `the-line-is-signed` |
| one shipped tier changes (`high-fuel?` 4096 → 8192) | `every-shipped-objects-bytes`, 7 rows |
| the ISR guard admits what `le32` would truncate | `interrupt-entry-refuses-a-fuel-it-would-truncate`, on the reason literal |
| the replenish cond is renamed | `elf64_twin_parity_test`'s evidence floor, by assertion message |

The twin-parity test's own fuel pattern had to move with the format, and that
is worth recording: it matched **zero** arms after the change and reported
`the .clj fuel tiers did not parse` — the evidence floor was the only thing
between "the two files agree" and "nothing was compared". Its floor is raised
from 3 to 20, and it now compares the `:else` default as a tier like any other.
