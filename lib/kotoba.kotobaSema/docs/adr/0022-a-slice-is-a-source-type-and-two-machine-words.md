# ADR-0022: A slice is a source type and two machine words

> **Renumbered.** This landed as ADR-0009 and collided with
> `0009-a-second-base-in-a-second-family.md`, which landed the same day.
> The coordinator's allocation table assigns this stream `0022`, so the file
> moved and the other stream's `0009` stayed put. References to **"kotoba-sema
> ADR 0009"** in kotoba-kir ADR 0240, kotoba-verifier ADR 0028 and amu ADR 0314
> mean this file.

- Status: accepted
- Date: 2026-09-02

## Context

amu ADR 0285 decided that the bulk carrier for GiB-scale memory must be
*addressable memory, not a bigger vector*, and refused to raise
`vector-item-limit`. The MEMWIDTH stream landed the machine half of that
decision: `slice-{load,store}-u{8,16,32,64}`, element-indexed, ceilinged at
2^40 items, four checks, a scaled index in the SIB byte, and **zero context
callbacks** in the loop.

What it deliberately did not land was a slice **value**. Every one of those
operations takes `base length index [value]` as three or four separate i64
words, so a program that walks a region threads two of them through every
call and re-proves the provenance of the base at each one — which is what the
aiueos objects do today, and it costs a parameter slot out of five.

kotoba-native's `docs/lang-authority-diff.md` wrote the gap up as four
possible routes and named erasure (its route 3) as the cheapest.

## Decision

`[:slice T]` for `T ∈ {:u8 :u16 :u32 :u64}` is a type of **this frontend's
source syntax and of nothing else**, carried by eight operations:

```clojure
(slice-of-u8 base length)   ; -> [:slice :u8]   length counts ELEMENTS
(slice-of-u16 base length)  ; -u32, -u64
(slice-length s)            ; -> :i64           elements, not bytes
(slice-get s index)         ; -> :i64           the element, zero-extended
(slice-set! s index value)  ; -> :i64           the value (kotoba-native ADR 0051)
(slice-sub s offset count)  ; -> [:slice T]     a CHECKED narrowing
```

`erase-slice-values` rewrites all of it into the machine family before any
other pass runs. A slice parameter becomes two i64 parameters named
`__kotoba_slice_<p>_base` and `__kotoba_slice_<p>_len`; a slice `let` binding
becomes two bindings; `slice-get` becomes `slice-load-u<w>`; `slice-sub`
becomes `kernel-subregion` with the element scale applied, so the narrowing is
written in elements and checked in bytes.

**`[:slice :f32]` is declared and refused.** It is the element type the
carrier is *for* — the Qwen weights are binary32 — and there is no
`slice-load-f32` on either native ISA to reach one with. Naming it and
refusing it by name is the honest record; recording it as available would be
amu ADR 0284's defect in miniature, an admission that admits what nothing can
lower.

## Where the type stops existing, and what enforces it

`erase-slice-values` runs immediately after `resolve-overloaded-calls` (which
must see the source arities) and after the `:param-types` defaulting (which it
reads), and **before** loop-helper type resolution, absent-parameter and
absent-result inference, abort elaboration, `validate-expr`,
`check-value-types!`, `check-kernel-region-provenance!`,
`check-lowering-budget!` and HIR construction. Downstream of that line the
program is `:i64` words and operations that already had a lowering.

Three independent things keep it there:

1. **This pass** refuses, each with its own `:kotoba.error/` code: a slice
   returned (`slice-result-type`), mentioned anywhere but a slice position
   (`slice-escape`), given to a non-slice parameter or given an i64
   (`slice-operand`), given the wrong element width
   (`slice-element-mismatch`), built from arithmetic
   (`slice-region-provenance`), on an exported function or on `main`
   (`slice-export-boundary`), or pushing a function past five machine words
   (`slice-erased-max-parameters`).
2. **`kotoba.kir`** refuses a `[:slice T]` in `:param-types` by name, so a
   failure to erase says which invariant broke rather than falling through the
   generic typed-value refusal (kotoba-kir ADR 0240).
3. **`kotoba.verifier`** refuses it again from its own table (kotoba-verifier
   ADR 0027).

The export refusal is made after the export list is known rather than in the
pass, because refusing *every* slice parameter would forbid the only shape the
carrier is for: an internal traversal handed a region by the module's own
entry point.

## Consequences

- **No IR gains a slice.** GMIR, MIR, codegen and both native backends are
  untouched by this change. `docs/lang-authority-diff.md`'s routes 1 and 2 — a
  second `pilot-expression?` shape and a two-slot spill in the x86-64 fallback
  — turn out not to be needed at all rather than merely to be dearer:
  `pilot-expression?` already answers `:scalar` for a four-operand
  `slice-load-u8`, because `kir-kernel-memory-ops` has carried the slice family
  since the lowering landed.
- **The taint scanner now sees the base.** `kernel-base-uses` reads argument 0
  of a machine operation; a carried operation's base is *inside* the value, so
  before erasure there is nothing at argument 0 to read. Erasure is what makes
  it visible, and `kernel-region-report` names the erased half at the ABI
  boundary exactly as it names a hand-written base parameter. The
  slice-specific provenance refusal in this pass is therefore a **second**
  check, not the only one: with it deleted, the generic rule still catches a
  computed base after erasure, with `:kotoba.error/kernel-region-provenance`
  instead. Both directions are pinned by test.
- **The two spellings coexist.** `(slice-load-u8 base length index)` is still
  admitted and is what the carrier compiles to. A carried traversal and the
  same traversal written by hand analyse to the same tree once the synthesised
  names are substituted back, and compile to identical bytes (amu ADR 0295).
- **A module that does not use the carrier is returned unrewritten** — the
  identical object, not an equal one — so no shipped aiueos object moves.
- **Not admitted, deliberately:** a slice in a record, set, option, result or
  vector; a slice returned; `(if c s1 s2)` as a slice; a slice captured by a
  `loop` (its helper's parameters carry no annotations, so there is nothing to
  read the element type from). Each is a refusal with a message, not a silent
  miscompile.

## Finding, not repaired here

`function-arities` in `analyze*` still decides a clause's arity by the old
alternating-pairs heuristic (`(quot (count raw-params) 2)` when any item looks
like a type), while `typed-param-parts` decides it per item. They disagree for
any *mixed* annotation — `[s :string i total]` counts as arity 2 — which
predates this change and is not specific to slices. Fixtures here annotate
every parameter to stay on the side the heuristic gets right.
