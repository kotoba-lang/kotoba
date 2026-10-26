# ADR-0032 — Three shipped objects that could not be rebuilt, and the reproducibility check that hid it

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0031

## Context

ADR-0031 found a signedness bug in `store64` — `(quot value 256)` is a signed
`idivq` truncating toward zero, not an arithmetic shift — in an object that was
already shipping. That instance was found by accident, so the disciplined
follow-up was to look for siblings across all 59 objects.

**The audit came back negative, and that is a real result.** 112 `quot` sites in
23 files, every one classified by tracing where its dividend comes from:
**0 wrong, 0 latent, 112 safe.** Only four sites in the whole tree divide a real
64-bit address — `idt-gate-build`'s handler, both `store64`s, and
`mmio-map-admit`'s address — and three were already correct.
`idt-gate-build` survives because `low`/`high` are masked and `(- handler low)`
is an exact multiple of 2^32; `mmio-map-admit` because its `or` short-circuits
and `(< address 2^30)` rejects every negative first. **`kernel-read-msr`'s value
is never divided anywhere**, so LSTAR — the higher-half address I most suspected —
never meets a `quot`.

Proven by execution against the real shipped objects, including a naive
divide-first model that reproduces the original `store64` measurements digit for
digit, which is what makes the negative trustworthy rather than merely asserted.

But the audit surfaced something worse than the bug it went looking for.

## The finding

**Three objects that ship in the image can no longer be compiled from their own
source.** `service-registry-build`, `mutable-object-build` and
`user-object-journal-build` all fail `:kotoba.error/subset-reject` — *"if
branches must have the same value type"* — at compiler `origin/main` `4c9650e`.

The cause is a legitimate tightening. `frontend.cljc:4809-4817` requires exact
type equality between `if` branches; `=` and the ordering comparisons became
`:bool` where they were `:i64`; and unannotated `defn` results are now inferred
from the body rather than defaulting to `:i64`. So a helper ending in an
`and`-of-`=` is now `:bool`, and `(if c <helper> 0)` straddles two types.
`and`/`or` desugar to a synthetic `if` carrying no source metadata, which is
exactly why `service-registry-build`'s diagnostic reports **no span**.

**Why nobody noticed:** `scripts/reproduce-kotoba-kernel-object.sh` pins compiler
`0b16d9b6`. Reproducibility was being maintained by freezing the toolchain rather
than by keeping sources valid. And that script covers **36 of the 56 objects
linked into the image** — every object added during 2026-08 (`pci-config-read/write`,
`mmio-map-admit`, the ACPI and VT-d admissions, `msr-read/write`, `idt-gate-build`,
`pic-disable`, the three `cpu-*`, `kernel-context-build`, the IPv4/TCP objects,
`x25519`, `net-arp-reply-valid`) has **no reproducibility check at all**.

This matters beyond tidiness. The architecture's claim (ADR-0015) is that every
decision in this OS is *compiler-emitted Kotoba*. For these three, the shipped
bytes were trusted but not regenerable, so that claim was unverifiable.

## Decision

Repair all three so they compile at `origin/main`, preserving behaviour.

Two are pure type bridges using an idiom nine sibling objects already use —
`(if (= length 512) 1 0)` in place of a bare `(= length 512)` inside a mixed
`and` chain. Every exported function keeps result type `:i64`, matching both the
shipped object and the C prototype.

**The third is not a compile fix, and is recorded as a deliberate semantic
change.** `mutable-object-build` passed `(+ object 24)` as a memory base, which
a second tightening now rejects: *"kernel memory base must name a region, not
compute one"* (`frontend.cljc:6349-6372`). A bare `+` in base position produced a
window nothing had checked; the admitted spelling is
`(kernel-subregion object object-length 24 16)`, which the backend emits as a
real bounds check.

So the rebuilt object is **stronger than the shipped one**, not identical to it.
The divergence band is `object_length ∈ [24,39]` or `transaction_length ∈
[16,31]` — where the metadata writes fit but the 16-byte payload window does not.
There the shipped object read and wrote an unchecked window and returned 1; the
rebuilt one traps. Below that band both already trap. The sole caller
(`pci.c:329`) passes hard-coded `512` and `32`, so the band is unreachable. The
change is accepted in the direction the tightening intends.

## Consequences

- **Differential old-`.o` vs new-`.o`: 73 cases, 0 unexpected divergences**, with
  inputs derived from the actual C call sites plus each object's guard-rejection
  cases. Every call ran in a forked child against a `MAP_SHARED` arena so traps
  were observed rather than fatal, comparing return value, the full 8 KiB
  poisoned output arena byte for byte, the input buffer, and `.data`. The only
  divergences are the five deliberately-probed unreachable-length cases above.
  30 byte-pattern assertions confirm the rebuilt objects still produce the
  `AIUJRN2`/`AIUOBJ1` records the journal-recovery smoke asserts on — otherwise
  two functions that both did nothing would have passed silently.

- On target: `AIUEOS_SERVICE_REGISTRY_OK … decoder=kotoba`,
  `AIUEOS_KOTOBA_STORAGE_WRITE_OK journal mutable-object`,
  `AIUEOS_KOTOBA_OBJECT_WRITE_OK … serializer=kotoba validator=kotoba`,
  `AIUEOS_OBJECT_TXN_OK … route=kotoba`.

- **`kotoba/*.o` contains artefacts of at least two compiler vintages.** Of the
  22 remaining pinned objects, 14 reproduce byte-identically at `4c9650e` and
  **8 do not**: `app-catalog-valid`, `capability-mutation-plan`, `capability-plan`,
  `journal-record-build`, `rsa2048`, `scheduler-dispatch-plan`,
  `service-task-transition`, `sha256`. All eight differ in the same two ways —
  `.text` shrank (better instruction selection), and `.data[8]` went **256 → 512**.
  That word is the per-object bounded-memory fuel budget, and **the 14 identical
  objects already carry 512**. So these eight were simply never rebuilt after the
  fuel base changed, and are running on half the headroom the current compiler
  considers correct — a latent prologue `ud2` on any input crossing 256 bounded
  operations. The direction is safe (512 can only complete work 256 would have
  trapped on), and the two that drifted most were fuzzed clean over 1,088,877
  comparisons, but six were not tested behaviourally and no claim is made for
  them.

- **`reproduce-kotoba-kernel-object.sh` is left failing for these three, on
  purpose.** Its `cmp` now mismatches, and bumping its compiler pin to `4c9650e`
  cannot be done today because eight other objects do not reproduce there.
  Repairing it *is* the eight-object rebuild; they are one task, not two, and
  doing it properly needs a per-object differential rather than a bulk recompile.
  Recorded as the next increment rather than papered over.

- **The check to add is coverage, not just a pin bump.** A reproducibility script
  that silently covers 64% of what ships, against a frozen compiler, cannot
  detect either failure mode found here. Whatever replaces it should derive its
  object list from `build-uefi.sh` so that adding an object to the image without
  adding it to the check is impossible.
