# ADR 0042: Transfer width, window tier, and the ADR 0285 slice carrier

- Status: accepted
- Date: 2026-09-02

## Decision

Both native backends gain the two remaining MMIO transfer widths, every window
tier for every width, a natural-alignment check, and the element-indexed slice
family amu ADR 0285 decided on.

### Windows: four widths by four tiers

`kernel-{load,store}-u{8,16,32,64}` at tiers 512 / 4096 / 16384 / 65536.

`kir-kernel-memory-ops` was seven entries, and four things were true of them
that nobody had written down as a judgement:

- `kernel-load-u8` reached a 16 KiB window; `kernel-store-u8` did not.
- the u32 pair reached neither the 4 KiB nor the 16 KiB tier.
- there was no 16-bit access, which is what a PCI vendor/device ID pair and
  most legacy device registers are.
- there was no 64-bit access, which is what a descriptor ring pointer is.

The GMIR operation carries the width and `:gmir/maximum` carries the tier,
which is what makes them two independent axes rather than a list of the
combinations someone happened to need. 65536 is a tier because
`cmp r64, imm32` costs the same bytes at 65536 as at 512.

### Alignment, and the two operations exempt from it

Every access wider than a byte checks `index mod width == 0`, **last**, so a
program that was trapping on the window still traps on the window and an index
that is both misaligned and past the tail reports the tail.

It is checked at all because a misaligned MMIO access is architecturally
undefined on AArch64 device memory and splits the bus lock on x86. The
machine's answer to one is not a value; making it a Kotoba trap is the only
answer that is.

`unaligned-accesses` names the exemptions: `kernel-load-u32` and
`kernel-store-u32` **at the 512-byte tier**, plus the lock pair, which reaches
the bounds check through a caller that never requests alignment. They are
exempt **by date**, not by shape — the same u32 load at a 4 KiB window does
check — because retrofitting the rule would change the bytes of shipped aiueos
objects, and a caller that was misaligned was already broken in a way this
change is not the place to discover.

That asymmetry is pinned by a test in both directions. If a later change closes
it, the test says so out loud rather than the closure happening quietly.

### The slice family

`slice-{load,store}-u{8,16,32,64}`. `index` and `length` count **elements**;
the ceiling is `slice-item-limit` = 2^40, an address-space bound chosen so
`length * 8` cannot wrap a 64-bit address.

Four checks against the window family's five, and the shape is the point:

| | window | slice |
|---|---|---|
| ceiling | tier (`cmp r64, imm32`) | 2^40 (`movabs` + `cmp`) |
| null base | yes | yes |
| index | `index < length`, bytes | `index < length`, **elements** |
| tail | `length - index >= width` | **not needed** — the index counts elements |
| alignment | per access, on the index | **once**, on the base |
| address | `mov r11,base; add r11,index` | `lea r11,[base+index*width]` |

A scaled index off an aligned base is aligned, which is why the per-element
alignment check disappears. What is left per element is **one unsigned compare
and one scaled load**. The `x86-slice-is-one-scaled-mov-after-one-compare`
golden asserts the absence of both `call qword ptr [r9+disp8]` and its disp32
form: no context callback, which is the property ADR 0285 set out to buy.

On AArch64 the two families emit the *same* `ADD (shifted register)` into x16
and differ only in the LSL amount, so a test that reads that field is the
sharpest form the claim can take.

## What this is NOT

**The `[:slice T]` value.** ADR 0285 asks for a two-word (base, length) carrier
a `let` binds, a function parameter carries, and `slice-sub` narrows. What
lands here is the machine layer it lowers to: three separate i64 operands.

The gap is a **register-allocator** change, not a machine-code one.
`pilot-expression?` knows exactly one value shape, `:scalar`, and
`kotoba.native.x86-64`'s fallback keeps every value in RAX. Both backends can
already emit every load, store and check a slice needs.

So no type is admitted. `kotoba.kir/native-word-value-type?` deliberately does
not list `[:slice T]`, because nothing produces a slice value — an admission
gate that admits what nothing can lower is the defect amu ADR 0284 named, and
0285's closing section refuses to create a second instance of it. The exact
remaining work, and the `kotoba-lang` authority entries this change proposes,
are in `docs/lang-authority-diff.md`.

**No existing ceiling moves.** `vector-item-limit` 16384,
`:vector-item-capacity` 65536, `:vector-capacity` 4096 and
`:bytes {:max-value-bytes 65536}` are all untouched. That is ADR 0285's second
decision and it is honoured literally: the loader memory image, the verifier's
derived limits and the pinned runtime identity SHA do not move together.

## The fallback path

`kotoba.native.x86-64` and `kotoba.native.aarch64` keep their four original
emitters **byte for byte**. Nothing reaches them today (measured 2026-08-31 by
instrumenting both vars), but their bytes are the ones shipped aiueos objects
were built with, and a generalisation that changed them would move a pinned
artifact for no reason of its own.

Everything new goes through two generalised emitters per backend which follow
`kotoba.native.machine-ir` exactly rather than the older form: `index < length`
first, then `length - index >= width`, which cannot wrap by construction. A
fallback nothing currently reaches is still a fallback, and it must not be the
weaker of the two.

## Evidence

`kbb -M:test` — **271 tests, 3411 assertions, 0 failures**, after merging
`origin/main` (the sysops general atomics, the SIMD-prep VEX work, f32 on both
ISAs, and the UEFI firmware boundary).

Every encoding was disassembled with `llvm-mc --disassemble` (LLVM 22.1.7)
*before* it was written into a golden, and the disassembly is quoted beside it.
A hand-derived encoding that decodes as something else is the one failure a
byte golden cannot catch by itself — it pins whatever the encoder produced,
correct or not.

| verified | bytes | decodes as |
|---|---|---|
| u16 load | `45 0f b7 03` | `movzwl (%r11), %r8d` |
| u64 load | `4d 8b 03` | `movq (%r11), %r8` |
| u16 store | `66 45 89 03` | `movw %r8w, (%r11)` |
| u64 store | `4d 89 03` | `movq %r8, (%r11)` |
| index mask | `49 83 e2 07` | `andq $7, %r10` |
| slice ceiling | `49 ba 00 00 00 00 00 01 00 00` | `movabsq $1099511627776, %r10` |
| scaled address | `4d 8d 1c d0` | `leaq (%r8,%rdx,8), %r11` |
| the RBP-form base | `4d 8d 5c 55 00` | `leaq (%r13,%rdx,2), %r11` |
| AArch64 alignment | `5f 08 40 f2` | `tst x2, #0x7` |
| AArch64 halfword | `03 02 40 79` | `ldrh w3, [x16]` |
| AArch64 doubleword | `03 02 40 f9` | `ldr x3, [x16]` |
| AArch64 scaled add | `21 0c 03 8b` | `add x1, x1, x3, lsl #3` |

Four deliberate breaks, each red for its own reason and then restored:

| break | red for |
|---|---|
| `0x66` prefix moved after REX in the u16 store | `"u16 store is 66 REX 89, in that order"` — the failure output shows `45 66 89 03` |
| alignment check made unreachable | the u16 and u64 masks, 3 failures |
| slice SIB scale fixed at 1 | `"slice-load-u16 scales the index by 2"` and the u32/u64 siblings |
| `unaligned-accesses` emptied | the two exemption assertions, on **both** ISAs |

The merge with `origin/main` found one thing worth recording. The sysops
general atomics call `x86-kernel-bounds-check` and its AArch64 twin, so
widening that function's signature with `aligned?` made six of their goldens
fail with an `ArityException` — loudly, at the call site, which is what a
positional argument buys over a derived one. They pass `false`: `lock`-prefixed
and LSE atomics require natural alignment architecturally, so adding the check
there would be a real change to their admitted set and would move bytes their
own goldens pin. Recorded as a follow-on beside the two u32 window exemptions,
not done in passing.

The goldens decode **fields** rather than pinning whole words wherever the
destination register is the allocator's choice. `ldrh w3, [x16]` and
`ldrh w0, [x16]` are the same claim about this encoder; pinning the register
would make these tests go red for a reason that has nothing to do with transfer
width.

`isa_parity_test` now lists all forty operations, so a gap on one ISA at one
width is a failure rather than silence — which is the whole reason that
namespace exists.

## Upstream

kotoba-kir `7aa6d2d` and kotoba-sema `87f7d32` carry the oracle and the
frontend halves. The gmir/mir/codegen pins land at `origin/main`'s values
(`11282bb` / `be99446` / `d450d46`), each of which was checked with
`git merge-base --is-ancestor` to contain this stream's own merges
(`cb935ce` / `37345aa` / `c024b11`) rather than assumed to.
