# ADR-0136: The GGUF admission runs on a CPU, and the translation is checked field by field

## Status

Accepted (2026-09-02)

## Context

ADR-0145 moved the whole of `kernel/qwen35_runtime.c`'s GGUF parser into three
Kotoba objects and made the C delegate to them under
`-DAIUEOS_QWEN35_KOTOBA_ADMISSION`, which `build-uefi.sh` defines for every
profile that compiles that file. Its own "What is NOT done" said what was
missing, and said it plainly:

> **Nothing has executed the delegation.** […] what is proven is that it LINKS,
> not that the translation from workspace to `struct aiueos_qwen35_model` is
> right. The three objects are graded by their oracles and the C reference is
> graded by `scripts/smoke-qwen35-runtime.sh`; the seam between them is not.

Two gaps, not one:

1. The emitted x86-64 had never been on a processor. This workstation is
   aarch64 and the objects are x86-64 ET_REL, so the KIR interpreter was the
   only thing that had ever run them.
2. The C that reads their workspaces and fills the struct `qwen35_infer.c`
   consumes had never run at all — in either direction. It had been read.
   Reading does not catch a field taken from the wrong workspace offset,
   because every 4-byte window of a plausible workspace is a plausible
   little-endian word.

Both are closed here.

## Decision

### 1. A boot self-test parses a real GGUF prefix, and the console carries the object's reason code

`kernel/main.c` gains a block under
`AIUEOS_QWEN38_MODEL_HANDOFF && AIUEOS_MODEL_TEST_FIXTURE`, placed after the
physical allocator so the 75,880-byte graph comes out of allocated pages rather
than growing the kernel's BSS. It runs only when the handed-off artifact is
exactly the 10,996,640-byte metadata + tensor-table prefix that
`tests/make_qwen35_header_fixture.py` builds — the model-handoff gate's own
fixture is 27 bytes of transport and carries no graph, so both fixtures now
reach this profile and the console says which one it got.

The prefix is not the artifact, so the artifact length passed is the contract's
10,934,860,704 rather than what was mapped. That is the same pair of arguments
`tests/qwen35_runtime_model.c` passes on the host, which is what makes the
numbers printed comparable with it.

`kernel/qwen35_runtime.c`'s delegating branch records the last verdict and
which object produced it in `aiueos_qwen35_admission_verdict` /
`aiueos_qwen35_admission_stage`, and the self-test prints them as
`QWEN-ADMIT reason=<n> stage=<n> admitted=<0|1>`. They are diagnostics: nothing
reads them to decide anything. They exist because `aiueos_qwen35_model_parse`
returns 0 or 1, so a boot that refuses a model could not say WHICH clause of
WHICH object refused it — and that reason literal is the only thing on the
console that could only have come from a Kotoba object.

### 2. The translation becomes a named function, and the host gate runs it

`aiueos_qwen35_model_translate` is split out of `aiueos_qwen35_model_parse`,
and a third switch, `AIUEOS_QWEN35_TRANSLATION_ONLY`, compiles ONLY that
function out of the delegating branch: no externs, no parse, no bind. No build
that produces an image sets it; `#error` refuses it without
`AIUEOS_QWEN35_KOTOBA_ADMISSION`.

That lets `scripts/smoke-qwen35-runtime.sh` build two translation units from
one source file and link them together: the C reference parser and the Kotoba
translation, in one binary, on a machine that cannot execute an x86-64 ET_REL
object.

The workspaces it feeds the translation are not synthesised. The two oracle
suites now write what a real run of each object produced —
`tests/fixtures/qwen35-kv-plan.bin` (128 bytes) and
`tests/fixtures/qwen35-tensor-plan.bin` (28,160 bytes) — and then assert on
every subsequent run that the committed bytes are the bytes that run produced.
Written by one run, verified by another; the file is pinned in both directions
and the gate cannot drift into grading the translation against a workspace no
object ever emitted.

## Evidence

### The objects on a CPU (QEMU 10.1, OVMF `edk2-x86_64-code.fd`)

`kbb --backend sci os/aiueos/scripts/smoke-qemu-qwen35-admission.cljk`, serial verbatim:

```
AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp
…
AIUEOS_QWEN35_GRAPH_FIXTURE_DEFERRED admission-selftest
AIUEOS_MODEL_HANDOFF_OK format=gguf-v3 parts=3 sha256=verified mapping=read-only-nx metrics=N/A
AIUEOS_PHYSICAL_ALLOCATOR_OK pages=2 zeroed
QWEN-ADMIT reason=0 stage=0 admitted=1
AIUEOS_QWEN35_ADMISSION_OK tensors=866 linear=48 full=16 data-offset=10996640 embd=715182080 qkv=1149091840 tail=10923843584
AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2
AIUEOS_PHYSICAL_MODEL_HANDOFF_OK qwen38-27b runtime=not-yet-present internal-disk-writes=none
```

`715182080`, `1149091840` and `10923843584` are three of the four
representative tensor offsets `tests/qwen35_runtime_model.c` asserts on the
host against the same fixture. They were derived here by
`kotoba_aiueos_qwen35_tensor_table_bind` running as x86-64 machine code and
copied into the struct by this image's translation.

`AIUEOS_QWEN35_ADMISSION_MUTATE=1` changes ONE field of ONE record — the `type`
of `token_embd.weight`, Q2_K → Q4_K, at file offset 10,945,527 — and the same
image refuses it:

```
QWEN-ADMIT reason=-21 stage=3 admitted=0
AIUEOS_QWEN35_ADMISSION_REFUSED kotoba-objects
```

`-21` is clause 21 of `kotoba/qwen35-tensor-table-bind.kotoba` ("token_embd
retyped, which the contract forbids") and stage 3 names that object.

### What that discrimination does and does not prove

It proves the decision came from the object, by two independent measurements:

* the reason literal. Under `-DAIUEOS_QWEN35_KOTOBA_ADMISSION` the C returns
  0 or 1; `-21` exists only in a `.kotoba` file and its oracle.
* the link. `nm` on the `kernel-qwen35-runtime.o` the image actually links:

  ```
  0000000000000008 B aiueos_qwen35_admission_stage
  0000000000000000 B aiueos_qwen35_admission_verdict
  00000000000005f0 T aiueos_qwen35_model_bind
  0000000000000410 T aiueos_qwen35_model_parse
  0000000000000000 T aiueos_qwen35_model_translate
  0000000000000ec0 t bind_tensor
                   U kotoba_aiueos_qwen35_gguf_header_valid
                   U kotoba_aiueos_qwen35_gguf_kv_scan
                   U kotoba_aiueos_qwen35_tensor_table_bind
  0000000000000010 b qwen35_kv_plan
  0000000000000090 b qwen35_tt_plan
  ```

  Three undefined imports the image does not link without, and not one of
  `parse_metadata`, `exact_contract_valid`, `tensor_storage`,
  `read_expected_u32`, `assign_tensor`, `type_layout` — not even as a local
  symbol, and `bind_tensor` shows locals are listed. The smoke asserts both
  halves rather than leaving them to be read.

  Red direction, measured: the same file compiled for the same target WITHOUT
  the define gives 20 symbols, zero `U kotoba_aiueos_qwen35_*`, and
  `exact_contract_valid` defined — so the check fails on both clauses. Note
  that at `-O2` five of the six named C-parser functions are inlined away and
  only `exact_contract_valid` survives; the load-bearing half of this check is
  the three undefined imports, and the symbol list is a second net rather than
  a six-strong one.

It does **not** prove that the C reference parser would have admitted the
mutated fixture. It would not: measured on this host, the reference parser
refuses it too (`FAIL exact contract admitted`), because
`exact_contract_valid` checks the same ggml-type histogram the object does. The
two implementations are built to agree and
`aiueos.qwen35-tensor-table-parity-test` exists to keep that true, so a
verdict-level disagreement would be a defect in one of them, not a gate. The
discrimination available is the reason literal and the link, and this ADR
claims only those.

### The translation, field by field

`sh os/aiueos/scripts/smoke-qwen35-runtime.sh` (Apple clang, aarch64 host):

```
AIUEOS_QWEN35_HEADER_FIXTURE_OK bytes=10996640 tensors=866 artifact=10934860704
SCANNED 34 fields MATCH 34 DIFFER 0
CONTROL corrupt=blk.0.attn_qkv.weight.d1 DIFFER 1 NAMED layers[0].mixer.linear.qkv
AIUEOS_QWEN35_RUNTIME_MODEL_OK gguf-v3 tensors=866 trunk=64 linear=48 full=16 mtp=1 bind=read-only
AIUEOS_QWEN35_TRANSLATION_OK fields=34 workspace=kotoba-oracle struct=byte-identical control=named
```

34 is every top-level member of `struct aiueos_qwen35_model`, and the gate
asserts both that the table names 34 and that its last entry reaches
`sizeof(struct aiueos_qwen35_model)`, so a member added later cannot be silently
uncompared. The whole struct is also `memcmp`'d: both are zeroed over `sizeof`
before use, so the padding is zero in both and that compare is exact rather than
approximately exact.

The CONTROL line is in the gate, not beside it. It corrupts the second
dimension of `blk.0.attn_qkv.weight` (10240 → 10241) in a copy of the
workspace the object produced and requires the comparison to report exactly one
differing top-level field and to name the tensor. A comparison that cannot go
red is not evidence that it went green for a reason.

### The oracle workspaces

```
SCANNED 866 tensor records in 83 s, verdict 0
WROTE os/aiueos/tests/fixtures/qwen35-tensor-plan.bin 28160 bytes
Ran 1 tests containing 891 assertions. 0 failures, 0 errors.

SCANNED 50 metadata entries and 495907 tokenizer strings in 307 s, verdict 0
WROTE os/aiueos/tests/fixtures/qwen35-kv-plan.bin 128 bytes
Ran 1 tests containing 18 assertions. 0 failures, 0 errors.
```

## How much C is left in the image

Preprocessed non-blank lines of `kernel/qwen35_runtime.c`, with the header's
own 232–240 lines subtracted:

| profile | lines | in an image |
|---|---|---|
| before ADR-0145 — the only implementation | 603 | yes |
| after ADR-0145 — delegating branch + bind | 192 | yes |
| **after this ADR — delegating branch + bind** | **243** | **yes** |
| reference parser (`#ifndef`) | 603 | no |
| `AIUEOS_QWEN35_TRANSLATION_ONLY` (the host gate's unit) | 130 | no |

The K16 profile grew by 51 lines, and none of them is a decision: 5 call sites
that record `verdict`/`stage` before returning 0, and 4 translation refusals
that now say which one fired. The parser is still gone — 603 → 243 against
ADR-0145's baseline of 641 physical lines, all of it C, all of it in the image.

`zig cc` was asked for and cannot run this gate: on this host it links no
hosted program at all (`zig cc hello.c` → `undefined symbol: _printf`, zig
0.15.2), because it has no libSystem to link against. It builds the freestanding
kernel because that needs no libc. The host gate runs under Apple clang, which
is what `${CC:-cc}` already selected.

## What is NOT done

1. **The full artifact has never been parsed on a CPU.** What ran is the
   10,996,640-byte prefix with the artifact length supplied as a constant, so
   `aiueos_qwen35_model_bind` — the branch taken when `accessible == artifact`
   — is still unexecuted there. Reaching it needs the real 10.9 GiB model
   mapped, which is the K16 machine, not QEMU with 1.5 GiB.
2. **One mutation, one clause.** The QEMU refusal exercises clause 21 of one of
   the three objects. The other twenty-plus clauses are exercised by the KIR
   oracle only; the boot proves the seam, not the table.
3. **`-22` and `-23` still have no case**, unchanged from ADR-0145 §2.
4. **`qualification/jvm-free-object-parity.edn` is still not regenerated**,
   unchanged from ADR-0145 §3. No `.kotoba` source and no `.o` changed here, so
   the object set and its provenance are untouched.
5. ~~**The two files numbered 0135**~~ **CLOSED.** They collided when two
   streams landed on the same day, and the first still said "ADR 0134" in its
   own heading. `…-a-kernel-object-imports-its-first-module` keeps 0135 and its
   heading now says so; `…-the-qwen38-gguf-admission-becomes-three-kotoba-objects`
   is **ADR-0145**, and the citations that meant it were re-pointed by reading
   each one rather than by rewriting every "ADR-0135" in the tree — half of them
   meant the other file.
