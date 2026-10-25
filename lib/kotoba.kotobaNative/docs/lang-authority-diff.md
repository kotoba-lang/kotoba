# The kotoba-lang authority diff this change proposes

Stream MEMWIDTH does **not** edit `kotoba-lang` this wave — the F32 stream owns
that repository's edits, and the orchestrator folds these in. This file is the
diff, written where it can be reviewed against the encoders it describes rather
than asserted from a distance.

Measured against `kotoba-lang` `aa9b49f`.

---

## 1. `lang/guest-grammar.edn` — `:admitted-builtins`

Today the set names three kernel memory operations:

```clojure
"kernel-load-u8" "kernel-store-u8" "kernel-boot-info"
```

That was already behind the frontend before this change: `kernel-load-u8-4k`,
`kernel-load-u8-16k`, `kernel-store-u8-4k`, `kernel-load-u32`,
`kernel-store-u32`, `kernel-subregion` and the lock pair have all been in
`kotoba.compiler.frontend`'s `kernel-memory-operations` and in both backends,
without ever reaching this list. **The authority understates the surface by
seven operations before a word of this change.**

Proposed replacement (thirty-eight window operations plus eight slice
operations plus `kernel-subregion` and the lock pair):

```clojure
 ;; Checked kernel memory. Four transfer widths by four window tiers, plus the
 ;; element-indexed slice family. Byte-indexed windows take
 ;; `base length index [value]` and cap `length` at their tier; slices take the
 ;; same shape but count ELEMENTS and cap `length` at 2^40.
 "kernel-load-u8"       "kernel-store-u8"
 "kernel-load-u8-4k"    "kernel-store-u8-4k"
 "kernel-load-u8-16k"   "kernel-store-u8-16k"
 "kernel-load-u8-64k"   "kernel-store-u8-64k"
 "kernel-load-u16"      "kernel-store-u16"
 "kernel-load-u16-4k"   "kernel-store-u16-4k"
 "kernel-load-u16-16k"  "kernel-store-u16-16k"
 "kernel-load-u16-64k"  "kernel-store-u16-64k"
 "kernel-load-u32"      "kernel-store-u32"
 "kernel-load-u32-4k"   "kernel-store-u32-4k"
 "kernel-load-u32-16k"  "kernel-store-u32-16k"
 "kernel-load-u32-64k"  "kernel-store-u32-64k"
 "kernel-load-u64"      "kernel-store-u64"
 "kernel-load-u64-4k"   "kernel-store-u64-4k"
 "kernel-load-u64-16k"  "kernel-store-u64-16k"
 "kernel-load-u64-64k"  "kernel-store-u64-64k"
 "slice-load-u8"        "slice-store-u8"
 "slice-load-u16"       "slice-store-u16"
 "slice-load-u32"       "slice-store-u32"
 "slice-load-u64"       "slice-store-u64"
 "kernel-subregion" "kernel-try-lock-u32" "kernel-unlock-u32"
 "kernel-boot-info"
```

---

## 2. `lang/surface-status.edn` — a new `:checked-memory` family

There is no entry for kernel memory at all, so it currently falls to
`:default-for-missing` (`:not-yet-implemented`) while being shipped on both
native ISAs — the same shape the file records for floating point. Proposed,
following the `:native-homogeneous-vectors` template:

```clojure
 :checked-memory
 {:kernel-memory-windows
  {:disposition :implemented-partial
   :surface #{kernel-load-u8 kernel-store-u8 kernel-load-u16 kernel-store-u16
              kernel-load-u32 kernel-store-u32 kernel-load-u64 kernel-store-u64
              kernel-subregion kernel-try-lock-u32 kernel-unlock-u32}
   :implementation #{:compiler-native-host}
   :value-families #{}   ; every operand and result is an ordinary i64 word
   :semantics :caller-declared-window-checked-at-every-access
   :bounds {:window-tiers #{512 4096 16384 65536}
            :access-widths #{1 2 4 8}}
   :checks [:length-within-tier :non-null-base :index-below-length
            :access-width-fits-tail :natural-alignment]
   :alignment
   {:rule "index mod access-width = 0, checked last"
    :reason "a misaligned MMIO access is architecturally undefined on AArch64
             device memory and splits the bus lock on x86; the machine's
             answer to one is not a value"
    :exempt #{kernel-load-u32 kernel-store-u32
              kernel-try-lock-u32 kernel-unlock-u32}
    :exempt-reason "these predate the rule; retrofitting it would change the
                    bytes of shipped aiueos objects. Recorded as an asymmetry,
                    pinned by a test, and closable only with a re-pin."}
   :provenance :base-must-name-a-region-not-compute-one
   :host-abi {:trap :ud2-or-brk}
   :evidence "kotoba-native ADR 0042; byte goldens cross-checked against
              llvm-mc 22.1.7; kotoba-kir ADR 0229 oracle parity"}

  :slice-carrier
  {:disposition :implemented-partial
   :surface #{slice-load-u8 slice-store-u8 slice-load-u16 slice-store-u16
              slice-load-u32 slice-store-u32 slice-load-u64 slice-store-u64}
   :implementation #{:compiler-native-host}
   :semantics :element-indexed-host-supplied-region
   :bounds {:items 1099511627776 :element-widths #{1 2 4 8}}
   :ceiling-is :address-space-not-vector-arena
   :checks [:length-within-item-limit :non-null-base
            :base-naturally-aligned :index-below-length]
   :element-cost "one unsigned compare and one scaled load; no context callback"
   :limits [:no-single-value-carrier :element-type-f32-declared-not-admitted]
   :decided-by "amu ADR 0285"
   :evidence "kotoba-native ADR 0042; the scale is read out of the x86 SIB byte
              and the AArch64 ADD shift field by byte goldens"}}
```

`:bounded-admission` (`:intentional-security-constraint`) is **not** widened by
any of this: every bound above is new and fail-closed, and none of the existing
ceilings — `vector-item-limit` 16384, `:vector-item-capacity` 65536,
`:vector-capacity` 4096, `:bytes {:max-value-bytes 65536}` — moves. That is amu
ADR 0285's second decision and it is honoured literally.

---

## 3. What the authority must NOT yet say

> **Superseded 2026-09-02 by the SLICE-VALUE stream.** This section said
> `[:slice T]` was not a type and must not become one until something could
> produce a slice value. Something now can: kotoba-sema ADR 0022 admits
> `[:slice T]` for `T ∈ {:u8 :u16 :u32 :u64}` as a type of the SOURCE SYNTAX
> and erases it into the two i64 words below before HIR. The four steps at the
> end of this section are answered in the addendum after them — three of them
> by turning out not to be needed. `[:slice :f32]` remains declared and not
> admitted, exactly as this section asks.

**`[:slice T]` is not a type.** ADR 0285 asks for a two-word (base, length)
carrier a `let` binds, a function parameter carries and `slice-sub` narrows.
What exists is the machine layer it lowers to: three separate i64 operands.

So the authority must **not** gain a `[:slice T]` type descriptor, and
`kotoba.kir/native-word-value-type?` deliberately does not list one. Nothing
produces a slice value, so nothing admits one — an admission gate that admits
what nothing can lower is the defect amu ADR 0284 named, and 0285's closing
section refuses to create a second instance of it.

`[:slice :f32]` is likewise **declared and not admitted**: it is named in this
file as an element type the carrier is intended to reach, and the F32 stream
owns admitting it. Recording it as available before an f32 exists on native
would be the same defect in miniature.

### What the single-value carrier still needs

The gap is a **register-allocator** change, not a machine-code one. Both
backends already emit the loads, the stores and the bounds checks; what neither
can do is carry a two-word value.

1. `kotoba.native.machine-ir/pilot-expression?` knows exactly one value shape,
   `:scalar`. A slice needs a second, and `value` must return a register *pair*
   rather than a register.
2. `kotoba.native.x86-64`'s fallback path keeps every value in RAX with stack
   pushes; a two-word value needs a second accumulator and a two-slot spill.
3. `kotoba.gmir` / `kotoba.mir` need a two-register SSA value, or the frontend
   needs to erase slices into two i64s before KIR (scalar replacement, which
   the record path already does for a directly nested `record-new` and which
   would generalise).
4. `kotoba.compiler.frontend` needs `[:slice T]` in its type system, with
   construction restricted to a parameter, a `kernel-boot-info`-derived region
   or `slice-sub` — the provenance rule that
   `kernel_region_provenance_test.clj:11-17` already enforces for a base.

Route 3-by-erasure is the cheapest and needs no new IR value: a slice
parameter becomes two i64 parameters and a slice `let` becomes two bindings,
which is exactly the shape the operations landed here already take.

### Addendum, 2026-09-02: what the four steps cost

Route 3-by-erasure was taken, in `kotoba.compiler.frontend/erase-slice-values`
(kotoba-sema ADR 0022). Reading the four steps back against it:

1. **`pilot-expression?` needed no second value shape.** It already answers
   `:scalar` for a four-operand `slice-load-u8`, because
   `kir-kernel-memory-ops` has carried the slice family since the lowering
   landed. This step was not merely dearer than route 3 — after erasure there
   is nothing to widen.
2. **The x86-64 fallback needed no second accumulator or two-slot spill**, for
   the same reason: the erased program has no two-word value in it.
3. **`kotoba.gmir` / `kotoba.mir` needed no two-register SSA value.** This was
   the step written as "or the frontend needs to erase slices before KIR",
   and that is the half that happened.
4. **`kotoba.compiler.frontend` gained `[:slice T]`** with construction
   restricted to a parameter, a literal, `kernel-boot-info`, a
   `kernel-subregion`-derived region or `slice-sub`. The provenance rule is
   the one `kernel_region_provenance_test.clj` already enforced — the carrier
   inherits it rather than restating it, because after erasure the base sits
   at argument 0 of a machine operation where `kernel-base-uses` already
   looks. A computed base is refused twice: once by name at the constructor
   (`:kotoba.error/slice-region-provenance`) and once by the generic rule
   after erasure. Both directions are pinned by test.

**This repository is unchanged by the carrier.** Not one encoder, table or
gate here moved. The evidence is amu ADR 0314: a carried traversal and the
same traversal written with the machine operations compile to **identical
objects** on both ISAs at every element width, and aiueos ADR 0160 boots one
of them — a `[:slice :u8]` passed as a function parameter, summed on a real
page under QEMU (`0000082000000410SLC`, exit 33).

Sections 1 and 2 above still stand as the diff to apply to `kotoba-lang`, with
one change: `:slice-carrier`'s `:limits` should now read
`[:element-type-f32-declared-not-admitted]` — `:no-single-value-carrier` is
no longer true — and the family gains the eight carried operations
`slice-of-u{8,16,32,64}`, `slice-length`, `slice-get`, `slice-set!` and
`slice-sub` beside the eight machine ones.

---

## 4. `lang/capability-semantics.edn`

No change proposed. `:host/mmio-map` already exists as a capability kind, and
none of these operations is a capability call — they are arithmetic over a
region the caller was handed, which is why the provenance rule rather than a
grant is what constrains them.
