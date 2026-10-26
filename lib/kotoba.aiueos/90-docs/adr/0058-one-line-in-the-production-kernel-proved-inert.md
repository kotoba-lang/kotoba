# ADR-0058 — One line in the production kernel, proved inert before it was written

Date: 2026-08-18

## Status

Accepted and executable. The composite image verifier now links, and fails
where everything else fails. The local blocker ADR-0057 named is gone; the
upstream one grew.

## Context

ADR-0057 found that the whole-image verifier had never run: `compile-project`
requires an explicit `:export` vector from every module, and
`native/kernel.kotoba` — this repository's **production hard-flip input**, the
source that becomes `KERNEL.ELF` — carried none.

That is a one-line change to the file the boot path depends on, in a
repository whose evidence rules require QEMU for exactly that path, on a
machine that cannot run the Amu closure. The tempting move is to make it and
assume; the rule is not to.

## What was measured before the edit

**Which names to export was not guessed.** `aiueos.native.value-runtime-kernel`
references exactly one name from the module — `kernel/main` — so the vector is
`[main]` by measurement.

**The change is inert for the production path.** The build script runs
`kotoba-compiler compile <source> --target x86_64-aiueos-kernel-v1 --artifact
image`: a single-source compile. Compiling `native/kernel.kotoba` with and
without the export vector produces:

| | code SHA-256 | binary SHA-256 | export |
|---|---|---|---|
| as-is | `c3bd9664…ac77` | `b64afc94…f094` | `kotoba_aiueos_probe` |
| with `(:export [main])` | `c3bd9664…ac77` | `b64afc94…f094` | `kotoba_aiueos_probe` |

Byte-identical on both artifacts. The export vector is read by the project
linker and ignored by the source-mode compile — which is the same asymmetry
[amu#626](https://github.com/kotoba-lang/amu/issues/626) is about, here working
in our favour.

**This is not a QEMU boot, and does not claim to be.** It is an argument that
the input to the build is unchanged where the build looks, not evidence that
the built image boots. The next real boot re-establishes that; nothing here
should be read as having done so.

## What the composite verifier says now

It links, and then:

```
operation has no admitted type signature   {:form kernel-compare-exchange-u32}
```

The eleventh measurement moved from `:project-module-missing-export` — work
here — to the wall every other object hits. **`kernel-compare-exchange-u32`
now accounts for 5 of 11 failures, and one of the five is the image itself.**
Nothing in the value runtime links without it. [amu#625](https://github.com/kotoba-lang/amu/issues/625)
updated with that.

Cause histogram: `:native-slice-typed-values` 7, `:per-object-export-symbol` 3,
`:native-slice-lowering` 1. The `:project-module-missing-export` class is
empty and its entry stays in `upstream-by-cause` — that map is a routing table
for a class that may recur, not a claim about the present, and the floor that
matters (`every-failure-class-points-at-where-the-work-is`) reads the failure
histogram rather than the table.

## Executable evidence

Full suite **628 tests, 9388 assertions, 19 failures** — the baseline
nineteen. `value-runtime-baseline-test` green with the ratchet unchanged at
eleven objects, eleven failing, zero passing. Lint unchanged.

The discriminating evidence for this change is the digest table above rather
than a mutation: the claim is *"this edit changes nothing the build sees"*, and
two identical SHA-256 pairs are the direct measurement of it.

## Remaining boundary

- **Eleven failing, and now five of them are one intrinsic.** The value runtime
  is one upstream answer away from linking, and no distance at all from
  running.
- **No boot has been performed** since the edit. The inertness argument covers
  the compiler's output, not the image's behaviour on hardware or in QEMU.
- `:per-object-export-symbol` (3) and `:native-slice-lowering` (1) are
  untouched.
