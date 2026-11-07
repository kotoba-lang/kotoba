# Complete native bytes primitive source

Tracking: [AWAI-25](https://linear.app/kotobalabs/issue/AWAI-25),
[AWAI-66](https://linear.app/kotobalabs/issue/AWAI-66),
[AWAI-48](https://linear.app/kotobalabs/issue/AWAI-48),
[AWAI-43](https://linear.app/kotobalabs/issue/AWAI-43), Kotoba Labs.
These retain the UUIDs of former JUN-241/200/201/202; no old workspace is used.

The canonical vector arena component now supplies all four additional ABI
bytes primitives and the real planner/prelude/profile composition. Source
implementation now covers twenty slots. This is a source candidate, not
native admission or runtime qualification. No project implementation,
generator/assembler/compiler, artifact, syscall/runtime or test was executed;
no tests were added.

## Complete byte value operations

| Slot | Full operation |
| --- | --- |
| bytes-from-vector | Check size and every item in 0..255, always copy all words into fresh arena storage and publish a fresh handle |
| bytes-slice | Check 0 <= start <= end <= length, publish an immutable view, allocate no item words |
| bytes-concat | Check total size without wrapping, copy both full input spans into fresh storage, publish a fresh handle |
| string-from-utf8 | Check size, byte representation and canonical UTF8 before pool allocation; copy all bytes and publish a validated string pair |

bytes-empty/count/at use the existing vector slots. The existing machine-IR
mapping also uses bytes-from-vector for vector-i64-from-bytes: that full copy
prevents a later compiler-proved in-place vector update from mutating bytes.
All eight original vector operation bodies remain unchanged. This is neither
an ASCII subset nor UTF8 re-encoding of arbitrary binary contents: byte
construction, slicing and concatenation impose no text decoding condition.
Embedded zero and non-UTF8 byte sequences remain bytes. Only conversion to
string requires canonical UTF8, with no replacement character fallback.

The conversion checks every byte word before examining UTF8. Its walk retains
all seven refusal categories and their order: unexpected continuation,
overlong, invalid byte, truncated, bad continuation, surrogate and above-max.
Second-byte categories precede later-byte availability, so E0 80 is overlong
even without its third byte. String size is checked first. The result uses
the shared checked pair allocator and validated-string flag, preserving the
pool/cell budgets and existing string representation. Both ISA register-save
protocols preserve the additional s-register fragment state.

## Actual integration and failure paths

The owning closed native profile projects the existing 65536 byte and string
per-value bounds, separately from the per-run pool budget. Planning refuses
missing/malformed bounds or refusal-name data when byte slots are admitted.
Profiles without byte slots retain zero byte-helper state and no new value
paths. The profile's ordered eleven canonical names agree with C1 names
indices 1..11; source comparison reads the pure names, without a C loader or
header generator.

Startup installs byte/string limits at private offsets 1688/1696. Prelude
composes all four real routines, validated pool-pair construction, all eleven
named terminal value refusal paths/messages and actual slot bindings.
Image budget metadata includes both per-value limits. Table/item/pool/cell
exhaustion retain their existing distinct paths; malformed handles or byte
representations do not become an empty success. Unknown slots or artifact
capability kinds remain refused.

The numeric value labels are an internal mechanism protocol. Refusal text
comes from the admitted profile, not a second policy table in the emitter.
The string-construction branch validates before advancing the pool; the
shared validated-pair fragment requires that proof and is not general
permission to trust unvalidated bytes.

## Source evidence and remaining closure

Shared vector/bytes source: 45 functions; original public supported-slots and
routine signatures retained, with supported-byte-slots added. Blob
`2c6dac29574a4e18f6d693b59e5e98f9a028d788`, SHA-256
`d5e8b2114db5741f6266acc2a36ee96bf22a0617e2bcee2e6bbe8a5c65a7b304`.
Strings adds validated-pool-pair-fragment while retaining prior exports and
their signatures/bodies. Static graph: 17 modules including owning
ELF/artifact, 35 schemas, 576 import calls, 460 record uses and 614 type
positions, no structural findings. A lexical source walk found no local data
used as a function call. All 99 private state words are unique/aligned in the
reserved header. These are source observations, not generated code evidence.

Byte capability kinds/lowering/provider/result contracts are still absent;
no byte capability call is newly admitted. Genuine raw-file/hash/I/O,
shared inline bytes-at refusal naming and its owning lowering/ABI coverage,
complete callers/resolver/materializer/authoring, remaining runtime/ABI,
exact artifacts/native positive/refusal/resource evidence, reviewed owning
main/pins, Definition CIDs and full Amu-produced self-rebuild remain open.
The complete compiler and CDCI are unqualified. No workflow/protection,
live service or production route changed. The owner approved progress writes
to these same-UUID AWAI issues within Kotoba Labs after the identifier review.
