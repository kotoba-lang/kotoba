# ADR-0219 — flat records answer the pointer rule; three more layer-0 files lose their judgment

- Status: accepted
- Date: 2026-09-16
- Executes step 3 of ADR-0212's order (the pointer question) and the first
  four of its "rest of layer 0". Follows ADR-0215 (relay_protocol.c retired)
  and ADR-0218 (install-intent admission as a native object). Authority for
  the direction: ADR-0013 (C-free hard flip), root ADR-2607241100 (C is
  mechanism, Kotoba judges). Owner direction 2026-09-16: "C free を全体的に".

## The decision: a struct crosses as one flat record

ADR-0212 measured the rule that blocked 840 of layer 0's 1,083 pure-logic
lines: a pointer loaded from memory cannot be a region root
(`:kotoba.error/kernel-region-provenance`), so no Kotoba object can take a
`struct *` and validate what its fields point at. It named two honest exits
and took neither. This record takes the first — **re-express the public
surface so the data arrives as parameters** — in the one shape that fits the
five-argument ABI whatever the struct's width:

> The C packs the struct, every pointer field it holds, and every expected
> value the decision compares against into ONE contiguous fixed-layout
> record. The object takes `(record length)` (or `(record length out)` when
> it answers with more than a verdict), reads by offset, and the record
> layout — written as the header comment of the `.kotoba` — IS the
> marshalling contract. The C side that fills it holds no comparison.

`native/job_protocol.kotoba` (ADR-0212) already used this shape for its
48-byte input record; this ADR makes it the rule and applies it to files
that were blocked. What it costs and what it does not:

- **No language change.** `kernel-load-ptr` stays unused; provenance stays
  where the language put it. A record is a parameter-rooted region.
- **The C grows.** Packing is new code where the C only ever read a struct
  (ADR-0212 predicted this for `inference_status.c` and it held). Measured
  on the three files: 201 lines of C before, 224 after — and zero of the
  224 compare anything. **Kernel C line count is not the progress metric;
  judgment lines remaining in C are.**
- **Out-parameters become out-records.** A C function that filled a struct
  through a pointer (`aiueos_model_mapping_plan`, `aiueos_device_worker_poll_response`)
  now has the object write a fixed record into a caller-owned region the C
  unpacks. The verdict is the return; the record is the answer.
- **64-bit fields are compared exactly where the oracle can.** The KIR
  oracle host carries words as doubles, so a u64 magic compared as one
  literal could not tell `0x414955454f53424f` from the same with bit 0
  flipped — measured: the `:magic-flipped` vector PASSED a u64 compare. Two
  u32 halves are exact on every host and that is how the magic is compared.
  The same limit is why two rate vectors above 2^53 are stated in their
  contract as magnitude-only in the oracle and exact only in the native run.

## What moved, file by file

| C file (layer 0) | judgment retired | Kotoba object(s) | record | vectors |
|---|---|---|---|---|
| `inference_status.c` | status admission (17 fields, 3 `const char *`) | `inference-status-valid` | 200 B | 36 |
| `inference_status.c` | milli-tokens-per-second (unsigned 64-bit divide) | `inference-milli-tokens-per-second` | — | 14 |
| `model_handoff.c` | huge-page mapping plan (out-struct) | `aiueos/model_mapping_plan` (shared module) | out 32 B | 18 + 18 memory |
| `model_handoff.c` | handoff admission (boot-info + identity + GGUF header) | `model-handoff-validate` (requires the plan module) | 192 B | 22 |
| `device_worker_protocol.c` | murakumo poll-response parse (out-struct) | `device-worker-poll-response` | out 32 B | 26 + 17 memory |

Every vector's verdict — and every out-record byte — was produced by the
RETIRED C, built standalone with `cc -O2` at aiueos 352c385 (the last commit
carrying the decisions), through the same packer the kernel now uses, so a
layout drift between the C packer and the object turns the contract red.
Contract format `:aiueos.flat-record/v1` maps to the existing
region-and-seed builder in `verify-admissions.cljk`; the five contracts are
on the oracle's default list and in task `:cfree-wave-1-contracts`.

Three things the C did that a careful reader would not have guessed, kept
because the C's verdict is the contract:

- `find_text` in the poll parser searched from byte 0 every time (`at` was an
  output, not a cursor), so `"operation"` before `"accepted"` and `"bos"`
  before `"job-id"` are ADMITTED. Both are vectors.
- On a refusal after the three admission checks the C left partial state in
  the caller's struct (a ready flag, a parsed id). No caller reads it —
  `pci.c` returns before touching the struct — so those vectors assert the
  verdict only, and the contract says why.
- `duration(v)` was `v == UINT64_MAX || v > 0` on an unsigned; on a signed
  word that is `(not (= v 0))`, which is the same predicate.

## What was measured before landing

- **Native semantics, not only the oracle.** The rate object's restoring
  division was compiled to `aarch64-macos` and run through amu's kexe loader
  against Python's exact answer for nine cases including `10000000 × 10^12 /
  1` (= 10^19, above INT64_MAX: correct as a bit pattern) and the UNMEASURED
  sentinel; all nine agree. The textbook "remainder overflowed" branch of the
  divider was found unreachable for a 64-bit dividend (no vector could turn it
  red) and removed rather than carried.
- **Every contract turned red for the named vector when its object was
  broken**: text bound 32→33 turns exactly `:model-33`; decode bound off by
  one turns exactly `:decode-over-generated`; signed instead of unsigned
  compare in the divider turns exactly `:elapsed-two-to-63`; a wrong magic
  literal refused `:exact-admitted` (found that way, fixed that way).
- **Objects reproduce.** `reproduce-kotoba-objects.cljk --attest` then a
  second run: 5 MATCH at amu 9bccc552 (branch `agent/kotoba-native-a6a4616`,
  the kotoba-native a6a4616 pin — reachable from amu main once #1003
  merges). Task `:cfree-wave-1-native` recompiles all five by their recorded
  recipe, byte-compares, and verifies the ABI; a flipped byte in a committed
  object turns it red (measured).
- **Linked and booted.** `smoke-qemu-uefi.sh`: `AIUEOS_UEFI_SMOKE_OK`, 76
  distinct `_OK` markers (the same count as ADR-0215), `kernel.map` carries
  `kotoba_aiueos_inference_status_valid` (3,745 bytes) and
  `kotoba_aiueos_inference_milli_tokens_per_second` (965) beside a 42-byte C
  `aiueos_inference_status_valid` and a 12-byte rate shim.
  `smoke-qemu-model-handoff.sh`: `AIUEOS_QWEN38_MODEL_HANDOFF_QEMU_OK` with
  the admission and the paging plan decided by the two objects; with the
  shim's verdict read misread (`== 2`), the same boot prints
  `AIUEOS_MODEL_HANDOFF_FAIL` and the smoke exits 1 — the boot goes through
  the object. The physical node profile (device result + direct HTTPS +
  handoff) links all five (`kernel.map`), and the poll parse is reached only
  after a real HTTPS exchange with api.murakumo.cloud, so its execution
  evidence is the oracle and the K16's next run.
- **The host harnesses of the retired C are retired with it.**
  `tests/model_handoff_model.c` + `smoke-model-handoff.sh` and
  `scripts/device_worker_protocol_model.c` + `smoke-device-worker-protocol.sh`
  are gone; every verdict they asserted is a contract vector.
  `tests/inference_status_screen_model.c` tests the RENDERER and keeps
  building on the host with two named stand-ins for the objects (a macOS
  arm64 host cannot link an x86-64 kernel object); the four decisions it
  used to assert are vectors, and its `_OK` line now says
  `decision=kotoba-object-not-linked-here`.

## Upstream

- kotoba-lang/kotoba-native #180 (a6a4616): the five `kernel-object-entries`
  rows in both elf64 twins, with the packaging asserted in both test files.
  Portable suite 74 tests / 330 passed / 35 errors — the identical 35
  string-search lowering errors unmodified main shows on the same sibling
  checkouts, none in elf64.
- kotoba-lang/amu #1003: kotoba-native pin dc853ff → a6a4616 (forward only,
  ahead 2 behind 0), `deps-lock.edn` regenerated. Measured: with the new
  pin the objects package under their symbols; with the old pin they are
  refused with "no admitted symbol".

## Where the C-free count stands

- Files whose judgment has left C: `relay_protocol.c` (deleted, ADR-0215),
  `tls_aes_gcm.c` (ADR-0132; 45 lines of marshalling remain), and now
  `inference_status.c`, `model_handoff.c`, `device_worker_protocol.c`
  (marshalling only). `os/aiueos/kernel`: 30 C files, 21,434 lines of C,
  assembly and headers (was 21,391 — the packers). Objects linked by
  `build-uefi.sh`: 103. C files that call into Kotoba: 21 of 30.
- ADR-0212's order, updated: step 1 done (0215); step 2 (`tls_aes_gcm.c`)
  is a 45-line shim whose selftest can move as a module requiring
  `aiueos.aes128-gcm` — deferred, not blocked; step 3 decided here; of the
  layer-0 pure-logic files `job_protocol.c` (181, its Kotoba exists unwired
  in `native/`), `micro_infer.c` (69, blocked only on moving the transition
  matrix's source of truth out of the C — the table generator, the relay
  model and `k16-pxe-server.py` all read the C), `qualification.c` (84%
  EFI-call marshalling; its 19 judgment lines are next) and `acpi.c` (table
  walking through pointers — under this ADR each table crosses as a record
  the C copies, which is the same one-record shape) remain.

## What this does not do

- No hardware: I6/I7 unchanged, QEMU evidence only. The poll parse has not
  executed as machine code anywhere; its oracle verdicts and the linked
  symbol are what is claimed.
- The three C files still exist. They are marshalling; deleting them means
  moving the packers to the call sites, which `pci.c` / `main.c` /
  `framebuffer.c` / `paging.c` would then each carry. Left where a reader
  finds one copy.
- The KIR oracle's double-precision ceiling is recorded, not fixed.
