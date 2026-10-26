# ADR-0145: The Qwen3.8 GGUF admission becomes three Kotoba objects

## Status

Accepted (2026-09-02)

## Context

`kernel/qwen35_runtime.c` is 641 lines of C that answers one question: is the
10,934,860,704-byte supervisor read-only mapping the kernel was handed the
model this OS boots with. It parses the GGUF v3 container header, walks 50
metadata key/value pairs against 31 required keys, walks 866 tensor records
against an exact graph, and checks that the extents tile the artifact exactly.
`contracts/qwen38-qwen35-runtime-v1.edn` is the graph it checks against.

ADR-0015 draws the C boundary at MECHANISM: C owns registers, MMIO, the GDT
and paging, and the judgements are compiled Kotoba linked into the ELF. A GGUF
admission is not mechanism. It is an admission decision taken against
firmware-supplied bytes, which is the shape every object in `os/aiueos/kotoba`
already holds -- `user-elf-valid`, `app-catalog-valid`, `acpi-table-valid`,
`dhcp-reply-valid`.

It was also the largest decision left in C, and the one with the most surface:
31 key literals, 27 tensor-name literals, 15 quantisation layouts, and a
65-layer hybrid schedule.

## Decision

Three objects, not one, because a kernel object exports one symbol and cannot
call another (ADR-0030), and because the three answer different questions.

| entry | arity | what it decides |
|---|---|---|
| `aiueos-qwen35-gguf-header-valid` | 3 | is this the file |
| `aiueos-qwen35-gguf-kv-scan` | 4 | what does it say it is |
| `aiueos-qwen35-tensor-table-bind` | 5 | where is every tensor |

kotoba-native admits the three exports and gives the second and third their own
fuel arms (kotoba-lang/kotoba-native#100, merged as `132be6c8`).

### None of the three is a boolean

The C returns 0/1. A caller handed a 10.9 GiB window and told only "no" cannot
tell a truncated mapping from the wrong file from a tensor whose shape moved.
All three return a REASON CODE with **zero as the success value**, the
`aiueos-dhcp-reply-valid` convention -- and negative, because the second and
third return file offsets and counts into a workspace on the success path, and
a file offset must never be confusable with a verdict.

The codes carry structure rather than being a flat enumeration:

* the metadata scan's `-100-k` is "required key k had the wrong GGUF type",
  `-200-k` is "wrong value", and `-(50 + slot/4)` names the workspace slot
  whose contract scalar disagreed;
* the tensor table records WHICH of the 866 records refused, in the workspace
  at byte 28148, because a code alone says a table of 866 records is wrong and
  nothing more.

The header object repeats the metadata scan's `-5..-8` rather than being called
by it. Repeating the code as well as the check is what stops two objects from
disagreeing about what a bad magic is called.

### They publish file offsets, never pointers

`aiueos_qwen35_model_bind` exists in the C because parsing an 11 MB prefix must
not fabricate pointers into bytes nobody mapped. `aiueos-qwen35-tensor-table-bind`
publishes FILE OFFSETS, so that property is structural rather than a rule a
future edit could drop: a caller adds its own mapping base, and an object that
never saw the mapping cannot invent a pointer into it.

### The C keeps buffer plumbing, and keeps a reference nobody ships

`kernel/qwen35_runtime.c` now holds two implementations of
`aiueos_qwen35_model_parse`, selected at compile time:

* `-DAIUEOS_QWEN35_KOTOBA_ADMISSION` -- calls the three objects, reads their
  workspaces, and translates them into `struct aiueos_qwen35_model`, which is
  the shape `qwen35_infer.c` reads. `build-uefi.sh` defines it on the only
  compile of that file, so **no image contains C GGUF parsing**.
* undefined -- the C parser, which is now the HOST REFERENCE. This workstation
  is aarch64 and the objects are x86-64 ET_REL, so
  `scripts/smoke-qwen35-runtime.sh` and `tests/qwen35_runtime_model.c` cannot
  run the objects; keeping the parser compilable is what keeps the fixture and
  the four representative tensor offsets gated on a machine that can execute
  something.

The `#else` branch is **not a runtime fallback**. Nothing selects it at run
time and no shipped artifact contains it. Deleting it instead would have
deleted the only executable check available here and put nothing in its place.

What survives in the delegating branch is 180 lines: two workspaces, a
little-endian load, a role-and-layer to struct-field switch, and the scalar
copies. It decides one thing the objects cannot, because it is about the
struct rather than the file -- two records claiming the same field -- and
refuses rather than recovering.

### The workspaces record what the C computed and discarded

`read_expected_array_length` walks the 248,320-string token array and the
247,587-string merge array to prove they parse, then throws away where they
are. Any later reader -- a tokenizer -- would have to walk 495,907
length-prefixed strings again. The metadata workspace records both coordinate
triples (offset, count, end). That is the reason these objects write a
workspace at all rather than returning a verdict.

### Two stated narrowings, both in the refusing direction

1. `qwen35.attention.layer_norm_rms_epsilon` is a float32 and this dialect has
   none, so the C's range check is done on the IEEE-754 bit pattern, which is
   monotonic in the value for positive finite floats. That admits exactly the
   positive floats in [0.0000009f, 0.0000011f]. A NaN compares false against
   both of the C's comparisons, so **the C admits NaN here and the object
   refuses it**. Against a value the artifact does not carry: its epsilon is
   1e-6f, bits 897988541.
2. `tensor_storage` guards its multiplications against `UINT64_MAX`. The object
   guards them against 17,592,186,044,416 elements and against the artifact's
   own 10,934,860,704 bytes, because an i64 has no unsigned half to compare in
   and a wrapped product compares small. Nothing that survives the C's guard
   and fails this one could also survive the C's very next test.

## Measured

### The oracles

All three are driven through the KIR interpreter, which models the same three
window checks the backends emit (`kernel-window-check!`), so the oracle covers
the bounds and not only the arithmetic. It does not execute the emitted
x86-64: this workstation is aarch64 and the objects are ET_REL kernel objects.

The fixtures are rebuilt in the tests -- entry for entry, record for record,
in `tests/make_qwen35_header_fixture.py`'s own order -- and each is pinned to
the sha256 of the corresponding slice of a fixture
`scripts/smoke-qwen35-runtime.sh` fed to the C:

| slice | bytes | sha256 |
|---|---|---|
| metadata section `[0, 10945379)` | 10,945,379 | `3d8de66dcd73318a4a8b176934eba1db2d3fadf39b51da8fea431e6b79260196` |
| tensor table `[10945379, 10996621)` | 51,242 | `cd3b1c42d92d9dd0918f87ea2cdd9fb5023577d269006e9cae91a930166942cc` |

A test that needed that 10.9 MB generated file present would report green when
it is absent. A test that built its own idea of GGUF would grade the object
against itself. The pin is what makes it neither.

The tensor test additionally reproduces the four tensor offsets
`tests/qwen35_runtime_model.c` asserts against the same fixture, and that C
gate passes on this workstation -- so the numbers this suite calls correct were
produced by the C rather than by the test.

### The image links, and carries no C GGUF parser

`AIUEOS_QWEN38_MODEL_HANDOFF=1 sh os/aiueos/scripts/build-uefi.sh` -> exit 0,
`BOOTX64.EFI` written. `build-uefi.sh` verifies all three on the way through:

    AIUEOS_KOTOBA_OBJECT_OK export=kotoba_aiueos_qwen35_gguf_header_valid  imports=0 relocations=1
    AIUEOS_KOTOBA_OBJECT_OK export=kotoba_aiueos_qwen35_gguf_kv_scan       imports=0 relocations=1
    AIUEOS_KOTOBA_OBJECT_OK export=kotoba_aiueos_qwen35_tensor_table_bind  imports=0 relocations=1

The compiled `kernel-qwen35-runtime.o` carries the three Kotoba symbols as
UNDEFINED and zero of `parse_metadata` / `exact_contract_valid` / `skip_value`,
which is the check that the delegating branch is the one that was built and
that the C parser is not in the image.

All 34 top-level fields of `struct aiueos_qwen35_model` are assigned by the
delegating branch -- checked mechanically against the header, because a field
the translation forgets is a zero that `qwen35_infer.c` would read as data.

The host reference is unchanged and still green:
`sh os/aiueos/scripts/smoke-qwen35-runtime.sh` ->
`AIUEOS_QWEN35_RUNTIME_MODEL_OK gguf-v3 tensors=866 trunk=64 linear=48 full=16 mtp=1 bind=read-only`.

### A silently dropped form, found by the oracle

`aiueos-qwen35-tensor-table-bind` refused the admitted table with -16 at record
338. 338 is the first tensor whose offset passes 2^32, and the cause was this
shape:

```clojure
(let [nextoff ...]
  (pput plan 28136 <low word>)
  (pput plan 28140 <high word>))
```

**A `let` whose body has more than one form compiles with `:ok true` and keeps
only the FIRST.** Measured against amu `b1fdaad2` with a two-store probe: the
compiler accepts it and emits one store. So the cursor's high word was never
written, and every offset below 4 GiB compared equal while the first one above
it did not. The fix is an explicit `do`; the object says so where it sits.

This is worth recording beyond this repository: the failure is silent at
compile time, and the only reason it was caught is that the oracle ran the
whole table rather than a sample. A sample of the first 300 records would have
been green.

### The gates were shown to fail

Every object had both directions demonstrated before it landed, and the object
was restored before the recorded run.

| object | break | result |
|---|---|---|
| header | magic `1179993927` -> `...28` | admitted header refused -5; distinct-code floor 9 -> 6 |
| header | tensor-count clause returns -6 | floor 9 -> 8; `(not (= -7 -6))` |
| kv-scan | version clause returns -5 | floor 11 -> 10; `(not (= -6 -5))` |
| kv-scan | `expect-str` for architecture -> `"gpt2"` | admitted section refused -200 after 13 s |

### Why the metadata oracle is slow

A length-prefixed array can only be traversed element by element -- that is
what the C does and what the object does -- so ADMITTING the artifact costs
~496,000 interpreter calls. The KIR interpreter recurses on its host stack with
no tail-call elimination, so the object chunks its walk at 512 (host depth
~2*sqrt(n) instead of n) and the test runs it on a 1 GiB stack thread. Measured
on this workstation at load ~200: ~312 s for the admitting walk. Only two of
its thirteen cases pay for one.

The chunking is not only for the oracle. On the machine the backend emits a
self tail call as a jump, so the outer loop costs 970 extra fuel and nothing
else; and inlining `skip-string` into the chunk loop took the walk from five
charged calls per element to one, which is 496,000 fuel instead of 2.5 million.

### Fuel

kotoba-native gives the two walking objects their own arms, both COMPUTED and
labelled so:

* `qwen-metadata-fuel?` = 250,000,000. The bound is not the artifact's shape.
  It is the widest shape the object must REFUSE: `skip_value` admits string
  arrays of up to 1,000,000 elements in each of 50 metadata entries, which is
  50,000,000 traversal steps spent before the object can say no -- a hundred
  times what accepting costs.
* `qwen-tensor-fuel?` = 10,000,000. 866 records x 810 comparison calls if every
  role candidate is exhausted, plus arithmetic and workspace writes.

The header object takes no arm: it reads four fields and costs single-digit
fuel. The immediates were read back out of the compiled objects at file offset
75 and are `00 04 00 00`, `80 b2 e6 0e` and `80 96 98 00`.

## Pins

* kotoba-native `132be6c8` (kotoba-lang/kotoba-native#100) admits the three
  exports in both twins and adds the two fuel arms. Failure direction shown on
  the `.clj` twin only, for both the table and the tier.
* amu `b1fdaad2` with that kotoba-native, via a local `deps.edn` bump and a
  regenerated `deps-lock.edn`. **amu is not landed**: the bump exists only in
  the worktree that produced these objects, and the next amu release picks the
  same kotoba-native up through its own pin.

## What is NOT done

1. ~~**Nothing has executed the delegation.**~~ **CLOSED by ADR-0136**
   (2026-09-02), along the resume point this item named. The three objects ran
   as x86-64 machine code in a QEMU/OVMF boot over the 10,996,640-byte fixture
   (`AIUEOS_QWEN35_ADMISSION_OK … embd=715182080 qkv=1149091840
   tail=10923843584`, and `QWEN-ADMIT reason=-21 stage=3` on a one-byte
   mutation), and both oracles now write their workspaces to
   `tests/fixtures/`, which `tests/qwen35_runtime_model.c` translates and
   compares against the reference parser's struct: 34 of 34 fields, byte
   identical, with a named-mismatch control. What is still unexecuted is
   `aiueos_qwen35_model_bind`, which needs the real 10.9 GiB mapping.

2. **Two of the tensor object's 21 refusal codes have no case.** -22 ("the
   table did not end at 10,996,621") and -23 ("the extents do not fill the
   artifact exactly") both need a walk that completes with a different total,
   and every single-field mutation that changes a record's size also moves the
   next record's expected offset, so -16 fires first. Reaching them takes a
   rebuilt table. Both are checked in the admitted direction instead.

3. **`qualification/jvm-free-object-parity.edn` is still not regenerated.**
   These three are recorded in a scoped
   `qualification/jvm-free-object-parity-qwen35.edn`, the shape ADR-0132
   established and for the same reason: that file's header names ONE compiler
   tree, and these objects need kotoba-native rows that did not exist when the
   66 were measured. ADR-0132's nine-hour estimate for a whole-roster
   regeneration is unchanged.

4. **Nothing here says K16 loads the model through Kotoba.** The objects are
   now IN the model-handoff image -- that is what changed -- but no QEMU or K16
   run was performed, so nothing has executed them on a CPU. `build-uefi.sh`
   producing a `BOOTX64.EFI` is a link, not a boot.
