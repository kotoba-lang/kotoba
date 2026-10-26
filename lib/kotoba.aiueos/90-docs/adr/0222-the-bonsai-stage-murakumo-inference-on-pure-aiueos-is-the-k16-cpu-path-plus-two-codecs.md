# ADR-0222 — the Bonsai stage: Murakumo inference on pure AIUEOS is the K16 CPU path plus two codecs, not the B70 GPU path moved over

- Status: accepted (stage A is landing item by item — the PTQ1_0 dequant,
  the Hadamard object, the two-profile admission objects, the graph
  contract and the C translation are in the tree and graded; stage B item 6's
  first step — norm + activation live on the objects — is in the tree and
  parity-checked on a CPU, but no forward pass has run through it on any
  machine, and the Bonsai profile has not generated a token)
- Date: 2026-09-22
- Owner question: 「実際に amu native compiler, binary のみで書かれた aiueos の上で
  murakumo inference が動くようにするには? inference は ternary bonsai 2 27b ptq1
  を murakumo by amu native binary で」
- Extends ADR-0220 (the whole-kernel programme; its "Inference" paragraph is
  the cutover this ADR adds a model to) and ADR-0221 (dequant + live matvec).
  Relates to ADR-0117/0119 (model transport), ADR-0120/0145 (graph
  admission), ADR-0121 (first token), ADR-0196 (`evaluate_token` budget),
  ADR-0205 (the missing tender), ADR-0207 (cluster admission), ADR-0211
  (calibrated counting), ADR-0212 (conversion order).
- Upstream evidence read, not re-measured: kotoba-lang/inference
  `verify/native/gpu/README.md` iteration 66 and
  `verify/evidence/ternary-bonsai-ptq1-native-e2e-20260920.json` (origin/main
  2026-09-22; the local checkout was 82 commits behind and was not used).

## Two streams that have not met

**Measured on the B70 2026-09-22, and it changes what stream A's row means:**
the unit `murakumo-b70-bonsai-native.service` is active but its ExecStart is
the Prism **llama-server** on :8093; :8092 is `murakumo-mishima-fleet-router`,
whose heads include that llama-server; no `kexe-loader` / `serve_http` /
`resident-replay` process runs and no unit under `/etc/systemd/system`
mentions either. So the native guest is **not serving today** — traffic for
`prism-ml/Ternary-Bonsai-2-27B-PTQ1_0` is answered by llama.cpp. That does
not touch the 2026-09-20 measurements (they were taken with the guest
running, and the artifact digest is now confirmed identical); it means the
row "stream A serves Bonsai natively" is a past measurement, not a running
system — and stage D's point, that nothing here holds a service across a
restart, is the same point one box over. Recorded in
kotoba-lang/inference `verify/evidence/ternary-bonsai-ptq1-native-e2e-20260920.json`.

Also 2026-09-22: the wire-42 GPU path gained a **fourth backend** — Apple
GPUs through MoltenVK (amu PR #1046: a portability driver is invisible to the
Vulkan loader unless the instance asks for `VK_KHR_portability_enumeration`,
so every Mac had answered `VK_ERROR_INCOMPATIBLE_DRIVER`). An M1 Max runs the
same guests at 146–163 GB/s (B70 160, Xavier 54, K16 44), `dot.kotoba` matching
an f64 twin to 3.1e-4. It does not move this ADR's plan: the AIUEOS path is
still CPU (stage A of this document), and no weights were mapped on that
backend.

Everything below is measured state as of 2026-09-22, read from the ADRs and
evidence files named. Nothing was booted for this ADR.

| | stream A — kotoba-lang/inference on B70 / Xavier | stream B — this repository on the K16 |
|---|---|---|
| model | Ternary Bonsai 2 27B `PTQ1_0`, sha256 `53107f53…`, GGUF architecture `qwen35`, 48 recurrent + 16 full-attention layers, base model Qwen3.8-27B | Qwen3.8 27B, 10,934,860,704 bytes, GGUF architecture `qwen35`, the SAME 48 + 16 layer graph (ADR-0120) |
| correctness | greedy `Hello` → `11, 353, 2688, 264, 5286, 303, 279, 3694`, 8/8 = Prism llama.cpp `prism-b10709-9a9394a`; tokenizer 18/18; template 3/3 | first token BOS `248044` → `2005`, runner-up `17`, = llama.cpp Metal, **on the physical K16** (ADR-0121); decode stopped at `T02 L04 SOFTMAX` (KV alias), decode tok/s `N/A` |
| where the arithmetic runs | GPU: Vulkan through amu's wire 42 — `tools/kexe_gpu_vulkan.c` (C, supervisor side) on Mesa ANV / RADV / nvgpu (C) | CPU: all fifteen tensor types dequantise in Kotoba and the live matvec is the Kotoba object (ADR-0221); `qwen35_infer.c` (1,844 lines: orchestration, AVX2 arm, SMP split, KV/recurrent state) is C |
| what is under it | Linux, systemd (`murakumo-b70-bonsai-native.service` :8092), Node/kbb for `serve_http.cljk` and for generating the guest | pure AIUEOS boot, RTL8125 direct TLS to Murakumo (ADR-0127), job protocol / device-worker signing / relay as Kotoba objects (ADR-0215/0219/0220) |
| serving | 125.2 ms/step GPU, 7.96 tok/s aggregate at 1–8 concurrent requests (`batch-rows = 0`); the public gateway did not route to it | one job per boot; the K16 is in `/infer/nodes` as `aiueos-micro-infer` (bigram), `admission "pending"` (ADR-0207); no tender on hardware, so fuel, code and state are all refreshed by reboot (ADR-0205) |
| the only measured CPU number | — | time to first token 46,666,864,001 ns, C scalar/AVX2, one token (ADR-0127) |

Stream A satisfies the owner's condition — "compiled by amu, native binary" —
only for the guest `.kotoba`. The loader, the GPU driver and the HTTP shell
are C and JavaScript on Linux. Moving stream A onto AIUEOS would mean a Vulkan
driver in Kotoba; AIUEOS has virtio-gpu 2D (ADR-0084/0094) and nothing else,
ANV/RADV are C in the 10⁵-line class, and a Venus/virtio-gpu passthrough puts
Linux back under the kernel. **A GPU on AIUEOS is not a stage of this plan.
Bonsai on AIUEOS is the CPU path.** That is the first decision, and it fixes
the class of the number to expect: the K16 has produced one Qwen token in
46.7 s in C; the Kotoba objects are scalar four-accumulator loops that
ADR-0220 already says will be slower than the AVX2 they replace. The number
is to be measured and printed, not predicted here.

## Why the K16 path is the road

Bonsai's GGUF declares `qwen35` and its layer split is Qwen3.8's. The three
admission objects (`qwen35-gguf-header-valid`, `-kv-scan`,
`-tensor-table-bind`, ADR-0145), the thirteen forward-pass objects
(ADR-0147/0148/0221), the tokenizer objects (ADR-0139) and the transport
(ADR-0117/0119) were all built against exactly this graph. What Bonsai adds
is **two tensor codecs and one basis change** — nothing structural.

## Who does this, and how the next floor is chosen (2026-09-23)

This programme is driven by a **local Claude loop**, not by whoever happens to
read this document:

- `scripts/bonsai-stage-tick.cljk` (superproject) measures the remaining
  floors against `origin/main` -- never the working tree -- and answers
  `:candidate` / `:no-candidates` / `:insufficient-scan` as three different
  things. `:needs-a-human` floors (the physical K16, the fleet, the tender)
  are never handed to an unattended run.
- `scripts/bonsai-stage-loop.cljk` wakes `claude -p "/bonsai-stage"` only when
  an unattended floor exists, holds a lock so two iterations cannot take one
  floor, and records the outcome by comparing this repository's `origin/main`
  sha before and after: a turn that ends without moving it is
  `:ran-without-landing`, not `:ran`.
- `.claude/skills/bonsai-stage/SKILL.md` is the runbook one iteration follows.
- `cloud.itonami.bot.bonsai-stage` (LaunchAgent, 6 h) runs it unattended; the
  ledger is `~/.itonami/bonsai-stage.ledger.edn`.

Measured over the first nine iterations (2026-09-22/23): $1.17-$16.47 and
2-49 minutes each, and the three defects the loop found in ITSELF are worth
more than the average -- a `-p` turn that backgrounds work and ends is not a
floor closed; a check keyed on a literal breaks the moment the floor removes
that literal; a detector that cannot tell a parity self-test from the live
call reports cutovers that never happened. Each is recorded in the loop's own
source rather than here.

## The stages, in the order ADR-0212 imposes

### Stage A — Bonsai enters the model plane (new work is codec only)

1. **`PTQ1_0` (GGML type 143), `PQ2_0` (142) and BF16 in
   `aiueos.lib.qwen35-dequant-core`.** The arithmetic's source of truth is
   Prism llama.cpp; stream A already holds it as `kdot_ptq1_dual_r1.comp` and
   `embed_iq4xs.comp -DPTQ1`, and its f64 oracle `dense_ref.py`. The block
   layout is `qs[24], qh[2], d` for PTQ1_0 and deliberately does NOT share
   PQ2_0's `d, qs[32]` offsets (stream A, 2026-09-20). Block size pinned
   2026-09-22 by tiling: **28 bytes per 128 elements** is the only size under
   which the 851 extents end at the file's last byte
   (`contracts/bonsai2-qwen35-runtime-v1.edn`, `bonsai2-qwen35-contract-test`).
   Contract vectors are
   cut from the real artifact and graded by Prism llama.cpp, the way
   ADR-0221's were cut and graded by the C — one row per type, one and two
   blocks, and a deliberately broken decoder shown red on the named vector.
   **Landed 2026-09-22 (PTQ1_0 and BF16; PQ2_0 is not in the file).**
   `aiueos.lib.qwen35-dequant-core` decodes type 143 (`ptq10-value`, a port
   of `dequantize_row_ptq1_0` from PrismML-Eng/llama.cpp
   `9a9394a895b96003ca842a6041cb28ac49a108f7`) and type 30 (`bits << 16`);
   `qwen35-dequant-row` and `qwen35-matvec` gain both through the shared
   core. Ten new contract vectors (48 total; 5 PTQ1_0 rows of which 3 are
   real blocks from `blk.0.attn_gate.weight` and `output.weight`, 2 BF16 rows
   of which 1 is `blk.0.ssm_alpha.weight`, 3 refusals), expected bytes from a
   `cc -O2` harness holding the Prism C verbatim: the KIR oracle passes all
   48 with 37 memory assertions and every reason observed, and goes red on
   `:ptq1-0-128-real-blk0-attn-gate` with `3^1` changed to 4. Fuel: the
   256-element PTQ1_0 row passes at 4,096 and traps `:fuel-exhausted` at
   2,048 — 8–16 per element against the dequant tier's 256 and the matvec
   tier's 119, so no kotoba-native row moves. Both objects recompile with the
   pinned amu, byte-identical twice, ABI verifier green, no slot-144 host
   call; `qwen35-dequant-row.o` 39,896 → 42,512 and `qwen35-matvec.o`
   44,576 → 47,192 bytes — 5,232 bytes of the low-region headroom ADR-0221
   left. **Re-measured by a QEMU boot 2026-09-22 at `624a01d`**
   (`AIUEOS_QWEN35_KOTOBA_PARITY=1 smoke-qemu-uefi.sh`, exit 0,
   `IMAGE-FRESH artifacts=3`): the parity profile links the grown objects,
   `QWEN-PARITY dequant ok` / `dot ok` / `matvec ok` over the fifteen
   C-twin types, `AIUEOS_UEFI_SMOKE_OK`, 76 distinct `_OK` markers.
   `KERNEL.ELF` 635,528 bytes; its lowest PT_LOAD segments end at 0x186fd2 /
   0x195fac / 0x1cc758 / 0x1cd14c against the 0x1f4000 limit (159,412 bytes
   under it at the tightest), the 2.7 MB `.high_bss` above. That is the
   `--gc-sections` parity image, not the production profile's two-segment
   loader, so the production headroom is still ADR-0221's number minus
   5,232 until that profile boots. There is no C twin of PTQ1_0 or BF16, so
   the self-test cannot grade them; until a Bonsai boot the oracle vectors
   are their whole evidence.
2. **The signed Hadamard basis change as an object.** Normalized 1024-wide
   Sylvester blocks, explicit signs from GGUF metadata, inverse after the
   embedding, and the Qwen3.8 recurrent `ssm_out` reorder from tiled
   `[hd, nk, rep]` to grouped `[hd, rep, nk]` before the transform. It runs
   before every folded matvec, so it sits in the same arena plan as
   `qwen35-matvec` (ADR-0147's 96-byte plan, offsets 64-bit).
   **Landed 2026-09-22** as `qwen35-hadamard.kotoba` (own object, own
   64-byte plan: mode / width / input / signs / output / perm hd, nk, rep;
   `[arena arena-length plan plan-length]`). The oracle is Prism llama.cpp
   `9a9394a`'s own CPU path (`tests/prism_hadamard_oracle.c`: `build_lora_mm`
   permute → `ggml_mul` signs → `fwht`; `build_inp_embd` fwht → signs; the
   scalar butterfly loop of `ggml_compute_forward_fwht_impl`, whose SIMD pass
   is the same function bit for bit). 22 contract vectors — 8 transforms
   including the artifact's REAL 5120 and 6144 sign vectors and the ssm_out
   [128 16 3] permutation, 14 refusals, reasons −10..0 all observed — pass
   in the KIR oracle (`bonsai-hadamard-contract`, ~6 min); red with `u − v`
   written `v − u`. Fuel bisected on the real 6144 case: passes 524,288,
   traps 262,144 → 43–85 per element; kotoba-native #190 gives the object
   its row and a 33,554,432 tier (6.0× the 65,536-element ceiling), amu
   #1045 advances the pin (a9f8a3c → 207db01) — the previous pin refuses
   the object by name ("declares an aiueos export with no admitted symbol",
   measured). Native: 8,592 bytes, fuel word 33,554,432 in the object,
   deterministic, ABI verifier green, no slot-144 call
   (`bonsai-hadamard-native`). Found on the way: every element walk had to be
   chunked per 1024-block — a 2,048-deep recursion exhausted node's stack in
   the oracle where 1,024 did not; the machine code loops either way. Not
   booted; not linked into `KERNEL.ELF`; the K16 caller that packs its plan is
   stage B.
3. **The GGUF metadata scan has to READ an `INT32` array it currently
   skips.** `prism.hadamard.sign_values` is GGUF type 5 (`INT32`) and holds
   −1. `qwen35-gguf-kv-scan.kotoba` today classes int32 arrays as "skip"
   (its own table: `7 int32 array + skip`) and reads every scalar through
   `u32-at`. Stream A's first full Bonsai run produced non-finite activations
   for exactly this reason — type 5 read unsigned turned −1 into
   4294967296 — and that is the bug to refuse here before the first boot,
   not after: a contract vector whose sign array holds −1 and whose expected
   workspace word is the two's-complement pattern. Measured 2026-09-22: the
   array is 28,672 entries (= 5120 + 6144 + 17408, the three folded input
   widths), 114,688 bytes, values {−1, 1}. The kv-scan object bounds one
   `kernel-load-u32` region at 512 bytes and its workspace at 128, so the
   array cannot be COPIED at admission; the admission records its file offset
   and count, and the Hadamard object reads signs from the read-only model
   mapping at use. The object now reads them exactly so — `sign_values` is
   `+1` / `0xFFFFFFFF` as INT32 words at a plan offset, refused by reason
   −10 for any other word. **The kv-scan side landed 2026-09-22 (option (a),
   owner's choice): the admission objects carry two profiles and no new
   argument.** `qwen35-gguf-header-valid` names the profile from the
   artifact byte length (10,934,860,704 / 5,946,648,928) and requires the
   matching counts; `qwen35-gguf-kv-scan` names it from the header's counts
   (866 / 50 vs 851 / 49), records it as bit 31 of the required-key mask,
   and every constant follows — the 40 Bonsai keys (30 of Qwen3.8's, not
   `nextn_predict_layers`, plus the ten `prism.hadamard.*`), `general.name`
   "Hf", padding 248044, file type 143, block_count 64, metadata end
   11,070,652, a 144-byte workspace whose four new words are the sign
   array's file offset (13,360) and count (28,672), the file type and the
   high mask. A Prism key under profile 0, or `nextn` under profile 1, is
   refused as −13 rather than skipped. Evidence: the Bonsai profile's
   contracts run in the KIR oracle over the REAL header (first 11,120,992
   bytes of the public file, sha256-pinned, refetched by range, refused when
   absent): header-valid 11/11; kv-scan **15/15 with the 144-byte workspace
   equal to one computed independently in python from the same header**,
   both profile mix-ups (−7, −201), one refusal per Prism key (−232, −237,
   −238, −239, −240) and the two end-of-section scalars (−227, −230). ~32
   minutes for the 15 (four full walks of 495,907 strings at ~7 min each).
   The Qwen3.8 profile is byte-for-byte the old behaviour by construction
   (128-byte workspace, same codes); the QEMU admission smoke
   (`smoke-qemu-qwen35-admission.cljk`, 2026-09-22, this tree) booted the
   rebuilt objects on the CPU against the 10,996,640-byte Qwen3.8 fixture:
   `QWEN-ADMIT reason=0 stage=0 admitted=1`,
   `AIUEOS_QWEN35_ADMISSION_QEMU_OK objects=3 offsets=match-host-reference`.
   **The Bonsai profile has been on a CPU since 2026-09-23** (below, after
   the C translation). It is still not what the K16 image is built to hand
   off in production — only the fixture branch accepts it. **The fixture for that boot
   landed 2026-09-22** — `tests/make-bonsai-boot-fixture.cljk`, task
   `bonsai-boot-fixture`. It does not SYNTHESISE a header the way
   `tests/make_qwen35_header_fixture.py` does for Qwen3.8: the Bonsai prefix
   is real and obtainable (the 11,120,992 sha256-pinned bytes
   `bonsai-admission-fixture` range-fetches), and it is the same prefix the
   three objects were graded over, so a synthesised second header would put
   the boot on bytes nothing else has read (ADR-0165). What the generator
   adds is the second arm: an independent walk of those bytes that derives —
   from the file, against the graph contract — the metadata end 11,070,652
   after walking 496,309 length-prefixed strings; the 28,672 INT32 signs at
   file offset 13,360, read SIGNED and each one ±1, with the offset and count
   cross-checked against slots 128/132 of the 144-byte workspace the kv-scan
   OBJECT produced; the 851 records with role, dimensions and ggml type; the
   48/16 schedule derived from `full_attention_interval` rather than assumed;
   the histogram 402/353/96; and the extents tiling with no gap to exactly
   `11,120,992 + 5,935,527,936 = 5,946,648,928`. It writes the fixture and a
   receipt of every number the boot gate will assert, so the next gate types
   none of them. Ten controls, each refused by its OWN reason literal
   (`:not-gguf :gguf-version :tensor-count :metadata-count
   :sign-value-not-unit :sign-values-count :unknown-role :role-dimensions
   :role-type :extent-not-contiguous`); the prefix missing is exit 3, not a
   pass. ~0.5 s. Found while writing it: searching for a tensor record by its
   length-prefixed name from byte 0 finds the copy inside the metadata's
   `prism.hadamard.weight_names` array first, and the control that mutated it
   was ADMITTED — the records are located from `metadata-end` now. This is a
   fixture and a walk; the boot that uses it is recorded below. Found on the way:
   amu `b36eb717` no longer compiles the PREVIOUS kv-scan object either —
   its 113-deep `if` key table exhausts the desugar stack ("desugared
   nesting exhausted the host stack"), so `reproduce-kotoba-objects` against
   the current amu could not have reproduced the committed object; the key
   tables are now balanced comparison trees (depth ~8) generated from the
   canonical strings and re-evaluated against them. **`qwen35-tensor-table-bind` followed the same day**: its profile is
   `metadata-end`, which the caller already passes and the kv-scan object
   derived (10,945,379 / 11,070,652), echoed into workspace slot 28144 — so
   again no new argument and no new slot. The two artifacts share every role
   SHAPE (checked: all 23 Bonsai roles carry the dimensions Qwen3.8's do);
   what differs is the record count (851), the artifact length, the data
   offset (11,120,992), the type histogram (`F32` 353 / `BF16` 96 / `PTQ1_0`
   402, counted in slot 31 because 143 would run off a 32-entry table), the
   model-level types (`token_embd` and `output` are PTQ1_0 where Qwen3.8's
   are Q2_K and Q4_K) and the absent MTP layer 64. 12 vectors in the oracle
   over the same fixture, 98.5 s: the admitted case's **28,160-byte
   workspace equals one computed independently in python** (851 binding
   slots, the type counters, the 65 role masks, the cursor), the profile
   mix-up refuses on the table floor (−5: the window that fills a Bonsai
   table cannot hold a Qwen3.8 one), and one mutation per refusal class
   (−21 retype, −20 dimension, −18 name, −16 offset, −13 unknown type).
   Both of its walks had to be chunked for the interpreter, like the kv-scan
   string walk: 851 records and a 7,040-word clear are host-stack overflows
   on node, and the chunk boundary is derived from the index because the ABI
   admits five parameters. After all three objects changed, the Qwen3.8
   profile was booted again: `QWEN-ADMIT reason=0 stage=0 admitted=1`,
   `AIUEOS_QWEN35_ADMISSION_QEMU_OK objects=3 offsets=match-host-reference`.
   **The C translation followed the same day, and is graded.**
   `aiueos_qwen35_model_translate` takes both profiles. Which one it is comes
   from bit 31 of kv workspace slot 124 — the bit the kv-scan object sets —
   and the four things that differ are CHECKED against that profile rather
   than assumed: record count (−106), artifact length (−107), metadata end
   (−108). The trunk is derived as `block_count − nextn` and refused unless
   it is the 64 the struct can hold (−109); the linear/full schedule is
   derived from the metadata's `full_attention_interval` rather than from a
   4 written in the C (−110 for a zero interval) and cross-checked against
   the count the object made from the role masks (−111), because a schedule
   that disagrees reads the mixer union as the wrong arm and nothing else
   would say so. PTQ1_0 (ggml type 143) counts in counter slot 31 — the slot
   `type-slot` in the object uses — while the tensor keeps 143 as its own
   type, so a dequantiser sees the file's number and the histogram stays the
   one the object checked. `aiueos_qwen35_model_parse` asks the OBJECT which
   workspace length this artifact wants instead of reading the header itself:
   128 first, and −3 — with a length the object admits — can only mean the
   other profile, so it retries with 144.
   New gate `run-task.cljk bonsai-c-translation`
   (`scripts/smoke-bonsai-runtime-translation.cljk` +
   `tests/bonsai_runtime_translation.c`; host `cc`, no artifact and no QEMU,
   because the translation records the model pointer and never dereferences
   it). Its INPUT is the two admission contracts' `:expect-plan-hex` — the
   144-byte and 28,160-byte workspaces computed independently in python and
   pinned to what the objects really produce by `bonsai-admission-contracts` —
   and its EXPECTATION is `contracts/bonsai2-qwen35-runtime-v1.edn`; no
   number is typed in either gate file. Two walks in opposite directions:
   851 shapes against the graph contract, and all 851 workspace records
   against the field each role id names, with the id → name half DECODED from
   the object's own `role-length` / `role-word` tables. The second walk is
   there because shape is not identity: `ffn_gate` and `ffn_up` are both
   5120 × 17408 PTQ1_0, and swapping them in `qwen35_slot` leaves the shape
   walk green — measured — while the identity walk names
   `blk.0.ffn_gate.weight`. Ten controls, every one seen red: the corrupted
   record the shape walk must NAME, and nine refusals asserted by reason
   literal (−103, −105, −106 twice, −107 … −111).
   The Qwen3.8 profile is unchanged where it can be checked byte for byte:
   `smoke-qwen35-runtime.sh` still reports 34 of 34 struct fields identical to
   the C reference parser, and the QEMU admission smoke booted this kernel —
   `QWEN-ADMIT reason=0 stage=0 admitted=1`,
   `AIUEOS_QWEN35_ADMISSION_QEMU_OK objects=3 translation=in-image
   offsets=match-host-reference` (2026-09-22, this tree, with the
   two-call kv-scan probe and the 144-byte workspace in the image).
   **Still Qwen3.8-only, and failing closed: `aiueos_qwen35_model_bind`.** It
   compares the data offset with Qwen3.8's 10,996,640 and binds the four MTP
   tensors, so a Bonsai model translates and then refuses to bind rather than
   fabricating a pointer. That is the floor after this one, and grading it
   needs the mapped 5.9 GB artifact.
   **The Bonsai profile's admission has run on a CPU (2026-09-23).**
   `kernel/main.c`'s fixture branch now takes two prefixes — Qwen3.8's
   synthesised 10,996,640 bytes and Bonsai's real 11,120,992 — and hands the
   objects the contract length that prefix belongs to
   (`AIUEOS_BONSAI2_DATA_OFFSET` / `AIUEOS_BONSAI2_ARTIFACT_BYTES` in
   `qwen35_runtime.h`). The prefix length chooses the LENGTH handed in; it
   does not choose the profile. The objects work that out from the header
   counts, and header-valid refuses a length that is not theirs. The
   printed tail is the last block's post-attention norm, indexed by the
   `block_count` the kv-scan object read: blk.64 under Qwen3.8 and blk.63
   under Bonsai, which has no MTP head. The line also prints `artifact=`.
   `smoke-qemu-qwen35-admission.cljk` with `AIUEOS_QWEN35_ADMISSION_BONSAI=1`
   (task `bonsai-qemu-admission`) builds the fixture through
   `tests/make-bonsai-boot-fixture.cljk` and reads its expected line from
   that generator's receipt, so no Bonsai number is typed in the gate. To
   reproduce, run `run-task.cljk bonsai-admission-fixture` and then the task
   (build + tcg boot, a few minutes). The result:
   `QWEN-ADMIT reason=0 stage=0 admitted=1`,
   `AIUEOS_QWEN35_ADMISSION_OK tensors=851 linear=48 full=16
   data-offset=11120992 embd=278138880 qkv=563159040 tail=5935507456
   artifact=5946648928`, `AIUEOS_BONSAI_ADMISSION_QEMU_OK`. Adding
   `AIUEOS_QWEN35_ADMISSION_MUTATE=1` retypes `token_embd.weight` from 143
   to 30, searching from metadata-end, and the gate requires
   `reason=-21 stage=3`. The Qwen3.8 line is unchanged except for the added
   `artifact=10934860704`. NOT measured: bind (the prefix is not the artifact,
   so `accessible != artifact` and bind is not reached), any tensor byte, and
   any token. PTQ1_0 / BF16 have no C twin, so `QWEN-PARITY` cannot score
   them.
4. **A graph contract for the Bonsai artifact**,
   `contracts/bonsai2-qwen35-runtime-v1.edn`: exact byte length, sha256
   `53107f53…`, metadata count, the 64-layer schedule, the tensor table and
   the type distribution (PTQ1_0 / PQ2_0 / BF16 and whatever else the file
   holds — counted from the file, not copied from this ADR). The three
   admission objects take their constants from the contract, so the objects
   do not change; the contract does. **Landed 2026-09-22** from the public
   file's first 32 MiB: 49 metadata keys, 851 tensors in 23 roles
   (48 × 9 + 16 × 6 + 64 × 5 + 3), types `PTQ1_0` 402 / `F32` 353 / `BF16`
   96 — no `PQ2_0` in this file — data offset 11,120,992, no nextn key and no
   MTP tensors. `test/aiueos/bonsai2_qwen35_contract_test.cljk` (6 tests, 43
   assertions on the kbb engine; seen red on the tiling and sign identities
   with the numbers broken) holds the document to its own arithmetic.
5. **Transport is existing mechanism.** FAT32-safe split under `EFI/AIUEOS`
   and the contiguous 2-MiB-aligned LoaderData mapping (ADR-0117); NVMe A/B
   slots for updates (ADR-0119, K16 write still unverified). The Bonsai
   file is **5,946,648,928 bytes** (Hugging Face LFS size, 2026-09-22; the
   B70's copy was not read — the session had no production access — so the
   two copies have not been compared and the sha256 has not been recomputed
   here). **Measured 2026-09-22**: `sha256sum` of the B70's copy
   (`/root/kgpu/models/Ternary-Bonsai-2-27B-PTQ1_0.gguf` on aiueos-6600hs)
   is `53107f53…`, equal to the value stream A's evidence records and to the
   graph contract here, so the two copies are the same bytes and the digest
   is no longer taken on trust. Split shape: 4,000,000,000 + 1,946,648,928. It is 4,988,211,776
   bytes smaller than the Qwen3.8 file that did fit the 16 GiB K16 beside
   the kernel; whether it fits is still a boot, not this subtraction.

### Stage B — the forward-pass cutover completes, and a second token exists

6. **The remaining stages of ADR-0220's cutover, in its order:**
   norm + activation → attention → recurrent-step (gated delta net) → rope.

   **Norm + activation: LIVE on the objects.** In `kernel/qwen35_infer.c`
   the forward pass's `rms_norm` (4 call sites), `rms_norm_heads_weighted`
   (q/k norm) and `l2_norm_heads` call `aiueos-qwen35-norm` modes 0/2/1;
   the FFN SwiGLU, the conv SiLU, the β sigmoid, the output-gate SiLU and
   the decay `exp(a·softplus(α+dt))` call `aiueos-qwen35-activation` modes
   4/0/1/0/2+3, each once over the whole vector, and `linear_attention`'s
   kernel-4 depthwise conv with its three-entry history calls modes 5/6
   (conv section below). The C is kept as
   `*_c` under `AIUEOS_QWEN35_KOTOBA_PARITY == 2 || AIUEOS_QWEN35_C_REFERENCE_NORM`;
   the flag is set for the host smokes and parity profiles 1, 3 and 4 (which
   do not link the two objects). The gated RMS of the linear-attention
   output is mode 3 of the norm object followed by activation mode 4
   (gated output norm, below). Rope's `exp` left
   the forward pass with `rope_heads` (rope stage, live, see below).
   Reproduce: `AIUEOS_QWEN35_KOTOBA_PARITY=2 smoke-qemu-uefi.sh` →
   `QWEN-PARITY activation ok` / `norm ok` in `build/aiueos/evidence-all.log`
   (the smoke's exit does not grep them); the harness now calls the live
   wrappers (`activate`, `rms_norm`, `l2_norm_heads`,
   `rms_norm_heads_weighted`), so the argument order checked is the
   forward pass's. Seen red: input/output swapped in the live `rms_norm`
   → `QWEN-PARITY norm mismatch`, activation still `ok`, exit 1. Profile 1
   still `dequant/dot/matvec ok`; `bonsai-qemu-admission` (model-handoff
   image, now linking the two objects) → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`;
   `smoke-qwen35-decode-math.sh` → `AIUEOS_QWEN35_DECODE_MATH_OK`.
   **Not measured**: a forward pass through these calls (QEMU has no model
   path; the parity vectors are 128 wide, the live widths are 5,120 /
   10,240 / 17,408 — inside both objects' admitted ceilings and fuel tiers,
   but never executed at that width); `smoke-qwen35-first-token-model.sh`
   (needs the real GGUF, not run).

   **Attention: LIVE on the object.** `full_attention`'s query/gate
   de-interleave, the fused softmax over the causal prefix of the KV cache
   (score, `exp`, denominator, weighted sum, gate sigmoid) and the
   position-zero reduction call `aiueos-qwen35-attention` modes 0/1/2. The
   object takes one arena and a plan of offsets; the live regions are the
   workspace (`scratch_a` / `scratch_c` / `scratch_b`, `beta_values` as the
   object's 128-byte scratch) and the decode context's key/value rows, so
   `attention_call` makes the arena the smallest span covering every region
   the plan names and rebases each address against it. Still C in
   `full_attention`: the KV cache write, its FNV
   hash and `resolved_cached_key` (custody, not arithmetic — the object
   header says why). The C is kept as `attention_*_c` under
   `AIUEOS_QWEN35_KOTOBA_PARITY == 3 || AIUEOS_QWEN35_C_REFERENCE_ATTENTION`;
   the flag is set for the host smokes and parity profiles 1, 2 and 4 (which
   do not link the object). A refusal maps to `FULL QUERY` (−11), `SOFTMAX`
   (every other mode-1 refusal), `FULL KEY` (mode 0) or `FULL OUT` (mode 2).
   Reproduce: `AIUEOS_QWEN35_KOTOBA_PARITY=3 smoke-qemu-uefi.sh` →
   `QWEN-PARITY attention ok` in `build/aiueos/evidence-all.log` (appended
   across runs; truncate it first). The harness calls the live wrappers with
   addresses, so the plan layout and the rebase checked are the forward
   pass's. Seen red: key and value cache swapped in the live softmax plan →
   `QWEN-PARITY attention mismatch`, exit 1. Profiles 1/2/4 still
   `dequant/dot/matvec ok`, `activation/norm ok`, `recurrent ok`;
   `bonsai-qemu-admission` (model-handoff image, now linking the object) →
   `AIUEOS_BONSAI_ADMISSION_QEMU_OK`; `smoke-qwen35-decode-math.sh` →
   `AIUEOS_QWEN35_DECODE_MATH_OK`. The production node image links with it:
   `aiueos_low_end` 0x1ef000, 20,480 B under 0x1f4000 (`.text` 0xb4f82).
   **Not measured**: a forward pass through these calls (no model path in
   QEMU; the parity geometry is 8 heads / group 2 / position 5, the live one
   24 / 6 / 1..7), and a live arena span — in the model the workspace and
   the decode context are separate allocations, so the span the object is
   handed is their distance apart, which no run has exercised.

   **Recurrent-step: LIVE on the object.** `linear_attention`'s per-head
   gated DeltaNet step (decay, `remembered`, the correction, the rank-one
   update and the read-out, 48 heads × 48 layers) calls
   `aiueos-qwen35-recurrent-step`. The wrapper `recurrent_step` builds the
   96-byte plan (dimension 128, six region words, decay and β as binary32
   bit patterns) and, as for attention, makes the arena the smallest span
   covering the head state in `decode->recurrent` and the five workspace
   vectors, rebasing each address against it. Still C in
   `linear_attention`: the q/k L2 norm call sites, the decay
   transition's `+ dt` and `a *` products, the two scalar products and the
   `v ·` loop of the position-zero reduction (its dot is the dot object, see
   item 7).
   The C is kept as `recurrent_step_c` under
   `AIUEOS_QWEN35_KOTOBA_PARITY == 4 || AIUEOS_QWEN35_C_REFERENCE_RECURRENT`;
   the flag is set for the host smokes and parity profiles 1, 2 and 3 (which
   do not link the object). Any non-zero answer maps to `LINEAR RECURRENT`
   (the caller has already refused a non-finite decay/β as `LINEAR DECAY`,
   so the object's −6 is unreachable). Reproduce:
   `AIUEOS_QWEN35_KOTOBA_PARITY=4 smoke-qemu-uefi.sh` → `QWEN-PARITY
   recurrent ok` in `build/aiueos/kernel-serial.log`. The harness calls the
   live wrapper with addresses, so the plan layout and the rebase checked
   are the forward pass's. Seen red: key and query swapped in the live plan
   → `QWEN-PARITY recurrent mismatch`, exit 1. Profiles 1/2/3 still
   `dequant/dot/matvec ok`, `activation/norm ok`, `attention ok`;
   `bonsai-qemu-admission` → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`;
   `smoke-qwen35-decode-math.sh` → `AIUEOS_QWEN35_DECODE_MATH_OK`. The
   production node image links with it: `aiueos_low_end` 0x1f1000, 12,288 B
   under 0x1f4000 (`.text` 0xb65a2). **Not measured**: a forward pass
   through the call; the live arena span (state and workspace are separate
   allocations — `decode->recurrent` is 150,994,944 B — so the span is their
   distance apart, which no run has handed the object); the per-token cost
   of 2,304 scalar calls where the C was an O3 loop.
   `smoke-qwen35-first-token-model.sh` needs the Qwen3.8 GGUF and was not run.

   **The production node image links again: `aiueos_low_end` is 0x1ec000,
   32 KiB under 0x1f4000.** Before, with `build-qwen38-murakumo-node-pxe.sh`'s
   flags (`AIUEOS_PHYSICAL_NETWORK_QUALIFICATION`, `…_DIRECT_HTTPS_…`,
   `AIUEOS_MURAKUMO_DEVICE_RESULT`, `AIUEOS_QWEN38_MODEL_HANDOFF`,
   `AIUEOS_PERSISTENT_BOOT`), `ld.lld` failed with `low kernel/user layout
   overlaps process-private aperture`: the low region ended at 0x1f8000 at
   231fe0b and at 0x1fa000 after this step (`.text` +9,776 B). `paging.c`'s
   `pci_pdpts` (16 KiB) and `pci_directories` (32 KiB) moved to `.high_bss`.
   Both are kernel-only page tables, reached through the kernel map that every
   process space copies, and zeroed explicitly in `aiueos_paging_initialize`.
   `.bss` went from 215,400 B to 158,056 B. `.high_bss` now ends at 0x486000,
   against its 0x600000 limit. Receipt:
   `os/aiueos/qualification/low-region-budget.edn`. To reproduce, run the
   build with `AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=1` if the tree is dirty
   and read the `aiueos_low_end`, `.bss` and `.high_bss` lines of
   `build/aiueos-qwen38-murakumo-node-pxe/core/kernel.map`. Seen red: on
   origin/main without the move, the same build fails with that `ld.lld`
   error, exit 1. Boots with the move: `smoke-qemu-uefi.sh` →
   `AIUEOS_UEFI_SMOKE_OK`. There, virtio modern and MSI-X are mapped through
   `aiueos_map_pci_mmio`, so the moved tables are walked. `bonsai-qemu-admission`
   → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`. **Not measured**: the production node
   image booting on the physical K16. With the attention, recurrent-step and
   rope objects linked `aiueos_low_end` was 0x1f2000 (`.text` 0xb7772); at
   origin/main 20c8b88 it is 0x1f3000 (`.text` 0xb8fb2), and with the conv
   modes (below) it is **0x1f4000 — the limit itself, 0 B of headroom**
   (`.text` 0xb9832), and with the position-zero dot it was still 0x1f4000
   (`.text` 0xb9ed2). The gated output norm (+792 B of object) put it at
   0x1f5000 and the link failed with the `ld.lld` error above. So
   `rtl8125.c`'s `rtl_parity_bar` (the NIC self-test's 4 KiB fake BAR,
   zeroed by `rtl_parity_seed` before every use and only read through its
   address) moved to `.high_bss`. Now `aiueos_low_end` is **0x1f3000, with
   4 KiB of headroom** (`.text` 0xba0a2, `.bss` 0x24728, `.high_bss` ends
   at 0x517000). The next move after that: the candidates left are the TLS
   scratch (tls13 8.8 KiB), the rest of the NIC scratch, main's 6.8 KiB, or
   a third loader segment. The 64 KiB boot stack cannot move, because it is in use
   before `.high_bss` is zeroed.
   **Rope: LIVE on the object.** `full_attention`'s rotation of the 24
   query heads and the 4 key heads calls `aiueos-qwen35-rope`
   (`kotoba/qwen35-rope.kotoba`, `[values values-bytes heads position]`, in
   place, reasons 0..−4, 6,152 B, fuel 16,777,216) through the wrapper
   `rope_heads`; a non-zero answer is `FULL KEY`, the stage whose checks
   precede it (none of the four refusals is reachable from those two call
   sites while decode stops at 7). Position 0 is computed rather than
   skipped: the identity for finite values. The C is kept as `rope_heads_c`
   under `AIUEOS_QWEN35_KOTOBA_PARITY == 5 || AIUEOS_QWEN35_C_REFERENCE_ROPE`;
   the flag is set for the host smokes and parity profiles 1–4 (which do
   not link the object). **This is the one stage whose parity is not
   against the C.** Profile 5 checks the object bit for bit against the
   Prism reference transcribed from `tests/prism_rope_oracle.c` — 24 and 4
   heads at every decode position 0..7, one head at 25,735 and at 15,975
   with pair 0 set to (0, 1), all 256 dimensions of every head — plus the
   refusals −4 (position 25,736) and −2 (0 heads), and it PRINTS the
   distance from `rope_heads_c` as a measurement, never a pass/fail.
   Reproduce: `AIUEOS_QWEN35_KOTOBA_PARITY=5 smoke-qemu-uefi.sh` →
   `QWEN-PARITY rope ok` and seven `QWEN-PARITY rope distance-from-c` lines
   in `build/aiueos/kernel-serial.log`. Measured under QEMU tcg, 24 query
   heads of synthetic inputs (magnitudes 2⁻⁷..2¹⁵, both signs), floats
   whose bits differ of 6,144 / largest distance in binary32 steps:
   position 1: 238 / 112, 2: 300 / 64, 3: 346 / 128, 4: 354 / 624,
   5: 374 / 1,536, 6: 392 / 1,792, 7: 292 / 1,536. The other 4,096 floats
   of each run (dimensions 64..255) are untouched by both. The large step
   counts are cancellations in `x0·cos − x1·sin` — a small result measured
   in its own ulps — not large absolute errors; the absolute error was not
   printed. Seen red: the live wrapper passing `position + 1` →
   `QWEN-PARITY rope mismatch`, `AIUEOS_EVIDENCE_STOP`, exit 1. Profile 1
   still `dequant/dot/matvec ok`; `bonsai-qemu-admission` (model-handoff
   image, now linking the object) → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`;
   `smoke-qwen35-decode-math.sh` → `AIUEOS_QWEN35_DECODE_MATH_OK` (C
   reference); kernel object digests `--check` OK, scanned 101.
   The object is not a port of that C. The C takes its sine from x87
   `fsincos`, which amu cannot emit, and its frequencies from `local_exp`, so
   the reference is Prism llama.cpp 9a9394a instead: `ggml_rope_cache_init` +
   `rotate_pairs` (theta starts at the position and is multiplied by
   `powf(1e7, −2/64)` = `0x3f1ab32b` after each pair, NEOX pairs `i` / `i+32`
   over the first 64 of 256 dimensions, binary32, unfused). For a text token
   the model's imrope sections `[11 11 10 0]` reduce to exactly this. One
   substitution: Prism calls `cosf` / `sinf`, the object evaluates the
   language's `f64-cos-bounded` / `f64-sin-bounded` on the widened angle and
   rounds to binary32. **The intrinsic is written out in binary64 in the
   object rather than called.** `x86_64-aiueos-kernel-v1` rejects it (amu
   8412d88, exit 70, "typed values currently require … qualified native …
   features"). It exists in osaho's KIR interpreter, restricted JS and Wasm,
   and has no kotoba-native lowering. The transcription keeps its constants,
   its two-part reduction and its Horner order.
   Positions above 25,735 are refused (−4). That is the intrinsic's
   `8192·π` domain, because pair 0's angle is the position itself. It is
   not a model limit: decode stops at 7 today and the context is 262,144,
   so a longer context needs a wider reduction.
   Reproduce: `cc -O2 -ffp-contract=off os/aiueos/tests/prism_rope_oracle.c
   -lm` prints the contract's rotations; `--measure` compares every angle of
   the admitted domain (823,552). The bounded answer differs from
   `(float)sin((double)θ)` at 5 angles and from `cos` at 7, and from macOS
   `sinf` / `cosf` at 149 / 328. `run-task bonsai-rope-contract` (KIR
   oracle, 15 vectors: 1 / 2 / 4 / 24 heads, positions 0 1 5 6 7 4096 15975
   25735, 7 refusals, 8 whole-head memory assertions, reasons −4..0 all
   observed) → green. Seen red: `x1·cos` written `x1·sin`, and the low part
   of π/2 dropped. With random inputs the second break stayed green at every
   position, so the 15,975 vector sets pair 0 to (0, 1), which puts −sin in
   dimension 0 unrounded. `AMU=../amu run-task bonsai-rope-native` →
   `AIUEOS_BONSAI_ROPE_NATIVE_OK fuel=16777216 bytes=6152`; seen red with
   amu's previous kotoba-native pin (exit 70, "no admitted symbol"). The
   kotoba-native row is #191 and amu #1047 advances the pin. Fuel was
   bisected in the oracle: 24 heads at position 6 pass at 81,920 and trap
   at 65,536; one head at position 25,735 passes at 8,192 and traps at
   6,144. The committed bytes are the `--jvm-free` recipe that
   `reproduce-kotoba-objects` records. amu's `--unpinned --source-path`
   route compiles the same source to different bytes (6,232), and which of
   the two is right has not been executed.
   **Not measured**: the distance from `rope_heads_c` on real hardware —
   QEMU tcg emulates `fsincos` through the host's binary64 `sin`/`cos`, so
   the numbers above are the object against QEMU's x87, not the K16's; the
   absolute size of the differences; their effect on a token (no forward
   pass has run through the call — QEMU has no model path); glibc's
   `cosf` / `sinf`, which Prism on Linux actually calls; whether Prism's
   build contracts the rotation into FMAs.
7. **`evaluate_token` becomes one object.** ADR-0196's estimate is
   5.62 × 10¹¹ fuel per token against the 2⁵³−1 ceiling — an estimate from
   shapes and a constant, not a measurement, and its three named errors all
   push the number up. Bisect the tier in the oracle on the real row range
   (ADR-0220's finding: four objects packaged at the 1,024 default `ud2`'d
   on the first real input) and give kotoba-native the row.
   **Not every stage this object would absorb is an object yet.** Rope is
   live (above), and so is the output projection (below). `qwen35_infer.c`
   still does one piece of the forward pass in C:
   - **the output projection — live on the matvec object.** The 248,320
     logits (the 1.271e9-MAC matrix ADR-0175 and ADR-0196 costed) used to
     be `tensor_row` (the dequant object) plus the C `dot`, which was AVX2
     when the CPU had it. They now go through `matvec`, so they use the
     Kotoba object plus the SMP split. The workspace has no room for 248,320
     floats. So `select_output_token` walks the tensor as views of at most
     FFN = 17,408 rows (15 views). A view is the same bytes with a smaller
     row count. Each view's logits land in `scratch_a`, which the trunk no
     longer uses. The argmax and runner-up are still C comparisons in token
     order. This part has no arithmetic.
     **The object is not bit-identical to the AVX2 path it replaced.** The
     object's dot is `dot_scalar`'s tree, `(s0+s1)+(s2+s3)`. `dot_avx2`
     keeps the scalar accumulators as lanes, but it reduces them left to
     right, and below eight elements it adds every product in sequence.
     Its comment said the order was preserved, and that was wrong.
     QWEN-PARITY profile 1 now prints the distance as a measurement, not
     as a pass/fail:
     `AIUEOS_QWEN35_KOTOBA_PARITY=1 node "$G" run build --
     os/aiueos/scripts/smoke-qemu-uefi.sh`, then
     `grep QWEN-PARITY build/aiueos/kernel-serial.log` →
     `dot-avx2 distance compared=30 differing=4 max-ulp=1`. That covers
     counts 0–17 and every multiple of 64 up to 768, under QEMU tcg
     `-cpu max`. `unavailable` means the CPU has no AVX2. It is not a zero
     distance. So on an AVX2 CPU a logit can move by 1 ULP, and a near-tie
     argmax can flip. The token is now the scalar tree's token, the same
     as the `AIUEOS_QWEN35_AVX2=0` build. Every other matvec already made
     this change with ADR-0221. The view walk is checked on the host:
     `sh os/aiueos/scripts/smoke-qwen35-decode-math.sh` → `output=views3`.
     That run uses a synthetic 34,819-row tensor across 3 views, with the
     winner planted in view 3 and the runner-up in view 1. The result is
     compared bit for bit against the old per-row loop. Offsetting a view
     by one row, or dropping the last view, turns it red on
     `token == want`.
     **Not measured:** the distance on the K16's own CPU, the effect on a
     real token (no model is on the build machine; `ADR-0121`'s
     `248044 → 2005` has not been re-run), and the rate.
   - **the rest of `linear_attention`,** which ADR-0175 already named: the
     kernel-4 depthwise convolution with its three-step history (**LIVE on
     the object**, see below), the gated RMS of the output (**LIVE on the
     objects**, see below), and the `dot` coefficient on the position-zero
     and cache-free paths (**LIVE on the object**, see below). No `dot(`,
     `local_sqrt(` or `history[` is left in the body of `linear_attention`.

     **Conv: LIVE on the object.** Modes 5 (`conv4-first`: position 0 or
     no cache, `a·k3`, the history not read) and 6 (`conv4-next`:
     `a·k3 + ((h0·k0 + h1·k1) + h2·k2)`, the C's association) of
     `aiueos-qwen35-activation`, with the history's address in the fifth
     ABI word. With a history, both modes shift it (h0←h1, h1←h2, h2←the
     input before the conv). Mode 6 with a null history is −5. The
     wrapper `conv4` picks the mode from `decode->position`. The C is kept
     as `conv4_c` next to the other `*_c` references. Contract
     `qwen35-activation-v1`: 18 vectors, 12 memory assertions, reasons
     −5..0 all observed. The expectations come from the C loop itself,
     compiled on the host (`tests/qwen35_conv4_oracle.c`,
     `cc -O0 -ffp-contract=off`). Two channels are probes: current 0
     against tap −1 with a zero history (mode 5 gives −0, mode 6 gives
     +0), and 2^24 against a history sum of −(2^24−2), which gives 2 only in
     the C's association. Seen red: `h0·k0 + (h1·k1 + h2·k2)` in the object
     → `memory mismatch` at `:conv4-next` region `:a` (channel 1's probe).
     Fuel, in the KIR oracle: the 24-channel mode-6 vector passes at 1,024
     and traps at 512 (the limit rounds up to a power of two). That is ≤ 43
     per channel, 2.8M at the 65,536 ceiling, under the existing 16,777,216
     tier, so kotoba-native is unchanged. Parity profile 2 now also drives
     `conv4` against `conv4_c` over 128 channels for five tokens (no cache,
     first cached, three later), comparing values and history after each
     token, plus the −2 (mode 7) and −5 refusals. Reproduce:
     `AIUEOS_QWEN35_KOTOBA_PARITY=2 smoke-qemu-uefi.sh` → `QWEN-PARITY
     activation ok` in `build/aiueos/kernel-serial.log`. Seen red:
     `conv4_c`'s association changed the same way → `QWEN-PARITY
     activation mismatch`, `AIUEOS_EVIDENCE_STOP`, exit 1.
     `bonsai-qemu-admission` → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`. The object
     is 9,976 B (was 7,736 B). **Not measured**: a forward pass through the
     conv at the live width of 10,240 channels (the oracle ran 24, the parity
     boot 128), and the object on the physical K16.

     **Position-zero dot: LIVE on the object.** Both places that form
     `β · dot(q, k) / √d` (the cache-free branch and the position-zero
     overwrite) call the wrapper `linear_zero_coefficient`, whose dot is
     `aiueos-qwen35-dot-f32` — already linked in the model image for the
     matvec, so no new object and no new `.text` in the low region. The two
     products and the `v ·` loop are still C. A refusal (an answer below
     INT32_MIN) is `LINEAR RECURRENT`. The C is kept as
     `linear_zero_coefficient_c` under `AIUEOS_QWEN35_KOTOBA_PARITY == 1 ||
     AIUEOS_QWEN35_C_REFERENCE_MATVEC` (host smokes, parity profiles 2–5).
     The reference is `dot_scalar`, not `dot`: the C it replaced was
     `dot_avx2` on an AVX2 CPU, up to 1 ULP from this tree (the dot-avx2
     distance above), so on an AVX2 CPU a position-zero coefficient can
     move by 1 ULP. That is the same change the output projection made.
     Parity profile 1's `dot` stage now also drives the live wrapper against
     the twin over nine 128-wide query/key windows with nine betas.
     Reproduce: `AIUEOS_QWEN35_KOTOBA_PARITY=1 node "$G" run build --
     os/aiueos/scripts/smoke-qemu-uefi.sh` → `QWEN-PARITY dot ok` in
     `build/aiueos/kernel-serial.log`. Seen red: the wrapper's count
     128 → 127 → `QWEN-PARITY dot mismatch`, `AIUEOS_EVIDENCE_STOP`,
     exit 1. `bonsai-qemu-admission` → `AIUEOS_BONSAI_ADMISSION_QEMU_OK`;
     `smoke-qwen35-decode-math.sh` → `AIUEOS_QWEN35_DECODE_MATH_OK`;
     `build-qwen38-murakumo-node-pxe.sh` links. Its `aiueos_low_end` is
     still 0x1f4000, with 0 B of headroom. `qwen35_infer.o` at the
     model-handoff flags (`zig cc -O3 -DAIUEOS_QWEN38_MODEL_HANDOFF=1`,
     `objdump -h`) goes from `.text` 0x344f to 0x321f, because `dot_avx2` is
     no longer reachable there. The link does not show those 560 B: they are
     smaller than the page `aiueos_low_end` rounds up to.
     **Not measured**: a forward pass through the wrapper (no model path in
     QEMU), and the 1-ULP effect on a real token.

     **Gated output norm: LIVE on the objects.** The per-head
     `v · (1/√(mean(v²)+ε)) · w · silu(g)` over the 48 × 128 output is
     `aiueos-qwen35-norm` mode 3 (`[3 values heads width weights]`, in
     place) and then `aiueos-qwen35-activation` mode 4 with the gate as `a`
     and the normed values as `b`, so the answer lands in the gate buffer
     (`scratch_b`). The wrapper `linear_output_norm` returns where it
     landed, and the output matvec reads from there. Mode 4 computes
     `silu(g) · x`, and the C computed `x · silu(g)`. Binary32
     multiplication commutes, so the two are the same bits, and there is
     no sixth ABI word for a gate address anyway. Mode 3 is mode 2 without
     the finiteness refusals and without the rescaled fallback, and its sum
     takes a non-finite square in instead of skipping it, as this C did.
     On finite inputs whose squares stay finite, modes 2 and 3 give the
     same bits. The C is kept as `linear_output_norm_c` with the other
     `*_c` references (it silu's the raw gate itself). Contract
     `qwen35-norm-v1`: 20 vectors, 9 memory assertions, reasons −5..0
     observed. The three mode-3 expectations come from the C loop compiled
     on the host (`tests/qwen35_linear_output_norm_oracle.c`, `cc -O0
     -ffp-contract=off`). One of them makes head 0's first square overflow
     (2^70): the C gives scale 0 and signed zeros, and a skipping sum gives
     a nonzero scale. Seen red: mode 3 summing with mode 2's skipping
     `sumsq` → `memory mismatch` at `:linear-output-norm-overflowing-square`
     region `:a`. Parity profile 2 now also drives `linear_output_norm`
     against `linear_output_norm_c` over 4 × 32 values with a gate, and the
     −2 probe moved from mode 3 to mode 4. Reproduce:
     `AIUEOS_QWEN35_KOTOBA_PARITY=2 smoke-qemu-uefi.sh` → `QWEN-PARITY norm
     ok` in `build/aiueos/kernel-serial.log`. Seen red: the wrapper's mode 4
     → mode 0 (the gate silu'd but never multiplied) → `QWEN-PARITY norm
     mismatch`, `AIUEOS_EVIDENCE_STOP`, exit 1. The object is 9,176 B (it
     was 8,384 B). It is compiled by amu 6c245f6, the revision the receipt
     already recorded. `smoke-qemu-uefi.sh` → `AIUEOS_UEFI_SMOKE_OK` and
     `NIC-PARITY ok`. `bonsai-qemu-admission` →
     `AIUEOS_BONSAI_ADMISSION_QEMU_OK`. `smoke-qwen35-decode-math.sh` →
     `AIUEOS_QWEN35_DECODE_MATH_OK`. Low region: see the next-move note in
     the low-region paragraph. **Not measured**: a forward pass through the
     wrapper at the live 48 × 128 (no model path in QEMU; the oracle ran
     2 × 8 and 4 × 32, the parity boot 4 × 32), the object on the physical
     K16, and the fuel at the live width. The export's tier is unchanged,
     and mode 3 does less work per element than mode 2, which the tier
     already covers.
   The loop's tick listed these as `:cutover-logits` (landed) and
   `:cutover-linear-attention-rest`, ahead of this floor, in the same way
   it put `:cutover-rope` first. It checks each one by reading the body of
   the C function at origin/main, with comments stripped, for `dot(`,
   `local_sqrt(` and `history[`. It is not checked by whether a file
   exists. Its controls go both ways: `matvec_range_c` must read as open
   and `ffn` as closed.
   Two constraints this object also meets, and which are not about fuel:
   a kernel object exports one symbol and cannot call another (ADR-0030),
   so every stage would be inlined through `aiueos.lib.*`. The low region
   has 4 KiB of headroom (low-region paragraph, above). The nine objects
   the forward pass calls today total 153,592 B (norm 9,664, activation
   11,120, attention 18,672, recurrent-step 7,000, rope 6,152, matvec
   47,192, dequant-row 42,512, hadamard 8,512, dot-f32 2,768; `git
   cat-file -s origin/main:os/aiueos/kotoba/qwen35-<name>.o`). That sum is
   an upper bound on one inlined object, not its size, since the objects
   share `aiueos.lib.*` code; an object that replaces them in the image
   frees their bytes. The SMP split (item 12) hands each half of a matvec
   to its own CPU from C, so one object would also have to either give
   that up or come after it.
   **This floor waits on the owner, not on the loop.** The SMP split is on
   in every image: `build-uefi.sh` defaults `AIUEOS_QWEN35_SMP` to 1, and
   `matvec` in `qwen35_infer.c` calls `aiueos_smp_dispatch(matvec_ap, …)`
   for any output of 512 rows or more when two worker threads exist. One
   object that calls nothing cannot dispatch, so it runs every matvec on
   one CPU. The choice is between two things. One is giving the split up,
   which is a rate regression the stage-C comparison would carry. The
   other is waiting for `smp.c` to move (ADR-0220 layers 3–5, item 12).
   That is a decision, and an unattended loop does not make it. The tick
   marks `:evaluate-token-object` `:needs-a-human`. It had offered the
   floor 12 times since 2026-09-23 with nothing landed. **Not measured**:
   the size of the inlined object, its fuel, and the single-CPU rate.
8. **The `T02` failure is retried on the physical K16**, with the KV alias
   fix of ADR-0121's follow-up in place, until eight greedy tokens exist.
   The floor is stream A's: `Hello` → `11, 353, 2688, 264, 5286, 303, 279,
   3694`. A different eighth token is a defect, not a rounding note, until
   the f64 oracle says which engine is right.
9. **tok/s is counted, not read from a clock that is not calibrated.**
   ADR-0211's icount, or the TSC under the `AIUEOS_QWEN38_MODEL_HANDOFF`
   profile — the only profile in which `tsc_hz` is non-zero (AGENTS.md,
   measured 2026-09-10). `N/A` until then, never zero.
10. **Tokenizer and template.** The `qwen35` tokenizer objects (ADR-0139)
    against Qwen3.5's tokenizer and chat template, including its default
    `xhigh` system instruction. Stream A's oracles exist: 18/18 corpus lines
    equal to llama-server `/tokenize`, 3/3 message shapes byte-equal to
    `/apply-template`. Those files, not new ones.

### Stage C — the throughput lever is the compiler, not the OS

11. **Vector ISA lowering in kotoba-native (AVX2 on x86-64, NEON on
    AArch64).** A ternary weight is a sign and a magnitude, so PTQ1
    matvecs are adds and subtracts over dequantised bytes — the shape SIMD
    pays for most. Without this stage "runs in Kotoba" is true and the rate
    is an order of magnitude under llama.cpp on the same CPU; with it the
    comparison is fair. This is a kotoba-native item, ordered after stage B
    so it optimises a measured path.

    **Where it stands.** The lowering exists: kotoba-native emits
    `kernel-dot-f32` (kotoba-gmir ADR 0010) as a `cpuid`/`xgetbv` guard
    over an eight-lane AVX2 arm and a scalar arm with the same
    accumulation tree, plus fused dequantise-and-dot primitives for Q8_0,
    Q4_K, Q6_K and the IQ family. kotoba-verifier admits all of them
    (its ADRs 0023 and 0043). The refusal `elf64.cljc` still describes
    ("runtime KIR operation rejected", 2026-09-02) is gone.

    **The live matvec now takes the AVX2 arm.** `qwen35-matvec.kotoba`
    calls `kernel-dot-f32` for its row dot whenever `cols` is a multiple
    of eight. Every Qwen3.5 and Bonsai dimension is. Other counts keep the
    scalar `dot-run`. Reproduce:
    `amu compile os/aiueos/kotoba/qwen35-matvec.kotoba --source-path
    os/aiueos/kotoba --unpinned --target x86_64-aiueos-kernel-v1`, then
    `objdump -d` shows `cpuid`, `xgetbv`, `vmulps %ymm…` and `vzeroupper`.
    Shortening the dot by eight elements turned the contract red with
    `memory mismatch` on `f32-4x16`. Under QEMU TCG `-cpu max` (`AIUEOS_QWEN35_KOTOBA_PARITY=1
    smoke-qemu-uefi.sh`), the serial log reads `QWEN-PARITY matvec ok`
    over all fifteen types. `smoke-qemu-uefi.sh` does not grep that line,
    so read `build/aiueos/kernel-serial.log`. Which arm the guard took on
    that CPU is not observed directly, because both arms answer the same
    bits.

    **PTQ1_0 rows never become f32 (2026-09-26).** For type 143 with
    `cols <= 16384` the live matvec calls `kernel-dequant-dot-ptq1-0`
    on the packed row and the input directly; every other type and width
    keeps dequant-then-`dot-row`. The fused op is the same weights the
    shared core writes, folded by `kernel-dot-f32`'s tree, so the answer
    is the materialising path's to the bit. The chain it took: grammar
    `b70bb39e` (kotoba-lang, kotoba-sema frontend arity 5 / bases [0 2]),
    kotoba-gmir ADR 0031 (28 bytes, 128 elements, limit 128 blocks),
    kotoba-mir, kotoba-codegen, kotoba-verifier, osaho ADR 0272 (the
    oracle), kotoba-native ADR 0088 (the x86-64 arms; AArch64 refuses
    with Q4_K's `:x86-simd-target-mismatch`), and amu's pins (amu #1179,
    merged as `faf7bc25`; the object's receipt records that revision).
    - Oracle: `cfree-wave-3-contracts` passes `qwen35-matvec-v1.edn` with
      31 vectors, 0 traps, 14 memory assertions, every reachable reason
      observed. The new vector `ptq1-0-3x384` (3 rows of 3 blocks,
      negative scales) takes its expected output from an independent
      binary32 reference of Prism's `dequantize_row_ptq1_0` loops plus
      `dot_scalar`'s tree. A left-to-right sum answers differently in all
      three rows. Making the fused call drop its row's last block turns
      exactly that vector red with `memory mismatch` on `:output`. The
      six IQ vectors pass too. They trapped `:rodata-address-unavailable`
      while a transitive `kotoba-kir` (1e00f830, whose `kotoba/kir.cljc`
      precedes osaho's `kir.cljk` in `kbb -Spath -M:verify-admissions`)
      shadowed osaho, so the task puts osaho's paths first and fails when
      none resolve. The runner now passes osaho's `:frames` budget at the
      ceiling (its default of 32 is sized for bin/amu's 4 MB stack; this
      runner has 64 MB and reports `:host/stack-exhausted` by name).
    - Both arms, executed: `run-task bonsai-ptq1-fused-arms` with
      `PTQ1_AVX2_HOST=gad` compiles `native/dequant-ptq1-arms.kotoba`
      (`--target x86_64-linux`) and runs it through amu's
      `tools/kexe_loader.c`: the scalar arm under Rosetta 2, which
      exposes no AVX, and the AVX2 arm on gad (AMD Ryzen AI MAX+ 395).
      Both answer `C88A9DFA`, which is kotoba.kir's answer. The three
      nearest wrong answers are `C88A9DFD` (upper half first),
      `C88A9DF9` (left to right) and `C88AA001` (qh at the wrong digit).
      Which machine ran which arm is tested, not assumed. Breaking the
      AVX2 arm's `>> 8` moves only gad's answer, and breaking the scalar
      arm's `sub rax,1` moves only Rosetta's. Without a host the task
      exits 2 (AVX2 not exercised).
    - Objects: `qwen35-matvec.o` is 58,416 bytes (48,000 before). The
      new amu compiles the unchanged `qwen35-dequant-row` and the
      previous matvec source byte-identically to their committed
      objects, so the diff comes from the source alone.
      `reproduce-kotoba-objects.cljk --amu <amu at faf7bc25> --objects
      qwen35-matvec.o` reproduces it (match). Under QEMU
      (`AIUEOS_QWEN35_KOTOBA_PARITY=1 smoke-qemu-uefi.sh`) this object
      boots and `kernel-serial.log` reads `QWEN-PARITY matvec ok`. That
      grades the fifteen C-twinned types through the new object, and not
      the fused PTQ1_0 path (see below).

    **Not done, and not measured:**
    - **A 17,408-column row cannot be computed by the live matvec,
      whatever its type.** `dot-row` hands `kernel-dot-f32` a
      69,632-byte region, and the family's 65,536-byte ceiling traps it
      (`:length-above-profile-maximum`, measured in the oracle
      2026-09-26; 16,384 answers). That is Bonsai's `ffn_down` (and
      Qwen's). Two calls would be a different accumulation tree. The
      fused PTQ1_0 path has the same 16,384 ceiling, and wider rows
      keep the materialising path that traps.
    - QEMU: the K-quant probe route (`--artifact image` for
      `x86_64-aiueos-kernel-v1`) left with amu's JVM route on
      2026-09-11, so there is no in-kernel boot of the fused PTQ1_0
      instruction. `QWEN-PARITY` cannot grade PTQ1_0 anyway (no C twin).
    - NEON: `a64-kernel-dot-f32` exists, and the K16 is x86-64.
      PTQ1_0 has no AArch64 arm.
    - The rate. No tok/s has been measured on any CPU for this object,
      fused or not.
12. **The SMP split stays C until `smp.c` moves** (ADR-0220 layer 3–5).
    Each half already calls the matvec object with its own row range and
    scratch (ADR-0221); the object does not change when the split does.

### Stage D — the layer that keeps it running

13. **kototama on hardware — the tender ADR-0205 names as absent.** Fuel
    refreshed per step, code arriving as a definition CID without a reset,
    state surviving a deploy. Until it exists "Bonsai generated eight tokens
    on the K16" is a job, not a service: the board reboots every ~20 s and
    every job is bound to a boot nonce. The timer that makes preemption
    possible is already Kotoba — `native/rt-kernel.kotoba` owns the APIC
    and a periodic release — and the K16 stream kernel does not use it.
14. **Murakumo membership.** The K16 sits at `admission "pending"` with
    every other field correct (ADR-0207); `can` gains the Bonsai
    capability name beside `aiueos-micro-infer`; the gateway routes model id
    `prism-ml/Ternary-Bonsai-2-27B-PTQ1_0` to the K16 head. The wiring
    already exists in the other direction — cloud-murakumo-api's
    `xavier_hosted_model.js` routes `nex-n2.5-mini-uncensored` to a native
    head as the fallback of a vLLM primary (stream A, tick 41) — and is the
    shape to copy. The model channel is Kotobase CID blocks + IPNS head
    (ADR-0118), whose physical writer is still red.

### Stage E — "AIUEOS written only in amu-native binaries" is the other wave

15. This is ADR-0220's programme and proceeds bottom-up regardless of
    Bonsai. Position: `os/aiueos/kernel` 21,294 lines of C and assembly,
    106 objects linked, 23 of 30 C files call into Kotoba, seven files
    retired. What blocks most of the rest is not inference: the pointer
    rule (ADR-0212), indirect `ms_abi` calls that stay mechanism until
    `BOOTX64.EFI` is Kotoba, `pci.c` (5,482 lines, layer 6) and `main.c`
    (3,699, layer 5).
16. **Order between the waves: Bonsai tokens first, C deletion after.** The
    in-kernel parity self-test grades every object against the C reference
    at boot (`QWEN-PARITY dequant ok / dot ok / matvec ok`, ADR-0221).
    Retiring `qwen35_infer.c` before a Bonsai token exists removes the
    instrument that would have graded the Bonsai objects. The C leaves
    "when the K16 has measured the object's token rate" (ADR-0221) — for
    Bonsai as for Qwen3.8.

## What is refused

- **Porting Vulkan.** GPUs stay with the Linux boxes (B70, Xavier); the two
  streams share Prism llama.cpp as oracle and share nothing else at run time.
- **Reusing kotoba-lang/inference's `.kotoba` in the kernel.**
  `kernel_math_core.kotoba` and its siblings are host-target (f64 rows
  handed in by a host); ADR-0220 already names the reuse target as the
  thirteen objects here. Stream A's GLSL and Kotoba here are two copies of
  the PTQ1 arithmetic; that is acceptable exactly as long as both are graded
  by the same Prism vectors.
- **Reading "links" or "passes its contract" as "ran".** Four objects landed
  green and would have jumped to address 0 on first execution (ADR-0220,
  AGENTS.md §5). Every stage above ends at a boot marker or a K16 receipt.
- **Predicting the token rate.** One measured CPU data point exists and it
  is 46.7 s to one token of a different quantisation in C. Bonsai's PTQ1 is
  fewer bytes per weight (memory-bound favours it) and adds a Hadamard per
  folded matvec (compute disfavours it); which wins is a measurement.

## Not measured, and named as such

Whether the artifact fits the 16 GiB K16 beside the kernel image (its byte
count is measured; the mapping is not); the CPU-bound rate of a PTQ1 matvec on the K16's Ryzen; the
K16's NVMe slot write; sampling-distribution parity (stream A lists it as
unmeasured too); contexts past 4,096 tokens; any board other than the K16
booting AIUEOS on real hardware (P5 remains UNVERIFIED, ADR-0084).

## Done means

1. `AIUEOS_BONSAI_GRAPH_READY` — the Bonsai contract admitted by the three
   objects on the K16, with the `INT32` sign array read as signed (marker
   naming follows `os-coverage.cljs`'s `/AIUEOS_[A-Z0-9_]+_OK/` for anything
   that should score).
2. Eight greedy tokens for `Hello` equal to Prism llama.cpp's, printed with
   the object's reason codes on the console and a decode count from ADR-0211.
3. A Murakumo job result signed by the device worker (ADR-0137) carrying
   those token ids, posted through the RTL8125 TLS path, and the K16's
   admission `accepted`.
4. Then, and only then, the token rate with the C reference deleted.
