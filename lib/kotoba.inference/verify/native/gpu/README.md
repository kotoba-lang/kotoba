# GPU dispatch from a native Kotoba binary — `:gpu/compute` (wire 42)

Root ADR-2609182400 C. No JVM, no Deno, no Node at run time: the `.kotoba`
programs here are compiled by amu to a kexe, and the kexe asks the host GPU
for work through `typed-cap-call :gpu/compute :string :string`. The Vulkan
mechanism lives in amu's loader (`tools/kexe_gpu_vulkan.c`, supervisor side);
every decision — which kernel, which shape, how many dispatches per command
buffer — is in the `.kotoba` file.

| file | what |
|---|---|
| `probe.kotoba` | `INFO` → `<device>\|<api>\|<maxWgX>\|<unified>` |
| `dot_rows.comp` | the first kernel: `o[row] = Σ w[row,k]·x[k]`, one workgroup per row (GLSL; `glslangValidator -V dot_rows.comp -o dot_rows.spv` at build time — the SPIR-V is data, not a runtime dependency) |
| `dot.kotoba` | MAP a 4096×1024 f32 matrix and a vector by path, one DISPATCH, READ the 4096 outputs back as hex — checked against an f64 twin |
| `bench.kotoba` | one command buffer (`BEGIN … SUBMIT`) of 40 dispatches over a 64 MiB matrix: 2.68 GB of weight reads, ~1.4 Nex tokens |
| `policy.edn` | `{:allow #{[:cap/call 42]}}` |

```
amu compile verify/native/gpu/bench.kotoba --target x86_64-linux --jvm-free --policy verify/native/gpu/policy.edn --output bench.kexe
amu extract-native bench.kexe --symbol main --output bench.bin      # note :offset
cc -std=c11 -O2 -Wall -Wextra -Werror -DKEXE_GPU_VULKAN <amu>/tools/kexe_loader.c -o kexe-loader-gpu -lvulkan
KEXE_RESULT_TYPE=string KEXE_STRUCTURED_REPORT=1 KEXE_FUEL=100000 KEXE_WALL_SECONDS=300 ./kexe-loader-gpu bench.bin <offset> 0 x86_64 42
```

Measured 2026-09-18 (`bench.kotoba`, 3 runs each, submit→fence on the host clock):

| box | GPU / driver | kexe ISA | 40 × 64 MiB | GB/s |
|---|---|---|---|---|
| aiueos-6600hs-1 | Intel Arc Pro B70, ANV 1.4 | x86_64 | 16.8 ms | 160 |
| aiueos K16 | AMD Radeon 680M iGPU, RADV 1.4 | x86_64 | 61 ms | 44 |
| xavier | NVIDIA Tegra Xavier, nvgpu 1.3 | aarch64 | 49 ms (first run 160, cold) | 54 |

`dot.kotoba` returned the same bits on all three (max rel err 2.2e-4 against
the f64 twin; the f32 tree in the shader is the order). Single small dispatch
(16 MiB): B70 0.68 ms, K16 0.80 ms, Xavier 2.47 ms — launch-bound, which is
why the serving path records one command buffer per token (ADR-2609182100 D1).

**A fourth backend, 2026-09-22: Apple GPUs through MoltenVK** (amu PR #1046;
`verify/evidence/gpu-compute-moltenvk-m1max-20260922.json`). Until then
`vkCreateInstance` answered `VK_ERROR_INCOMPATIBLE_DRIVER` on every Mac — a
portability driver is hidden from the loader unless the instance asks for
`VK_KHR_portability_enumeration` by name — so the whole wire-42 path was
unreachable there, which reads as "no GPU here" rather than as a missing
line. The same guests, on an M1 Max (loader 1.4.357, MoltenVK 1.4.2):

| box | GPU / driver | kexe ISA | 40 × 64 MiB | GB/s |
|---|---|---|---|---|
| this Mac | Apple M1 Max, MoltenVK 1.4.2 | aarch64 | 16.5–18.4 ms (3 runs) | **146–163** |

`INFO` answers `Apple M1 Max|1.3.357|1024|1`; `dot.kotoba` (4096×1024) is
2.043 ms with max rel err 3.1e-4 against an f64 twin, the same class as the
other three. Two things the run found: the gate
(`amu scripts/test-gpu-compute.cljk`) built its child environment with
`(merge (js->clj (.-env js/process)) env)` and died on the kbb engine before
reaching a GPU on ANY host; and a guest whose answer is a 16 KiB buffer read
back as hex needs `KEXE_STRING_POOL` above the 65,536-byte default (the dot
guest traps at 32,939 bytes used). **No weights were mapped** — synthetic f32
only; the K-quant / PTQ1_0 / delta-net kernels are not compiled for this
backend, and nothing was served.

## The Nex K-quant kernels on the same path (2026-09-19)

### Prism Ternary Bonsai 2 codecs and activation basis (2026-09-20)

The canonical sources for `kdot_f32_r1.comp`, the positions kernel,
`kdot_ptq1_dual_r1.comp`, `embed_iq4xs.comp`, and `hadamard_signed.comp` are
shipped by the library from `resources/kotodama/inference/kernels/native/`.
The verification programs in this directory execute those exact resource
bytes. `kdot_f32_r1.comp` and the positions kernel decode Prism's group-128
`PQ2_0` (GGML type 142) and `PTQ1_0` (143), plus the BF16 projections used by
the Qwen3.8-27B gated delta net. Its GGUF architecture identifier is `qwen35`;
that implementation identifier does not make the checkpoint a Qwen3.5 model.
PTQ1_0's physical block order is `qs[24], qh[2], d`;
it intentionally does not share PQ2_0's `d, qs[32]` offsets.
`embed_iq4xs.comp -DPTQ1` supplies the corresponding token-row lookup.

Folded Bonsai weights require an activation basis change before every folded
matmul. `hadamard_signed.comp` implements the checkpoint contract: normalized
1024-wide Sylvester Hadamard blocks, explicit signs, inverse-after-embedding,
and the Qwen3.8 recurrent `ssm_out` reorder from tiled `[hd,nk,rep]` to grouped
`[hd,rep,nk]` before the transform. It handles independent rows, so the same
kernel is usable by the resident adaptive batch scheduler.

The gates execute the production GLSL after `naga` translation rather than a
test-only GPU implementation:

```
deno run --unstable-webgpu --allow-read --allow-write --allow-run \
  verify/ternary_kdot_parity.js 37 5120 /path/to/Ternary-Bonsai-2-27B-PTQ1_0.gguf
deno run --unstable-webgpu --allow-read --allow-write --allow-run \
  verify/hadamard_signed_parity.js
```

Measured on Apple M1 Max: synthetic PQ2_0/PTQ1_0 and BF16 dots agree with the
CPU codec to at most `1.526e-5`; 37 real rows of
`blk.0.attn_gate.weight` agree to `1.192e-7`; forward, inverse, and grouped-GDN
Hadamard cases at widths 5120, 6144, and 17408 agree to `2.384e-7` absolute.
This evidence covers tensor execution and the activation transform. It does
not claim a complete 64-layer token, HTTP throughput, or fleet concurrency;
those require wiring these operations into the Qwen3.8 dense-hybrid layer
recipe and measuring the resident guest on the target GPU.

`ternary_kdot_bench.js` measures the same production PTQ1_0 shaders with real
checkpoint tensors and independent activation rows. It rejects dispatches
larger than the WebGPU workgroup limit instead of reporting command-error
overhead as throughput. A row limit can be used for the 248,320-row LM head;
scaling that partial timing to the full vocabulary remains an estimate.

```
deno run --unstable-webgpu --allow-read --allow-write --allow-run \
  verify/ternary_kdot_bench.js /path/to/Ternary-Bonsai-2-27B-PTQ1_0.gguf \
  blk.0.ffn_gate.weight 1,4,8,16
```

The 2026-09-20 M1 Max measurements and their scope are recorded in
`verify/evidence/ternary-bonsai-2-27b-m1max-20260920.json`. The Murakumo values
there are real kernel timings accumulated over the model's tensor inventory,
not a completed token or HTTP measurement.

Co-scientist iteration 64 removed PTQ1's four variable-trip radix loops per
four weights. Because a shader invocation always asks for four consecutive
trits, it now loads their packed word once and applies one fixed `3^n` vector
operation. `blk.0.ffn_gate.weight` improved by **1.84–2.42x** across Metal,
Intel ANV, AMD RADV, and NVIDIA nvgpu while producing the same output bits as
the old shader on each backend. The three Vulkan measurements used the native
`.kotoba` → amu kexe → `:gpu/compute` path; Metal used the existing WebGPU
gate because the native loader has no Metal arm. Full measurements and scope:
`verify/evidence/ternary-bonsai-ptq1-radix-decode-20260920.json`.

Co-scientist iteration 65 fused the two dense SwiGLU projections. The
PTQ1-specific `kdot_ptq1_dual_r1.comp` reads the activation once, decodes gate
and up weights in one workgroup, reduces both dots together, and writes
`silu(gate) * up` directly. Against two iteration-64 single projections, the
conservative speedup (before counting the removed standalone SiLU dispatch) is
**1.71x B70, 1.21x K16, 1.54x Xavier, and 2.02x/2.18x M1 Max at B1/B8**.
Native output agrees with the CPU oracle to at most `2.690e-6` relative; Metal
agrees to `1.192e-7` absolute. The model-wide accumulated matmul upper bound
moves from 1.004 to 1.207 aggregate seq-tok/s at B1 and from 1.943 to 2.625 at
B8. This is still not a complete token recipe. Full evidence:
`verify/evidence/ternary-bonsai-ptq1-dual-swiglu-20260920.json`.

`kdot_f32_r8.comp` / `kdot_f32_r1.comp` are the GLSL twins of
`shaders/ggml_kdot_f32_r8.wgsl` / `ggml_kdot_f32.wgsl` (Q4_K 12 / Q5_K 13 /
Q6_K 14 / IQ4_XS 23, f32 activations, five storage bindings). `gen_kdot_guest.cljk`
reads a GGUF's tensor directory and writes a guest that `MAP`s the tensor by
file offset; `kdot_ref.py` is the CPU dequant oracle (first 64 rows),
`kdot_check.py` the comparison. All four formats agree with the oracle on all
three boxes (max rel err ≤ 1.4e-5). Real Nex tensors, 10 dispatches in one
command buffer:

| tensor (type, bytes) | B70 r8 / r1 | K16 iGPU r8 / r1 | Xavier r8 / r1 |
|---|---|---|---|
| `blk.0.attn_qkv` (Q5_K, 11.5 MB) | 25 / **98** GB/s | **21** / 21 | **13** / 1.2 |
| `blk.0.attn_gate` (IQ4_XS, 4.5 MB) | 14 / **57** | **17** / 13 | **11** / 4.4 |
| `blk.0.ffn_gate_exps` expert 0 (IQ4_XS, 0.56 MB) | 2.2 / **16** | 6.5 / **16** | 4.8 / 3.6 |
| `output` lm_head (Q6_K, 417 MB) | **135** / 107 | 38 / **43** | 6.7 / **12** |

Read across: the best layout is per (backend, tensor) — the same finding the
Deno-era table had — and the small tensors are launch-bound (B70 ≈ 0.1 ms per
dispatch inside a buffer, Xavier ≈ 0.5). Two NVIDIA-specific fixes on the way:
a dynamically indexed `ivec4`/constant array goes to local memory on nvgpu
(Q5_K at 1 GB/s until the loops were written out and the IQ4_XS codebook became
four packed words), and a live `VkDevice` at process exit segfaults in the
driver's atexit path (amu #1028 tears down in order). Xavier is still far from
its 54 GB/s f32 number — its own layout is the next co-scientist item.

## One whole recurrent layer on the native path (2026-09-19)

`nex_ops.comp` (15 entry points, `-DOP=<name>`, GLSL twin of `shaders/nex_ops.wgsl`
plus `gate_decay2` and an input offset for `l2norm`) and `deltanet_step.comp`
complete the kernel set for a gated-delta-net layer. `gen_layer0_guest.cljk`
reads the GGUF directory and writes the guest: 20 tensors `MAP`ped by file
offset, 37 buffers, 27 metas written, then **27 dispatches in ONE command
buffer** (`BEGIN … SUBMIT`) — rmsnorm → qkv/gate/alpha/beta kdots → gate_decay
→ conv1d → q/k l2norm → delta-net → gated rmsnorm → out kdot → add_rmsnorm →
router → softmax-top8 → 8-expert gate/up kdots (one dispatch each, `positions=8`)
→ silu·up → 8-expert down → shared expert → weighted sum → residual.
`layer0_ref.py` is the f64 numpy port of the retired Deno reference; token 9707,
position 0, `blk.0`:

| box | command buffer (27 dispatches) | x_out vs f64 | top-8 experts |
|---|---|---|---|
| B70 (ANV) | **0.93 ms** | rel 1.1e-6 | identical |
| K16 iGPU (RADV) | **1.55 ms** | rel 1.1e-6 | identical |
| Xavier (nvgpu, aarch64 kexe) | 48.9 ms | rel 1.0e-6 | identical |

Every intermediate read back (h, qkv, g/β, conv, delta-net out, resid, router,
top-k weights) matches to f32 precision. Estimate from this: 30 recurrent layers
at ~1 ms + 10 attention layers + the 417 MB lm_head ≈ 35–40 ms/token on B70
before any tuning (~25 tok/s class; llama.cpp Vulkan 60, vLLM 103); K16 ~16
tok/s class (llama.cpp CPU-only there: 11); Xavier needs its own kernel layout
(the small kdots are 10× slower than on Mesa).

Found on the way, now refused by the loader: a `WRITE`/`MAP`/`READ` while a
`BEGIN` is open reuses the one command buffer and silently discards the
recorded dispatches (the first layer run answered zeros) — amu #1028 refuses
them by name, and the generator hoists every constant write before `BEGIN`.

## The decode step through N layers, one command buffer (2026-09-19)

`gen_decode_guest.cljk <gguf> <layers> <dir> <out>` generalises the layer
generator: every tensor of layers `0..N-1` MAPped once, recurrent AND attention
layers (q/k/v kdots → per-head rmsnorm → NEOX rope → `attn_decode` with the
T = 1 cache → output kdot), then output norm → Q6_K lm_head (r8) → two-stage
argmax — all recorded into **one command buffer**. `decode_ref.py` is the f64
oracle (token 9707, position 0), `decode_check.py` compares the last hidden
state and the argmax. Depth is bounded by what the device can hold beside the
box's serving process (the full 40 layers are 18.7 GB):

| box | layers (of 40) | dispatches | command buffer | x vs f64 | argmax |
|---|---|---|---|---|---|
| B70 (ANV; vLLM holds 27 of 30 GB) | 4 (3 recurrent + 1 attention) + lm_head | 125 | **3.94 ms** | rel 2.9e-6 | 59315 = ref, logit 8.50742 = ref |
| K16 iGPU (RADV) | 12 + lm_head | 349 | **28.96 ms** | rel 4.6e-6 | 163967 = ref, logit 12.82849 = ref |
| Xavier (nvgpu, aarch64 kexe) | 16 + lm_head | 462 | 140.5 ms | rel 6.5e-6 | 204887 = ref, logit 13.07352 = ref |

Straight-line extrapolation to 40 layers (untuned kernels, position 0):
B70 ≈ 40 ms/token (~25 tok/s; llama.cpp Vulkan 60, vLLM 103), K16 iGPU ≈ 70 ms
(~14 tok/s; llama.cpp CPU-only there 11), Xavier ≈ 350 ms (~3 tok/s; llama.cpp
CUDA 18 — the nvgpu kernel layout is the open item).

Three bounds surfaced by name on the way and raised (amu #1028): 64 → 2048
dispatches per command buffer, 256 → 4096 buffers, the 1 MiB SOURCE bound that
`extract-native` applied to a 1.09 MB artifact (now the 8 MiB EDN bound); and
the guest needs `KEXE_PAIRS=1048576` (one pair per string) beyond ~300 requests.

## Greedy decode over tokens, entirely on the device (2026-09-19, kaizen loop tick 1)

`gen_decode_tokens_guest.cljk <gguf> <layers> <tokens> <prompt-id> <dir> <out>`:
the prompt id is `WRITE`n once; `embed_iq4xs.comp` dequantises the token's
embedding row on the device, reading the id from the prompt buffer for token 0
and from the **argmax buffer** for every later token — no id ever crosses back
to the host. State stays in device buffers across steps: conv ring, delta-net S,
and the KV cache (`copy_at` appends this token's rope'd k and v at row `pos`;
`attn_decode` runs with `T = pos + 1` and rope with `aux2 = pos`, all as
per-position metas written before the first `BEGIN`). One command buffer per
token. `decode_tokens_ref.py` is the stateful f64 oracle (ring / S / KV
carried), `decode_tokens_check.py` compares every step:

| box | layers | tokens | per-token command buffer | argmax per step |
|---|---|---|---|---|
| B70 (vLLM resident) | 4 | 3 | 16.8 / 11.2 / 6.7 ms | 59315, 149044, 169222 = ref |
| K16 iGPU | 12 | 3 | 28.7 / 27.8 / 27.8 ms | 163967, 1320, 11278 = ref |
| Xavier (aarch64 kexe) | 12 | 3 | 139.8 / 103.3 / 88.6 ms | 163967, 1320, 11278 = ref |

x after the last layer: rel ≤ 7.5e-6 at every step on every box.

A language ceiling met and routed around: binding every handle in one `let`
(358 bindings + the request temporaries over ~1,400 requests) hits kotoba-mir's
`:spill-frame-too-large` at 4,095 slots (the AArch64 `ldr [sp, #imm12*8]` reach).
The loader assigns buffer and pipeline handles sequentially per kind, so the
generator writes every handle as a literal and the program keeps nothing live
between requests — 5× less machine code, and the bound is not approached.

## Xavier (2026-09-19, kaizen loop tick 2)

Two findings, one lever pulled:

- **The GPU clock governor was the largest Xavier cost.** `nvpmodel` said MAXN
  but the GPU ran `nvhost_podgov` from 114 MHz, ramping per burst; our command
  buffers are bursts. With `jetson_clocks` (min = max = 1377 MHz) the 12-layer ×
  3-token chain went from 89–140 ms/token to a flat **59.7 ms/token** (1.5–2.3×).
  kotoba-lang/murakumo already ships `murakumo-xavier-performance.service` for
  exactly this; it was *disabled* on the box. Enabled and started 2026-09-19
  (persists across boots). The production llama-server there: 18.4 → 18.7 tok/s
  (sustained decode was already ramped; bursts were not).
- **The r1 structure, not the dequant arithmetic, is what nvgpu dislikes.**
  `kdot_ctrl_r1.comp` (r1 with a trivial one-load dequant — a probe, not a
  kernel) reaches only 5.8 GB/s where the f32 `dot_rows` reaches 54. `kdot_x8.comp`
  (256 threads per row, eight consecutive values per thread, `vec4` x loads,
  contiguous warp loads) brings Q5_K attn_qkv from 1.3 → **14.1 GB/s** and IQ4_XS
  attn_gate 4.4 → **10.5** — parity with r8 on nvgpu, and correct (rel ≤ 1.6e-5).
  In the composed 12-layer step it is *slower* than r1 (69 vs 60 ms): the many
  tiny kdots (32-row alpha/beta, 512-row experts) pay for 256-thread groups.
  The lm_head Q6_K stays at 17–20 GB/s on every layout (the 210-byte blocks are
  misaligned; a load-time repack is the next idea). Memory pressure is a confound
  on this box: 26 of 31 GB used with swap active while the 17 GB llama-server is
  resident.

**Correction (tick 3, same day).** The x8 numbers above were taken BEFORE the
clocks were pinned and are governor-confounded. With `jetson_clocks` in force,
r1 ≈ x8 ≈ r8 on Xavier: Q5_K attn_qkv 13.8 / 14.0 / 11.8 GB/s, IQ4_XS gate
10.8 / 10.4, lm_head 20.4 / 17.6 / 19.5. The structure claim survives in a
weaker form: the control probe reaches 33 GB/s and the f32 kernel 79 GB/s
(pinned), so the K-quant kdot on nvgpu loses ~2.4× to dequant arithmetic and
loads and ~2.4× more to the 64-thread structure. `kdot_s1_r1.comp` (the block's
16-byte header staged through shared memory once per block, scales read from
there) is the first real gain on the arithmetic side: 14 → **17 GB/s**, correct.

`gen_decode_tokens_guest.cljk` now takes a backend (`anv | radv | nvgpu`) and picks
the kernel per tensor class (`:wide` / `:narrow` / `:lm`) from `layout-table`. In the
composed 12-layer × 3-token step the table changes nothing measurable (K16
28.0 vs 27.8 ms; Xavier 60.4 vs 59.7): at this depth K16 is already near its
bandwidth (~0.9 GB of weights actually touched per token — 8 of 256 experts —
in 28 ms ≈ 32 GB/s of ~44), and Xavier's 60 ms is ~15 GB/s, i.e. the kdot
ceiling above plus per-dispatch cost. The next Xavier levers are the dequant
path (s1, then fewer loads per value) and fewer dispatches per layer.

**Tick 4 (iteration 9): `kdot_s2_r1.comp`** = s1 for every format (Q4/Q5 header,
IQ4_XS 8-byte header, Q6_K 16 scales + d through `weight_u32_at`) plus the
activation as one `vec4` load. Xavier, pinned clocks, 10 dispatches in one
command buffer, all oracle-exact (rel ≤ 1e-5):

| tensor | r1 | s1 | **s2** | x8 | s2-on-x8 (`kdot_s2_x8.comp`) |
|---|---|---|---|---|---|
| attn_qkv Q5_K | 14.0 GB/s | 17.0 | **18.9** | 14.0 | 14.4 |
| attn_gate IQ4_XS | 11.0 | 11.8 | **12.6** | 10.5 | 10.3 |
| ffn_gate_exps[0] IQ4_XS | 7.2 | 8.5 | **9.2** | 6.5 | 8.0 |
| output Q6_K | 20.1 | 20.1 | **20.6** | 17.6 | 14.8 |

Header staging does nothing for x8 (a warp's header loads were already one
broadcast); the gain is in the 64-thread r1 shape. With the nvgpu row of
`layout-table` set to s2 for all three classes the composed 12-layer × 3-token
step goes **60.0 → 54.0 ms/token** (argmax chain unchanged: 163967 → 1320 →
11278). On the K16 iGPU (RADV, one wave64 per workgroup) s2 is *slower* than r1
(attn_qkv 31.9 → 22.5 GB/s, experts 16.5 → 9.5; lm_head equal), so s2 stays
nvgpu-only — the layout table is no longer neutral, it carries this. Remaining
Xavier gap: 54 ms ≈ 17 GB/s against the 33 GB/s control probe.

**Tick 5 (iteration 10): barrier groups.** The "~0.5 ms per dispatch" above was
the single-dispatch *submit* latency, not the cost of a dispatch inside a
command buffer. Measured with a probe of N trivial dispatches in one buffer
(amu `test/fixtures/gpu/gpu-dispatch-floor*.kotoba`, slope 270 → 1080):

| box | per dispatch, with the loader's compute→compute barrier | without (`DISPATCHC`) |
|---|---|---|
| B70 ANV | **13 µs** | 0.18 µs |
| K16 RADV | 2.7 µs | 0.15 µs |
| Xavier nvgpu | 3.5 µs | 0.35 µs |

So dispatch count is a B70 lever (125 dispatches ≈ 1.6 of 3.9 ms at 4 layers),
a small one elsewhere, and the barrier — not the launch — is what costs. amu
PR #1029 adds `DISPATCHC`: recorded like `DISPATCH` but with no barrier before
it; the guest asserts the dispatch reads nothing written, and writes nothing
touched, since the last plain `DISPATCH`. The generator marks 18 of the 27
per-layer dispatches concurrent (qkv|gate|alpha|beta, gate_decay2×2|conv1d,
l2norm q|k, q|k|v, rmsnorm q|k, rope q|k|copy v, router|gate_sh|up_sh|shlogit,
softmax_topk|silu_sh, gate_exps|up_exps|down_sh) and orders the MoE tail so
the groups are contiguous — 27 → 15 barriers per layer. Results bit-identical
on all three boxes (same `x rel`, same argmax chains):

| box | before | after |
|---|---|---|
| B70 4L × 3T | 3.93 ms/token | **3.63** |
| K16 iGPU 12L × 3T | 28.4 | **27.4** |
| Xavier 12L × 3T | 54.0 | **52.8** |

Fusing kernels (rmsnorm+kdot etc.) would remove the same barriers and is now
worth less than it looked; the Xavier budget is still the kdot bandwidth
(~12.6 GB/s over the layers, 20 on the lm_head).

**Tick 6 (iteration 11): what the Xavier kdot ceiling actually is.** Three
probes on top of s2, all oracle-exact (Xavier, pinned clocks, GB/s):

| tensor | s2 | s3 (`subgroupAdd` reduction) | s3_r8 (8 rows/wg, named accumulators) | **s4** (all headers staged once, 2 blocks/iter) |
|---|---|---|---|---|
| attn_qkv Q5_K | 19.0 | 19.7 | 20.1 | 19.6 |
| attn_gate IQ4_XS | 12.1 | 13.0 | 11.3 | **13.7** |
| ffn_gate_exps[0] IQ4_XS | 8.4 | 9.2 | 6.4 | **9.6** |
| output Q6_K | 21.0 | 21.6 | 16.9 | **23.7** |

Refuted: the reduction tree (s3: +3%), the workgroup count (s3_r8: no
better), and the Q5_K "one word per four values" repack premise — the r1 layout
already touches each qs word twice and each qh word eight times from L1, so
the traffic is minimal and a 20-bit packing would add 55% bytes. What the
numbers say instead: in **values per second** every format sits at 26–29 G/s
(Q5_K 28.5, IQ4_XS 25.8, Q6_K 28.9) while the f32 kernel does 19.8 and the
trivial-dequant control 48 — an **instruction-issue ceiling** (~25
instructions per value on 512 cores × 1.377 GHz), not a memory one. s4 is the
nvgpu row now: composed 12-layer × 3-token **52.8 → 48.6 ms/token**.

Next levers are per-value instruction count: the Xavier driver reports
`shaderFloat16` + `shaderInt8` + 16-bit storage but **no
`VK_KHR_shader_integer_dot_product`**, so packed `f16vec2` FMAs (two values per
instruction) and the exponent-trick int→float conversion are the candidates;
`dp4a`-style int8 activations are not available on this driver.

**Tick 7 (iteration 12): packed-half dequant, `kdot_h2_r1.comp`** — Q4_K / Q5_K
codes become two `f16vec2` by the exponent trick (`0x6400 | q` is the half
1024 + q), IQ4_XS through a 16-entry half codebook in shared memory (one LDS
per value instead of three selects), the activation converted to halves once
per block, products as two packed multiplies. Q6_K keeps the f32 path. Xavier,
pinned clocks:

| tensor | s4 (exact) | h2 | h2 max rel err (random-normal x, 1e-2 floor) |
|---|---|---|---|
| attn_qkv Q5_K | 19.1 GB/s | **21.9** | 4.0e-2 |
| attn_gate IQ4_XS | 13.5 | **22.2** | 1.8e-2 |
| ffn_gate_exps[0] IQ4_XS | 8.7 | **13.7** | 4.5e-3 |
| output Q6_K | 23.7 | 24.1 (same path) | 1.4e-6 |

The error is the format, not a bug: against a reference computed with the
activation rounded to f16 the kernel's rel-RMS error is 8.6e-4 (attn_qkv), of
which the f16 rounding of x alone is 2.2e-4; the max-rel column is the
worst-case row of a random-normal dot with Σ|p|/|Σp| ≈ 120–170. The first
version summed the four products in a packed FMA chain (`qlo*ylo + qhi*yhi`
in f16) and drifted **3e-2** (`x rel`) over 12 layers; summing the four
products in f32 (two packed multiplies, four converts) brings that to
**6e-4 – 3e-3** at the same speed. Composed 12-layer × 3-token on Xavier:
**48.5 → 39.3 ms/token**, argmax chain unchanged.

This is a numerics decision, so h2 is an **opt-in row** (`nvgpu-h2`) and the
`nvgpu` default stays the exact s4. For comparison llama.cpp's Vulkan path
quantizes activations to Q8 per 32-block (≈4e-3 relative per activation),
coarser than f16; a like-for-like distribution comparison against llama.cpp
is the open parity item.

**Tick 8 (iteration 13): the parity probe, and why the first one was worthless.**
The f64 oracle now runs all 40 layers (K16, ~1 min/token) and saves the full
logits; llama-server (K16, CPU, the same GGUF) and vLLM (B70, W4A16 AutoRound)
were asked for the next-token distribution after the same single token 9707
(`prompt` as a token array, no BOS, `n_probs` / `logprobs`). Three engines, three
unrelated answers: oracle top-1 198 (p 0.134), llama.cpp top-1 19 (p 0.119,
198 at 0.099; KL(llama‖oracle) over its top-40 = **1.04 nats**), vLLM top-1 a
CJK fragment at p 0.0048. A single token at position 0 with no BOS is a
degenerate input on which nothing can be concluded — the fact that this is
the only prompt the guests could run was the real gap.

So the generator and the oracle take a **comma-separated prompt**: the first P
steps are forced to those tokens (prefill at decode speed, one command buffer
per token, KV/recurrent state carried), greedy decode continues from step P.
`decode_tokens_ref.py nex.gguf 9707,198,220 12 4` / the guest with the same
argument: K16 12 layers, all four steps match (argmax 163967 / 112516 /
169222 / 169484, `x rel` ≤ 6e-6, 27–28 ms per step). The helper modules
(`layer0_ref.py`, `decode_ref.py`) no longer run their own layer when
imported with a token list. The like-for-like llama.cpp comparison needs the
40-layer guest, which needs per-layer MAP/FREE streaming on the K16's 13 GiB
GTT — the next item.

**Tick 9 (iteration 14): the whole model on the K16 iGPU, and llama.cpp parity.**
`gen_decode_tokens_guest.cljk … radv stream` emits a *function-shaped* program:
`recurrent-layer [xin xout ring S]` and `attention-layer [xin xout kc vc]`
hold the layer's dispatches once; `layer-N [g]` MAPs its tensors, calls the
body, FREEs them; `main` calls the 40 layer functions per token. Two ceilings
forced that shape and both are real: the ABI allows **5 parameters** per
function (kotoba-sema `max-parameters`) and a module **64 KiB of string
literals** (`kotoba.kir.value/string-value-byte-limit`; the straight-line
40 × 5 program was 589 KB of source). Two consequences: the position is now
read on the device (`nex_ops.comp` `dyn_pos`: `p1 != 0` → `ids[0]` from a
16-byte `posbuf` the guest WRITEs once per token; `rope_neox`, `attn_decode`,
`copy_at`), so a layer's dispatches are the same request every token; and the
weight handles are literal even though they are MAPped per layer per token —
the loader hands out the lowest free slot, so every recurrent layer lands on
the same 19 slots and every attention layer on the lowest 16 of them, which the
generator simulates. The non-stream guest is unchanged in behaviour (K16 12 L
re-verified with the new kernels).

Result, K16 iGPU (RADV, GTT 13 GiB; the 17.4 GB GGUF is re-uploaded every
token from the page cache), prompt "The capital of France is" = `760,6511,314,9338,369`:

| | |
|---|---|
| 5 tokens × 40 layers, wall | 25.8 s (uploads; the lm_head buffer alone is 9.8 ms) |
| every step vs f64 oracle | argmax 271 / 314 / 279 / 369 / **11751** all equal; `x rel` ≤ 1.7e-4 (step 0), ≤ 1.5e-5 after |
| final logits vs oracle | max\|Δ\| 1.5e-5, KL(oracle‖gpu) 7e-13 nats |
| **vs llama-server (same GGUF, CPU)** | top-1 **11751 " Paris"** on both; KL(llama‖gpu) over llama's top-40 = **0.0143 nats**; llama mass on its top-40 0.907, gpu 0.911; gpu top-10 ⊂ llama top-40 10/10; p(Paris) 0.549 vs 0.474 |

So the native path computes the same model as llama.cpp; the 0.014 nats are
the two engines' rounding (llama.cpp quantizes activations to Q8 per 32-block).
`parity_check.py <loader output> <ref npz> <llama json>` prints all of the above.
The single-token probe of tick 8 was indeed the input, not the model.

**Tick 10 (iteration 15): the same on Xavier, for the exact and the packed-half
kernels — h2 becomes the nvgpu default.** Streaming fits beside the 17 GB
llama-server (weights re-read from NVMe every token: 85 s for 5 tokens; the
lm_head buffer is 18.1 ms). Same prompt, oracle copied from K16, CUDA
llama-server on the box:

| Xavier, 40 layers | s4 (exact f32) | **h2 (packed half)** |
|---|---|---|
| argmax chain vs oracle | 5/5 | 5/5 |
| `x rel` per step | 8.7e-5, 5e-6, 4e-6, 1e-5, 6e-6 | 6.5e-2, 4.2e-3, 4.8e-3, 4.8e-3, 1.2e-1 |
| final logits vs oracle | max\|Δ\| 6.7e-6, KL 8e-13 | max\|Δ\| 0.32, **KL(oracle‖gpu) 8.5e-4 nats** |
| vs llama-server (CUDA) top-40 | top-1 Paris, **KL 0.0167** | top-1 Paris, **KL 0.0142** |
| p(Paris) | 0.549 | 0.557 (llama 0.474) |

h2's distance from the f64 oracle (8.5e-4 nats) is twenty times smaller than
llama.cpp's own (~0.015), and its distance from llama.cpp equals the exact
kernel's. So `nvgpu` now means h2 for the wide/narrow classes (the lm_head
stays f32), and `nvgpu-exact` keeps s4. The hidden-state `x rel` of h2 is
large on some coordinates (1.2e-1 at step 4) while the distribution moves
8.5e-4 nats — the number that matters for serving is the second; both are
recorded.

**Tick 11 (iteration 16): the guest is a program, not a transcript.** The
default (`fn` mode; `flat` keeps the 2026-09-19 straight-line form for A/B)
computes its handles: `string-from-i64` exists in the profile, so
`recurrent-layer [w0 xin xout ring S]` / `attention-layer [w0 xin xout kc vc]`
build every request from `(+ w0 k)`; weights are MAPped at a stride of 19
handles per layer (attention layers pad with three 16-byte ALLOCs);
`layers [il n]` recurses over the layers (attention when `(bit-and il 3) = 3`,
state index `il - il/4` or `il/4`); `token-step [pos n acc]` recurses over the
tokens and accumulates the answers. The position and the tokens live on the
device: `embed_iq4xs` reads `tokbuf[pos[0]]` (binding 4, `dyn`), `argmax_final`
appends the next token to `tokbuf[pos + 1]` once past the prompt (binding 2 is
writable now), `pos_incr` bumps the counter. So the program no longer depends
on T except for the token buffer's size, and a 12-layer × 4-token guest is
30 KB of source instead of 200 KB. Trap found on the way: an nbb map literal
with more than 8 entries evaluates its values in *hash* order, so the layer's
MAPs came out scrambled — `layer-weights!` now MAPs in `rec-keys` / `att-keys`
order explicitly. Verified: K16 12 L, `9707,198,220` + 1 greedy — all four
steps match the oracle at 27.2–27.7 ms/token (flat: 27.0–27.8); Xavier 12 L × 3
(h2 default) 39.4 ms/token, chain 163967 → 1320 → 11278.

**Tick 12 (iteration 17): the third box.** B70 (Intel Arc Pro B70, ANV) ran the
same 40-layer streaming guest beside vLLM (27 of 30 GB held; the box has only
15 GB of host RAM, so the 17.4 GB GGUF is re-read from disk every token:
44.5 s for 5 tokens, lm_head buffer 6.6–8.6 ms). Same prompt, oracle from K16,
llama.cpp reference from K16:

| box, 40 layers, exact kernels | argmax vs oracle | final logits vs oracle | KL(llama‖gpu), top-40 | p(Paris) |
|---|---|---|---|---|
| K16 RADV | 5/5 | max\|Δ\| 1.5e-5 | 0.0143 | 0.549 |
| Xavier nvgpu (s4) | 5/5 | 6.7e-6 | 0.0167 | 0.549 |
| Xavier nvgpu (h2, default) | 5/5 | 0.32 (KL 8.5e-4) | 0.0142 | 0.557 |
| **B70 ANV** | **5/5** | **1.7e-5** | **0.0143** | **0.549** |

Three GPU architectures, three drivers, two ISAs of the same `.kotoba` program,
one distribution. The llama.cpp distribution-parity item is closed for the
fleet. Streaming stays a correctness tool: on a box that cannot page-cache the
model it is disk-bound.

**Tick 13 (iteration 18): sampling on the device.** `nex_ops.comp` `sample_topp`:
one workgroup over the vocabulary — `p = softmax(logits / T)`, the top-p set is
`{p ≥ τ}` for the largest τ whose mass reaches `top_p` (30-step bisection; the
sorted definition with boundary ties included), the draw is `u · mass` in index
order over 256 contiguous chunks, `u = mix32(seed ^ pos·0x9E3779B9) >> 8 / 2²⁴`
with `pos` from `posbuf`; the token goes to `ids[61]` (read back) and to
`tokbuf[pos+1]` past the prompt. `sample_test.kotoba` draws 256 times from one
fixed logits vector (the oracle's last step, `logits_last.f32`) advancing the
counter with `pos_incr`; `sample_check.py` recomputes every draw in f64 with
the same hash: K16, T 0.8, top-p 0.95 — top-p set 14 tokens (mass 0.9523),
**256/256 draws equal to the oracle**, all inside the set, empirical-vs-exact TV
0.052 (≈ the 256-sample noise). In the token loop (`fn` mode, 9th argument
`sample:T:top_p:seed`; `decode_tokens_ref.py … --sample T top_p seed` is the
oracle) K16 12 L, 3 forced + 3 sampled: **6/6 tokens equal** (18171 / 84249 /
236687 / 112516 / 21356 / 226585). Cost: the single-workgroup sampler is 4.8 ms
per draw on K16 (27.5 → 32 ms/token). Not implemented: top-k, repetition
penalties, min-p.

**Tick 14 (iteration 19): the sampler on 61 workgroups.** Same definition,
split into `sample_part` (61 wg: partial max and partial Z relative to it) →
`sample_probs` (61 wg: global max/Z from the 61 partials, `p_i` into a 1 MB
scratch, lo/hi reset) → 30 × (`sample_bisect_part` (61 wg: mass of `p ≥ mid`
per chunk) + `sample_bisect_step` (1 wg: sum, move lo or hi)) →
`sample_final` (1 wg: index-order draw over the set). 63 dispatches, one
scratch of 1 KB for partials + lo/hi and one for `p_i`. `sample_test.kotoba`
now runs this chain (65 dispatches per draw, one command buffer per draw
because of the 2048-dispatch cap): **256/256 draws equal the oracle**, same
picks as the single-workgroup op, **1.25 ms** per draw command buffer (was
4.8). In the token loop: K16 12 L 3 forced + 3 sampled 6/6, **28.6 ms/token**
(greedy 27.5, single-workgroup sampler 32.0); Xavier 12 L with the exact
kernels 6/6 at 49.7 ms (greedy 48.5); Xavier with the **h2** default 40.7 ms but
the *sampled* tokens differ from the oracle from step 0 (18185 vs 18171 —
neighbouring ids): at 12 layers the distribution is flat, the top-p set is
huge, and h2's ~1e-3 probability shifts move the index-order draw to a nearby
token. That is the format's numerics, not the sampler (the same SPIR-V picks
256/256 on exact probabilities); sampled-output comparisons against an oracle
must use the exact kernels or compare distributions, not token chains. The
single-workgroup `sample_topp` stays in `nex_ops.comp` as the reference form.

**Tick 15 (iteration 20): the whole model resident on one GPU.** The owner
stopped Xavier's llama-server (`murakumo-xavier-nex-n25-mini.service`, 21 GB
of device memory) for this path (2026-09-19, order A → B → C). The `fn`-mode
guest with 40 layers and the `nvgpu` (h2) row then runs resident — 17.4 GB of
weights MAPped once in 19 s, then one command buffer per token:

| Xavier, 40 layers resident, h2 | |
|---|---|
| ms/token (12 tokens: 5 prompt + 7 greedy) | **89.3–89.6, mean 89.5 → 11.2 tok/s** |
| vs oracle | 12/12 argmax equal; final logits as tick 10 |
| greedy continuation of "The capital of France is" | ` Paris.<\|im_end\|>\n<think>\n\n</think>\n\n` |
| llama.cpp CUDA on the same box (stopped) | 18.7 tok/s |

The first full-model number of the native path, and it is what the 12-layer
extrapolation said (1.8 ms/layer × 40 + 18 ms lm_head). The token budget is
72 ms of layers (kdot at the nvgpu instruction-issue ceiling) + 18 ms of
Q6_K lm_head on the f32 path; those two are the A items that follow.

**Tick 16 (iteration 21, A-2): the Q6_K lm_head on the half path — and a
regression caught by A/B.** `kdot_h2_r1.comp -DQ6_HALF` → `kdot_h2q6_r1.spv`:
the 6-bit codes as bytes (ql nibble | qh 2 bits), exponent trick with 1056,
packed multiplies, f32 sums. Bench (Xavier, lm_head Q6_K): s4 23.7 → **26.6
GB/s** (17.7 → 15.9 ms per dispatch; Q6_K's 210-byte blocks keep it
unaligned-load bound), max rel err 3.4e-3 on random x. The first attempt put
the arm into the same binary as the Q5_K / IQ4_XS arms, and the 40-layer
token went 88.9 → **94.7 ms** although the lm_head itself got faster: the extra
arm raised the register pressure of the whole uniform-branch kernel and cost
the other formats ~5 ms per token. Caught only because the previous guest was
re-run in the same session (89.5 → 94.7 with the *same* guest binary, since it
names the `.spv` by path). So the Q6 arm is a separate binary
(`kdot_h2q6_r1.spv`, the `:lm` row), the wide/narrow binary is byte-identical
to tick 15, and the resident 40-layer token is **88.9 → 86.9 ms (11.5 tok/s)**,
12/12 oracle, KL(oracle‖gpu) 1e-7 at the last step. `fn`-mode guests now
append the final logits to the last token's answer, so `parity_check.py` works
on them too (needs `KEXE_STRING_POOL` ≥ 8 MiB).

**Tick 17 (iteration 22, A-3 preparation): where the 71 ms of layers go.**
`profile_guest.py` turns a flat one-token guest into one whose every dispatch
runs alone in its own command buffer (grouped `timed` functions; 112 nested
lets exhausted the desugarer's stack) and reports per op. Xavier, 4 layers,
min of two runs, each figure carrying the ~0.07 ms single-submit floor:

| recurrent layer (sum 4.8 alone; ~1.8 in-buffer) | ms | attention layer (4.2 alone) | ms |
|---|---|---|---|
| qkv 8192×2048 Q5_K | 0.82 | attn_out 2048×4096 | 0.47 |
| gate 4096×2048 IQ4_XS | 0.40 | q 8192×2048 | 0.44 |
| down_exps 2048×8 | 0.37 | down_exps 2048×8 | 0.37 |
| gate_exps / up_exps 512×8 | 0.26 / 0.26 | gate_exps / up_exps | 0.26 / 0.26 |
| deltanet | 0.26 | gate_sh / up_sh 512 | 0.21 / 0.22 |
| ssm_out 2048×4096 | 0.24 | softmax_topk | 0.19 |
| gate_decay2 (beta) | 0.23 | router f32 | 0.16 |
| alpha 32 / beta 32 | 0.22 / 0.15 | add_rmsnorm | 0.14 |

Reading: the big K-quant kdots (qkv, gate, ssm_out/attn_out, the three expert
kdots) are ~75% of a layer and all sit at the nvgpu instruction-issue ceiling
measured in tick 6 (~28 G values/s); fusing the element-wise ops around them
would buy 10–15%. The tiny kdots (alpha/beta 32 rows, gate_sh/up_sh 512) cost
0.1–0.2 ms each because 32–512 workgroups of 64 threads cannot fill 8 SMs —
a split-K layout for narrow kdots is the one cheap win left (~0.25 ms/layer,
≈10 ms/token). Budget arithmetic for the A target: the token touches ~2.6 G
weight values; at 28 G values/s that is ~90 ms, and llama.cpp CUDA's 18.7
tok/s (53 ms) needs ~50 G values/s — what `dp4a` gives it and what this
Vulkan driver does not expose (`VK_KHR_shader_integer_dot_product` absent,
tick 6). Realistic Vulkan ceiling on Xavier with the remaining items: ~75 ms
≈ 13 tok/s, i.e. 0.7× llama.cpp CUDA. That is a decision for the owner, not a
kernel.

**Tick 18 (iteration 23, B-1): the same profile on B70, and the barrier
halved.** `profile_guest.py` on B70 (ANV, vLLM resident): the single-submit
floor is ~0.11 ms and almost every op sits *at* it — subtracting it, a
recurrent layer is qkv 0.09, deltanet 0.07, down_exps 0.06, gate 0.05,
gate_exps / up_exps 0.05 each, ssm_out 0.04, everything else ≈ 0; the lm_head
(r8) 1.59 ms = 262 GB/s, so the B70's memory is faster than the 160 GB/s the
f32 probe suggested (that probe was compute-bound). Kernel work per layer
≈ 0.35 ms, in-buffer layer ≈ 0.46 ms → the difference is the **15 barriers ×
13 µs**, i.e. ~40% of a layer — on B70 the barrier is the item, the opposite
of Xavier. amu PR #1031: when the device is Vulkan 1.3 the loader records a
`synchronization2` barrier naming `SHADER_STORAGE_WRITE → STORAGE_READ|WRITE`
only; the 1.0 `SHADER_READ` also covers uniform / sampled reads and ANV flushes
twice as much for it. Floor per dispatch **13 → 6.6 µs**; the 4-layer × 3-token
guest **3.81 → 3.50 ms/token**, bit-identical. RADV: no difference; Xavier's
JetPack headers are Vulkan 1.2, so the block compiles out there. Corrected
B70 estimate for 40 layers: 40 × ~0.40 + 1.8 ≈ **18 ms/token ≈ 55 tok/s**
(the earlier "~28 tok/s" multiplied the 4-layer figure without separating the
lm_head). Remaining B levers, in order: fusing the ~20 element-wise dispatches
per layer into the kdots (the other half of the barrier cost), expert kdot
bandwidth (90 → 200+ GB/s), qkv at 128 GB/s.

**Tick 19 (iteration 24, B-2): the fused delta-net step — correct, and
neutral.** `deltanet_fused.comp` does, per head, in one dispatch of 128
threads: conv1d + silu on the head's q / k / v channels (the conv ring is
double-buffered by the position's parity, because q / k channels are shared by
two heads), the l2 norms, the gate and beta from alpha / betaL / dt / a, the
delta rule on S, and the gated rmsnorm × silu(z) — seven dispatches and four
barriers of the recurrent path become one (27 → 21 dispatches per recurrent
layer; 13 bindings, so amu #1032 raises the cap to 16). Oracle-exact on both
boxes. Timing, A/B twice each: B70 4 L × 3 T **3.51 → 3.49 ms/token**; Xavier
12 L × 3 T **37.3 → 37.3 ms**. So the "barriers are 40% of a B70 layer" reading
of tick 18 was the floor probe's artefact: between *real* dispatches the drain
overlaps with work and a removed barrier is worth ~1 µs, not 6.6. Fusion is
the default (`<mode>-nofuse` keeps the seven-dispatch path for A/B) because it
is simpler and never slower, but it is not a B lever; the B70 layer's ~0.46 ms
is kernel time plus launch gaps of small dispatches, and the next B levers are
the kdots themselves (expert kdots at ~90 GB/s and qkv at ~130 on a ≥ 260 GB/s
device).

**Tick 20 (iteration 25, B-3): the B70 kernel zoo at a pinned clock.** The B70
idles at **400 MHz** (`/sys/class/drm/card0/device/tile0/gt0/freq0`, max 2800)
and a ten-dispatch bench does not ramp it: the same kernels measured 19–26 GB/s
cold and 120–260 GB/s with `min_freq` pinned — the Xavier governor story again
(tick 2). Composed decode steps ramp the clock themselves (4 L × 3 T 3.50 ms
either way), so only the micro-benches were wrong. Pinned, GB/s:

| tensor | r1 | s2 | s4 | h2 | x8 | **r8** | s3_r8 |
|---|---|---|---|---|---|---|---|
| attn_qkv Q5_K | 121 | 120 | 141 | 134 | 143 | **170** | 105 |
| attn_gate IQ4_XS | 90 | 79 | 91 | 102 | 97 | 91 | 104 |
| ffn_gate_exps[0] (1 expert) | 30 | 29 | 31 | 31 | 30 | 14 | 15 |
| output Q6_K | 151 | 133 | 195 | 192 | 173 | **261** | 187 |

The `anv` row's `:wide` class moves to r8 (qkv +40%); `:narrow` stays r1 (r8
starves on 512-row tensors); `:lm` was r8 already. Composed 4 L × 3 T on B70:
**3.50 → 3.45 ms/token** — the wide kdots are a small share of the layer. The
B70 budget, restated with these numbers: a recurrent layer's ~36 MB of weights
at 260 GB/s is 0.14 ms; the layer takes ~0.46. The rest is latency: the
delta-net step is 32 workgroups × 128 threads each walking two serial 128-step
loops (~0.065 ms, ~2 ms per 40-layer token), the expert kdots run at ~90 GB/s,
and ~20 small dispatches per layer each cost their launch. Those three, in that
order, are the remaining B levers.

**Tick 21 (iteration 26, B-4): the delta-net step on 512 threads.**
`deltanet_fused.comp` now runs 512 threads per head: thread `(j = t & 127,
part = t >> 7)` owns value column j and a quarter of the 128 keys in both state
loops, the four partial `kv_mem` / `o` are summed through shared memory, the
conv / l2 / gated-rmsnorm parts stay on part 0. Oracle-exact on all three boxes
(B70 `x rel` 4.9e-6, Xavier 3.1e-3 with h2, K16 chain equal). Per token,
A/B'd: **B70 4 L × 3 T 3.46 → 3.30 ms** (−0.053 ms per recurrent layer, ≈ −1.6 ms
on 40 layers), **Xavier 12 L × 3 T 37.1 → 36.4**, **K16 12 L 27.3 → 27.3** (RADV's
wave64 already had the parallelism). `profile_guest.py --report` knows the
fused layer's 21 labels.

**Tick 22 (iteration 27, B-5): the expert kdots get their own class.** The
layout table has a fourth class, `:expert` (the three 8-position expert kdots;
falls back to `:narrow` when absent). On B70 the experts move to r8: 4 L × 3 T
**3.30 → 3.06 ms/token** (−0.06 ms per layer, ≈ −2.4 ms on 40 layers),
oracle-exact; the same for the *narrow* class (alpha/beta 32 rows, k/v/shared
experts 512–2048) **loses** (3.15 — small row counts starve r8's 8-rows-per-
workgroup shape), so `anv` is now wide r8 / narrow r1 / expert r8 / lm r8. On
K16 (RADV) experts on r8 are neutral (27.2 vs 27.3, bandwidth-bound), so the
`radv` row is unchanged. B70's 40-layer estimate: ~14 ms/token, ~70 tok/s class
(still an extrapolation from 4 layers — a resident run needs vLLM's memory).

**Tick 23 (iteration 28, B-6): consolidation measured, one class split found.**
`kdot_f32_r8_dual.comp` computes gate and up for the same eight (expert, row)
pairs from one x read and writes `silu(gate)·up` directly — three dispatches
(gate_exps, up_exps, silu_mul) become one. Correct, and **slower**: 3.06 → 3.09
ms on B70 (two weight streams and four accumulator arrays per thread; the two
separate dispatches were already concurrent). Kept as `:expert-dual` in the
table for A/B, not used. The per-op profile of the current layer (pinned
clock, floor-subtracted) then showed the real item: **ssm_out / attn_output
(2048 rows × 4096 cols) on r8 get only 256 workgroups** and had slowed from
0.04 to 0.063 ms when `:wide` moved to r8 in tick 20 — the "wide" class was
two shapes. A fifth class `:out` puts them back on r1: **3.05 → 2.96 ms/token**
(oracle-exact). `anv` = wide r8 / narrow r1 / expert r8 / out r1 / lm r8.
Session tally for B70's 4-layer token: 3.63 (tick 5) → 2.96; 40-layer estimate
≈ 40 × 0.315 + 1.7 ≈ **14 ms, ~70 tok/s**. Small-dispatch consolidation is
closed as a B lever (ticks 19 and 23 both measured it at 0 to −1%).

**Tick 24 (iteration 29): the memory floor, and the row sweep.** `mem_probe.comp`
+ `mem_probe.kotoba` stream 1 GiB with pure `vec4` loads (4096 workgroups × 256
threads × 64 vec4, ten dispatches in one buffer): **B70 598 GB/s** (pinned),
**K16 46 GB/s**, **Xavier 103 GB/s**. Against that floor the K-quant kdots sit
at 28–44% on B70 (qkv 170, lm_head 261), 70–95% on K16 (bandwidth-bound, as
tick 3 said) and ~20% on Xavier (instruction-bound, as tick 6 said). The token
floor on B70 is 1.3 GB / 598 GB/s ≈ 2.2 ms — vLLM's 9.7 ms is far from it too.
`kdot_f32_r8.comp` takes `-DROWS`; the sweep on B70 (pinned, GB/s): attn_qkv
r1 120 / **r4 172** / r8 168 / r16 128 / r32 69; lm_head r1 152 / r4 256 /
**r8 261** / r16 131 / r32 132 — rows in flight saturate at 4–8 and spill past
16, so the remaining 2.3× to the floor on ANV is the per-value dequant
arithmetic, the same wall Xavier hit at a lower height. `gen_kdot_guest.cljk`
accepts `r1 | r4 | r8 | r16 | r32`. Next kernel: an r8-shaped packed-half kdot
for ANV (h2's arithmetic, r8's rows in flight), with the 40-layer parity
measurement before it can become the `anv` default.

**Tick 25 (iteration 30, B-7): packed half on ANV — refuted; and the lever
ANV does have.** `kdot_h2_r8.comp` (r8's eight rows in flight, h2's exponent-
trick halves and packed multiplies, shared half codebook for IQ4_XS). B70,
pinned, vs the f32 r8: attn_qkv Q5_K 162 → **103** GB/s, attn_gate IQ4_XS 90 →
111, single expert 13 → 16, lm_head Q6_K 261 → **191**. Packed half is not
cheaper on Xe2 in this shape — the byte composition of the codes costs what the
half multiplies save, and Q5_K / Q6_K lose outright. The `anv` row stays f32;
the kernel is kept as a measured negative. The floor-to-kernel gap on ANV is
therefore not "arithmetic that halves in fp16". What Xe2 *does* expose, and the
Xavier driver does not: **`VK_KHR_shader_integer_dot_product` with
`integerDotProduct4x8BitPackedSignedAccelerated` (B70 and K16 both)** — the
`dp4a` path llama.cpp's CUDA kernels live on: quantize the activation to int8
per 32-block once per token, then one packed 4×8-bit dot per four values with no
int→float conversions (the K-quant `codes` words are already byte-per-code, so
the dot consumes them directly; mins and the Q6_K −32 fold into a Σx term).
That is the next kernel, and its numerics are llama.cpp's own.

**Tick 26 (iteration 31, B-8): the dp4a kdot, measured.** `nex_ops.comp`
`quant_q8` (per 32-value block: scale = max|x|/127, int8 codes four to a word;
thread = block) and `kdot_i8_r8.comp` (r8 shape; `dotPacked4x8EXT` on the
byte-per-code K-quant words against the int8 activation word; the K-quant mins
and Q6_K's −32 use one more dot with `0x01010101`; IQ4_XS packs the four
codebook values into an int; six bindings). The system glslang (15.1) does not
know `GL_EXT_integer_dot_product`; glslang 16.6 from the Khronos release does
(`/opt/glslang-16.6`, `glslang16` on B70). `gen_kdot_guest.cljk … i8r8` runs the
quantizer then the kdot. B70, pinned:

| tensor | f32 r8 | **i8 r8** | i8 error vs f64 |
|---|---|---|---|
| attn_qkv Q5_K | 168 GB/s | **193** | rel-RMS 6.1e-3 (max-rel 0.20 on the 1e-2 floor) |
| attn_gate IQ4_XS | 90 | 99 | |
| ffn_gate_exps[0] | 13 | 14 | |
| output Q6_K | 261 | **289** | rel-RMS 4.5e-3 |

Correct at Q8-activation precision (the error is the quantization of a
random-normal activation, llama.cpp's own regime) and **+11–15%** — not the 2×
the floor suggested, so on ANV the K-quant kdot's remaining cost is not the
multiply-accumulate either: what stays is the code extraction (shifts, masks)
and the 4-byte-granular loads (the 598 GB/s floor was measured with 16-byte
`vec4` loads; the block layout gives each thread 4-byte words). The lever that
is left is layout: 16-byte loads per thread (`uvec4`, 16 values per thread per
block) with rows in flight — an "r8 × x16" kernel. Wiring `i8r8` into the token
loop needs a `quant_q8` before each of a layer's six kdot inputs; that is the
generator work of the next tick if the layout idea does not beat it.

**Tick 27 (iteration 32, B-9): three more hypotheses for ANV's kdot ceiling,
all measured, none it.** (1) *Load width*: `mem_probe_u32` streams the same
1 GiB with 4-byte loads — **593 GB/s**, same as `vec4` (598); granularity is not
the cause. (2) *Occupancy*: `kdot_f32_r8k4.comp`, the r8 kernel with the block
loop split across four thread groups (256 threads per workgroup, same rows in
flight): attn_qkv 162 → 162, attn_gate 91 → 111, lm_head 261 → 236. (3) *Load
instruction count*: `kdot_s4_r8.comp`, block headers staged through shared
memory once per block for all eight rows: attn_qkv 162 → **132**, lm_head 261 →
196 — the added shared memory and per-block barriers cost more than the header
loads they remove (the lm_head takes no staged path and still lost, so the
shared allocation itself reduced occupancy). What is left, and consistent with
every number so far: the *coalescing pattern inside a block*. In the r8 layout
a 64-thread load instruction for one row touches 128 B of `qs` with 50%
redundancy (threads t and t+8 read the same word for the two nibble halves)
plus 32 B of `qh`, while the probe's instructions read 256 contiguous bytes;
`kdot_x8` (eight consecutive values per thread, no redundancy) was the best
r1-shaped kernel on B70 (143 vs 121) but is one row per workgroup. The next
kernel is x8's thread mapping with r8's rows in flight ("x8 × r8"). Both
negatives are kept for A/B.

**Tick 28 (iteration 33, B-10): x8 × rows.** `kdot_x8r8.comp` (`-DROWS`): 256
threads = 8 block slots × 32 lanes, a lane owns eight consecutive values, R rows
per workgroup share the activation's two `vec4`. B70, pinned, GB/s:

| tensor | f32 r8 | x8 × r8 | **x8 × r4** |
|---|---|---|---|
| attn_qkv Q5_K | 163 | 159 | **199** |
| attn_gate IQ4_XS | 90 | 104 | |
| ffn_gate_exps[0] (1 expert) | 14 | **29** | |
| output Q6_K | 261 | 173 | **272** |

Composed 4 L × 3 T: wide + lm on x8r4 **2.97 → 2.82 ms/token** (oracle-exact);
experts on x8r8 lose in the 8-position shape (3.27), so `anv` = wide x8r4 /
narrow r1 / expert r8 / out r1 / lm x8r4. Rows-per-workgroup is now read from
the kernel's name (`…r8.spv` → 8, `…r4.spv` → 4, else 1). Coalescing inside the
block was a real factor (qkv +22%), not the whole gap: 199 of 598. Session
tally, B70 4-layer token: 3.63 → 2.82 (−22%); 40-layer estimate ≈ 40 × 0.28 +
1.7 ≈ **13 ms, ~75 tok/s**.

**Tick 29 (iteration 34, B-11): dp4a on x8r4, wired into the token loop, and
the parity that makes it the ANV default.** `kdot_i8_x8r4.comp` (two
`dotPacked4x8EXT` per lane per block on the x8 mapping, 4 rows): B70 pinned
attn_qkv **221 GB/s** (f32 x8r4 199, session start r8 163), attn_gate 127 (90),
lm_head **321** (272 / 261) — the coalescing and the integer-dot gains stack.
The generator quantizes an activation once per layer (`quant_q8` into a paired
`[xq xscale]` buffer, rows `:wide-i8` / `:lm-i8` / `:expert-i8` name the int8
kernels). Composed 4 L × 3 T: **2.83 → 2.55 ms/token (−10%)**; int8 experts add
nothing (2.58) and stay f32 r8. 40-layer streaming parity on B70, same prompt:
5/5 argmax = oracle, **KL(oracle‖gpu) 3.4e-3 nats, KL(llama.cpp‖gpu) 0.0054** —
closer to llama.cpp than the exact kernels' 0.0143, as it should be (the same
Q8-activation regime); p(Paris) 0.535 (llama 0.474, exact 0.549). The hidden
state's `x rel` reaches 0.42 at the last step while the distribution moves
3.4e-3 nats — the same shape as h2 on Xavier, and the same rule: decide on the
distribution. `anv` = int8 wide / lm, `anv-exact` keeps f32. Session tally, B70
4-layer token: 3.63 → **2.55 (−30%)**; 40-layer estimate ≈ 40 × 0.21 + 1.7 ≈
**10 ms, ~100 tok/s class** — vLLM's 103 is within reach of the estimate; a
resident run is what turns it into a measurement.

**Tick 30 (iteration 35): the same int8 path on K16 — measured, not adopted.**
RADV also exposes the 4×8 integer dot; glslang 16.6 installed on K16 and the
same kernels compiled. K16 (GB/s): attn_qkv f32 r8 25.7 / r1 22.3 / **i8 x8r4
21.9** / i8 r8 20.0; lm_head f32 r1 43.1 / r8 38.2 / **i8 x8r4 44.2** / i8 r8
38.4; attn_gate i8 x8r4 17.4. Against a 46 GB/s floor the K16 kdots were already
at 55–95%, and the int8 path buys nothing (qkv loses, lm_head +2%) while
adding the Q8 numerics — so `radv` stays f32 (wide r8 / narrow r1 / lm r1).
Per box, the kdot story is now: K16 bandwidth-bound (nothing left in the
kernel), B70 issue/coalescing-bound (int8 × x8r4 landed), Xavier
instruction-bound without an integer dot (h2 landed, dp4a unavailable).

**Tick 31 (iteration 36, C-1 groundwork): the kernels are prefill-ready.** A
real prefill runs the prompt's P tokens through each layer as *one* batch where
the math allows and P sequential steps where it does not: the kdots take
`positions = P` with `input_per_expert = 1` (the activation is `[P × n]`, the
weights are read **once** instead of P times — the whole point); rmsnorm /
rope / softmax / silu are row-wise already; the delta-net step and causal
attention are recurrences and run P dispatches each, one per token. Two kernel
changes make that possible and change nothing for decode: `deltanet_fused`
reads its **row** from `pos[1]` (which token of the batch; 0 in decode) and
offsets `qkv / alpha / betaL / z / out` by it; every kdot's `in_row` is
`position / pad0` when `Meta.pad0 > 1` (the MoE prefill has 8 expert positions
per token). Decode re-verified on all three boxes after the rebuild (B70 2.58
ms, K16 27.3, Xavier 36.6). Dispatch arithmetic for a P-token prompt on 40
layers: decode-as-prefill = P × ~21 dispatches and P weight passes; batched =
~21 + 2P dispatches (the two recurrences) and one weight pass — for P = 16 the
weight traffic per prompt drops 16×, the dispatch count 5×. The generator's
`prefill` mode (batched layer bodies, a `stepbuf` for the recurrences, MoE ids
`[P × 8]`, lm_head on the last row) is the next tick.

**Tick 32 (iteration 37, C-1): batched prefill, recurrent layers.**
`gen_decode_tokens_guest.cljk … <backend> prefill` (the prompt is the batch,
`tokens` = 1): every buffer that holds an activation is `P` rows; the kdots run
with `positions = P`, `input_per_expert = 1` and a zero `expert_ids` of P
entries (the MoE experts with `8P` positions and `pad0 = 8`); `rmsnorm`,
`add_rmsnorm`, `f32_matvec`, `softmax_topk`, `weighted_sum` and the embedding
gained a row dimension (workgroup x or y = row; decode dispatches shape 1 and is
unchanged); the delta-net step runs P dispatches on a per-layer `stepbuf`
advanced by `pos_incr2` (absolute position and batch row together); the final
norm runs on all rows and the lm_head reads the last one (`pad1`). The answer
is `ns | x of all P rows | argmax`; `prefill_check.py` compares every row with
the oracle's per-step hidden states (same math, so they must agree). K16,
3 recurrent layers, the 8-token prompt "The capital of France is. The capital":

| | dispatches | time | vs oracle |
|---|---|---|---|
| decode, 8 steps | 8 × (21 + tail) | 118.6 ms (14.1–16.1 per token) | 8/8 argmax, `x rel` ≤ 5e-6 |
| **prefill, one command buffer** | 113 | **40.2 ms** | **8/8 rows `x rel` ≤ 5e-6**, argmax 261 = oracle |

2.9× on the whole; the lm_head (~10 ms on K16) is paid once either way, so the
layers went from ~37 ms to ~30 — the batched kdots read the weights once but
the delta-net's P sequential dispatches remain the prefill's cost on a
recurrent layer. Attention layers are not batched yet (the generator refuses
them in prefill mode; `layers ≤ 3` on this model), so this is the recurrent
half of C-1. Decode paths re-verified on K16 (3 L, 8/8) after the kernel
changes; B70 and Xavier kernels rebuilt in tick 31's pass.

**Tick 33 (iteration 38, C-1 second half): attention layers batched.** In
prefill the attention layer is fully parallel over the prompt: q / k / v kdots
with `positions = P`, the head-wise rmsnorm over `16P` / `2P` rows, `rope_neox`
takes the token from the head row (`h / rows`, position `base + token`), the
KV copies are one contiguous `512P` write, and `attn_decode` runs `(16, P)`
workgroups — query row `y`, causal `T = base + 1 + y`, since all P keys are in
the cache before the dispatch. Unlike the delta-net there is no sequential
step. K16, 12 layers (9 recurrent + 3 attention), the same 8-token prompt:
decode 8 steps **217.3 ms** (26.9–27.6 per token), prefill **122.5 ms** (1.8×),
**8/8 rows `x rel` ≤ 1.3e-5**, argmax 240548 = oracle. The prefill's cost is
now the recurrent layers' P delta-net steps (9 layers × 8 dispatches); the
attention layers are one pass. Decode re-verified on all three boxes after the
kernel change (B70 2.58 ms, Xavier 36.8, K16 chain equal).

**Tick 34 (iteration 39): where the prefill's time went, and the kdot that
reads weights once.** `profile_guest.py` on the 12-layer prefill (407
dispatches): the kdots were **105 of 122 ms**, the delta-net steps 12 — because
the `(rows, positions)` dispatch gives every position its own workgroup and
re-reads the row, so a P-token prefill read the weights P times exactly like
decode (the 1.8× had come from amortised launches and the single lm_head).
`kdot_f32_p.comp` puts the positions in the *inner loop*: one workgroup per
row, the block dequantized once, multiplied against every position's
activation (P ≤ 16), reduction per position. It serves every kdot whose
weights do not depend on the position (all but the MoE experts). K16, 12
layers, 8 tokens: prefill **122.5 → 84.5 ms** (decode 8 steps 217.3), all 8
rows `x rel` ≤ 1.3e-5. Left in the prefill: the MoE expert kdots (their
weights differ per position; sharing needs grouping by expert), the delta-net's
P steps (~12 ms), the lm_head (~10 ms).

**Tick 35 (iteration 40, C-2): the tokenizer.** `gguf_tokenizer.cljk` (kbb) reads
`tokenizer.ggml.tokens` / `merges` / `pre` from the GGUF header alone and
implements byte-level BPE — the qwen2/gpt2 pre-tokenizer regex (`\p{L}` /
`\p{N}` classes, the contraction and whitespace alternatives), GPT-2's
byte→unicode map, greedy lowest-rank merges — and the inverse for decode.
`tokenizer_check.cljk` runs a corpus through it and through llama-server's
`/tokenize` (`add_special false`): **12/12 lines equal** on
`tokenizer_corpus.txt` (English, Japanese, Korean/Russian, German with
apostrophes, Python, prices and dates, emoji, contractions, leading/trailing
and multiple spaces, a URL), and decode round-trips the text. This is the
serving shell's text ↔ ids; the guest keeps taking ids. Not covered yet:
special tokens (`<|im_start|>` etc. must be spliced by the chat-template layer,
not the BPE), and `add_special` (Qwen adds no BOS).

**Tick 36 (iteration 41, C-3-1): the prompt at run time.** One guest binary
now serves any prompt: `… <backend> fn - runtime` emits an exported
`serve [plen ntok]` beside `main` (the frontend requires `main` to take no
arguments; the loader passes i64 argv to an exported entry —
`extract-native --symbol serve`, arity 2). `serve` reads the prompt as a
decimal list from `:env/read NEX_PROMPT` and writes it to the token buffer
with the loader's new `WRITEDEC` (amu #1034; the guest formats decimals but
has no hex, no `string->i64`, no `string-length` on the native slice — those
three refusals shaped the design), rewrites `argmax_final`'s prompt-length
meta the same way, and runs the token loop for `plen + ntok` steps; the token
buffer holds 4096 slots and the KV caches a 4096-token context. Policy gains
`[:cap/call 33]`. K16, 12 layers, one binary: `NEX_PROMPT=9707,198,220 … 3 1`
→ 163967 / 112516 / 169222 / 169484 (4/4 = oracle); `NEX_PROMPT=760,6511,314,
9338,369 … 5 3` → 8/8 = oracle, 26.6–27.8 ms/token. The first attempt sized
the KV cache from the build-time token count and the second prompt's step 4
read past it — argmax happened to match while `x rel` was 1.2; the row check
caught it.

What this is not yet: the 40-layer model on a device with room (the serving
processes own the memory), prompt-side prefill (tokens are fed one at a time),
sampling other than argmax, distribution parity with llama.cpp over a real
prompt, and the per-backend kernel layouts (Xavier).
## Tick 37 (2026-09-20, C-3-2): the HTTP shell — `serve_http.cljk`

The serving surface is a kbb script (`node /opt/kbb-engine/cli.js serve_http.cljk ...` on the box; the
kbb engine is `org-babashka-nbb` rsynced to `/opt/kbb-engine`, no kbb launcher there): `POST /v1/completions`
→ `tokenizer_core.cljk` (encode, loaded once with `nbb.core/load-file`; the CLI `gguf_tokenizer.cljk` now
loads the same core) → `kexe-loader-gpu` with `NEX_PROMPT=<ids>` + argv `<plen> <max_tokens>` (the runtime
guest of tick 36, WRITEDEC, amu #1035 merged this tick and the loader promoted on all three boxes,
previous kept as `kexe-loader-gpu.pre1035`) → parse `:result-utf8-hex`, split `#`-joined `ns|x|id` parts,
take the argmax after the last prompt token and each generated one → decode → OpenAI-shaped JSON with
`token_ids`, `usage`, `timing`. One process per request; greedy only.

Two things node 18 (the boxes) would not run: destructuring `def` (kbb/sci wants `(def a ..)` per name)
and the qwen2 pre-tokenizer's `(?i:'s|...)` inline modifier (V8 12.5+) — spelled out case by case in
`tokenizer_core.cljk`; `tokenizer_check.cljk` still 12/12 against llama-server after the change.

K16, `rt12.bin` (12 layers, runtime prompt): `curl -d '{"prompt":"The capital of France is","max_tokens":8}'`
→ ids `128186,116769,166224,2752,2752,132819,176133,4032`, 27.0 ms/token on the 13 steps, HTTP wall
3.8–5.2 s over 3 runs; the bare loader run is 3.95 s (3 runs: 3.92–3.97) of which the 13 token steps are
0.35 s — **the other 3.6 s is process start + MAP of the 12 layers + pipeline creation, paid per request.**
That is the cost the resident form (guest loops over requests, weights mapped once) removes, and it is the
next item. The 12-layer text is not meant to read (a 12-layer prefix is not the model); the check is the id
list against the f64 oracle (`decode_tokens_ref.py nex.gguf 760,6511,314,9338,369 12 13`) — the oracle's steps 4–11 are `128186,116769,166224,2752,2752,132819,176133,4032`: 8/8 exact through
the whole HTTP → tokenizer → kexe → detokenize path (prompt steps 0–3 are forced, so 5 prompt + 8 generated = 13 steps).

## Tick 38 (2026-09-20, C-3-3): the resident guest — weights mapped once, one message per token step

`… <backend> fn - resident` (generator) emits a guest whose `main` runs the constant phase (MAP, ALLOC,
PIPELINE) once and then `serve-loop`: `:io/read "64"` (wire 41, the pipe's atomic write) → one message
`"<token id>,<reset flag>"` → `WRITEDEC` into a 16-byte control buffer → the token step's command buffer,
now opened by the `ctl` op (`nex_ops.comp`: flag ≠ 0 rewinds `pos` to 0, then `tokbuf[pos] = token`) →
`SUBMIT` → `READ` the argmax → `:io/write` `"<ns>|<hex id>\n"` + an empty `:io/write-error` (the loader
buffers standard output 64 KiB and flushes it before any diagnostic write — the first run hung in `read(0)`
with the reply sitting in that buffer) → recur until EOF. Policy `policy_resident.edn` (wires 42 33 41 37 39).
No state is zeroed on a reset: `deltanet_fused.comp` reads the ring and S as zero when `pos[0] == 0`
(`fresh`), `attn_decode` reads `T = pos + 1` entries, `copy_at` rewrites the cache at `pos` — position 0
has no history by definition, so the rewind is the whole reset. `argmax_final`'s prompt-length meta is
4096 in this mode (the shell is the token buffer's only writer).

`serve_http.cljk` is now this guest's shell: spawns it once (`KEXE_STRING_POOL` 1 GiB, `KEXE_PAIRS` 2^26,
`KEXE_WALL_SECONDS` 86400 — the loader's ceilings; larger values are refused at start), serializes
requests, feeds the prompt (flag 1 on the first token) then each argmax back, respawns after
`steps-per-life` (15000) steps or on exit. The pool and pair heap are bump allocators: measured 11.3 KiB
and 3.5 K pairs per 12-layer step (120 steps: 1,360,741 B / 420,849 pairs), so 2^26 pairs is ~19 k steps.

Measured, 12 layers, prompt 760,6511,314,9338,369 + 8 greedy (`resident_drive.py`, 3 requests each box):

| box | GPU ms/token (SUBMIT ns) | wall per 12-step request | first request (MAP + steps) | ids |
|---|---|---|---|---|
| K16 radv | 27.1 | 0.374 s | 1.69 s | oracle 8/8, ×10 identical |
| B70 anv (int8) | 4.97 | 0.112 s | 2.00 s | oracle 8/8 |
| Xavier nvgpu (h2) | 37.2 | 0.669 s | 2.99 s | oracle 8/8 |

HTTP on K16 (`curl … max_tokens 8`, 5 runs): **wall 381–395 ms, was 3.8–5.2 s in tick 37**; the same 8 ids.
`resident_mix.py` alternates the two oracle prompts (5-token/8 and 3-token/2) on one guest: **6/6** equal
to the single-prompt oracle — the rewind leaks nothing across requests of different lengths.

**The number that fell out**: wall per step minus GPU ns = host cost per step, and it is one round trip
per `gpu` request (12 layers = 291 requests per step: 22 per recurrent layer, 27 per attention, 12 in the
loop): K16 4.1 ms (14 µs/request), B70 4.4 ms (15 µs), Xavier 18.6 ms (64 µs). Every earlier "ms/token"
in this README is the SUBMIT ns — GPU time — so the served rate is lower than those tables say: Xavier
40 layers ≈ 942 requests ≈ 60 ms on top of 86.9 ms GPU (≈ 6.8 tok/s served, not 11.5); B70 40 layers
≈ 14 ms on top of the ~10 ms GPU estimate. The broker pipe round trip and the Vulkan recording per
dispatch are not separated yet. Since fn mode made every step's dispatches identical (device-side pos
and token), the whole step is ONE reusable command buffer: record once, replay per step — a loader
request (`BEGIN keep` / `REPLAY`) that turns 291–942 round trips into 1. That is the next item.

## Tick 39 (2026-09-20, B / C-3-4): the step as one kept command buffer — `resident-replay`

The loader (amu #1036, `kexe-loader-gpu6` on the boxes until merged) gains kept command buffers:
`BEGINK <slot>` records a replayable buffer, `SUBMIT` submits it once and keeps it, `REPLAY <slot>`
submits it again, `DROP <slot>` frees it; `FREE` of a buffer a kept buffer binds is refused by name.
`… fn - resident-replay` uses it: `record-step` records the token step once (`BEGINK 0` … `SUBMIT`: one
warm-up step on zero state that the first request's rewind discards), and `serve-loop` is 4 `gpu`
requests per step — `WRITEDEC` ctrl, `REPLAY 0`, `READ` argmax, plus the two io writes — instead of 291.

Measured (12 layers, France prompt + 8, `resident_drive.py`, 3 requests; GPU ns unchanged, ids oracle 8/8
on every box, `resident_mix.py` 6/6 on K16):

| box | GPU ms/token | wall / 12 steps | host per step, tick 38 → now | guest pool + pairs per step |
|---|---|---|---|---|
| K16 radv | 27.1 | 0.374 → **0.340 s** | 4.1 → **1.2 ms** | 11.3 KiB / 3.5 K → 0.42 KiB / 142 |
| B70 anv | 4.97 | 0.112 → **0.064 s** | 4.4 → **0.36 ms** | same |
| Xavier nvgpu | 37.5 | 0.669 → **0.462 s** | 18.6 → **1.0 ms** | same |

HTTP on K16 (`curl … max_tokens 8`, 5 runs): **0.331–0.354 s** (tick 38: 0.381–0.395). The remaining
host cost per step is the 4 round trips + the `READ` (its own copy command buffer + fence) + the pipe;
the guest's life is no longer bounded by its allocators in practice (2^26 pairs / 142 ≈ 470 k steps).
For the served rate this is the correction of tick 38's correction: Xavier 40 layers ≈ 87 ms GPU + ~3 ms
host, B70 40 layers ≈ 10 ms GPU + ~1 ms.

## Tick 40 (2026-09-20, A / C-3-5): the 40-layer model served natively on Xavier — chat included

`… 40 4 9707 /root/kgpu … nvgpu fn - resident-replay` (1123 constant requests + the step; kept command buffer of
~940 dispatches) on Xavier with `kexe-loader-gpu` (= #1036): the France prompt + 8 greedy →
`11751,13,248046,198,248068,271,248069,271` = the 40-layer f64 oracle (`decode_tokens_ref40-12.npz`) 8/8,
**85.5–86.2 ms/token GPU, 1.04 s wall per 12 steps (86.7 ms/step → 11.5 tok/s served)**, first request 13.1 s
(the 18.7 GB MAP). Text: " Paris.<|im_end|>…" — llama-server (K16 :8097) continues " Paris.\n\nThe capital of
France is": after "." it has "\n\n" 0.128 vs `<|im_end|>` 0.120 (its own top_logprobs), a near-tie the f64 oracle
resolves our way. Not a bug to chase; it is what KL 0.014 looks like at an argmax.

The tokenizer now matches control / user-defined tokens (`token_type` 3 and 4: `<|im_start|>` `<|im_end|>`
`<think>` `</think>` …) verbatim before the pre-tokenizer, longest first, like llama.cpp's `parse_special`:
the ChatML prefix tokenizes identically to llama-server's `/tokenize` (13/13 ids); the corpus stays 12/12.
`serve_http.cljk` gained `POST /v1/chat/completions` (the template as `/apply-template` renders it for this
GGUF, checked on two message shapes; `reasoning_content` split at `</think>`) and stops at `<|im_end|>` /
`<|endoftext|>` (`finish_reason "stop"`). Xavier, 40 layers, chat "What is the capital of France? Answer in
one word." → `"Paris"`, stop, 21 prompt + 4 generated, 2.26 s (llama-server: "Paris", 5 tokens). A haiku
request: 200 tokens with reasoning, coherent, 216 steps in 19.0 s = **88.2 ms/step wall, 11.3 tok/s**.

The surface is a systemd unit on Xavier, `murakumo-xavier-nex-native.service` (:8091, node 18 + the kbb
engine at `/opt/kbb-engine`, `steps-per-life` 400000), enabled. It is NOT yet the gateway head (:8090 of the
stopped llama-server unit): the shell has no `stream: true` (SSE) and prompt tokens are still fed one step
each (21 prompt tokens = 1.8 s of the 2.26 s above) — the prefill mode of tick 33 has to enter the resident
protocol first. Those two are the next items; B70's 40 layers still wait on the vLLM 27 GB decision.

## Tick 41 (2026-09-20, A / C-3-6): streaming, and Xavier's native surface takes the gateway's fallback head

`serve_http.cljk` `stream: true`: SSE, one `data:` chunk per generated token as the guest returns it — text
through `TextDecoder {stream: true}` over `token-bytes` (a token can end inside a UTF-8 sequence; 日本の首都は →
「東京」 arrived whole), chat as `delta.reasoning_content` until `</think>` then `delta.content` (the template's
newlines after the think block dropped), a final chunk with `finish_reason` + `usage` + `timing`, `data: [DONE]`.
Also `GET /health`, `/slots` (llama-server's shape, one slot, `is_processing` while a step is in flight),
`/v1/models`; OpenAI content-parts arrays (text joined; an `image_url` part is refused with 400 — no vision on
the native path, the mmproj stays with llama.cpp); a thrown refusal answers 400 instead of ending the server.

**The gateway's Xavier head is now this surface.** cloud-murakumo-api `src/xavier_hosted_model.js` routes
`nex-n2.5-mini-uncensored` to heads in order 6600hs1 (B70 vLLM, 64 slots) → xavier (`192.168.1.28:8090`,
1 slot, taken when the primary is unreachable) → k16 (:8097 llama-server). Xavier's llama-server unit has been
stopped since tick 36 (owner: 「xavier の serving を止めて ok」), so :8090 was dead; `murakumo-xavier-nex-native.service`
now listens there (moved from :8091). Through the gateway the model answered `system_fingerprint: vllm-0.29.0`
both times — the primary is up and takes the traffic, as designed; the native head is the fallback, reachable
and answering `/health` `/slots` `/v1/models` locally. Not exercised via the gateway this tick (that would mean
taking the primary down). Note for the gateway repo: `worker.cljk`'s `probe-xavier` still expects model id
`murakumo-main` / alias `qwen3.8-27b` / 27.3 B params — stale since Xavier moved to Nex, independent of this work.

**Prefill on Xavier, measured before building it into the resident protocol**: a 40-layer `prefill` guest does
not compile (`module string literals exceed UTF-8 byte limit` — prefill mode is still the literal program; it
needs fn mode's functions). 12 layers, the 5-token France prompt, Xavier: **174 ms batched vs 5 × 36.6 =
183 ms decode — 5 % faster**, where K16 got 2.6× (84.5 vs 217 ms for 8 tokens). Xavier is instruction-bound and
`kdot_f32_p` is f32: the batched kdot saves weight reads Xavier was never short of. Also found: Xavier's
`kdot_h2_r1.spv` / `kdot_h2q6_r1.spv` predated the `pad1` row offset (built 23:56, source changed 00:36) — the
prefill's lm_head read row 0 (argmax 163967 = the prompt's first step) until the rebuild; then 128186 = oracle,
rows `x rel` ≤ 2.2e-3 (h2 experts). Decode re-checked after the rebuild (36.6 ms/token, 8/8). Conclusion for
the next item: on Xavier a resident prefill needs an h2 positions-inner-loop kdot before it is worth its
complexity; on B70 / K16 the f32 one already pays.

## Tick 42 (2026-09-20, C-1 / C-3-7): prefill as a fn-mode program — 40 layers compile; measured on three boxes

`… <backend> prefill` is now the FUNCTION program (the literal one is `prefill-flat`): the layer functions run
`PF` rows; a recurrent layer seeds its stepbuf from the position (`pos_seed`: `[pos, 0]`, handle = `S + (SB0 − S0)`
since states and stepbufs both run one per recurrent layer — the 5-parameter ABI has no room for a sixth) and
runs its P delta-net steps; the step ends with `pos_add PF`; the dyn `copy_at` meta covers `512 · PF` (the
first fn-mode run had rows 1–4 at `x rel` 8–12 with row 0 exact — only row 0 of K/V reached the cache).
The embed already read `pos + row`. The 40-layer guest is 66 KB of source (1155 constant requests) and compiles.

12 layers, the 5-token France prompt, rows vs the f64 oracle and the last row's argmax (3 runs each):

| box | prefill (one command buffer) | decode 5 steps | ratio | rows | argmax |
|---|---|---|---|---|---|
| K16 radv | **67.3–68.1 ms** | 5 × 27.1 = 135 ms | **2.0×** | `x rel` ≤ 1.3e-5 | 128186 = oracle |
| B70 anv | **10.3 ms** | 5 × 5.0 = 25 ms | **2.4×** | ≤ 2.7e-5 | 128186 = oracle (after the rebuild below) |
| Xavier nvgpu | 174.4 ms | 5 × 36.6 = 183 ms | 1.05× | ≤ 2.2e-3 | 128186 = oracle |

**40 layers on Xavier**: 545–558 ms for 5 tokens vs 5 × 86 = 430 ms decode — **1.27× slower than decode**;
rows `x rel` ≤ 1.35e-2 (the h2 experts, 40 layers deep), argmax 11751 = the 40-layer oracle. Same conclusion as
tick 41 with the sign now negative: on Xavier the f32 positions-inner-loop kdot loses to the h2 decode kernels
it replaces. The next item is the h2 twin of `kdot_f32_p` (`-DHALF`: f16x2 dequant and activations, HFMA2 on
Volta); until then the Xavier shell must keep feeding prompts one step at a time.

**Stale kernels, second time.** B70's `kdot_x8r4.spv` / `kdot_f32_r1.spv` / `kdot_f32_r8.spv` / `kdot_i8_*` were
built between the two prefill commits (they had `pad0`, not `pad1`), so the prefill's lm_head read row 0
(argmax 163967) while every row was right. Rebuilt all seven from the current sources (glslang 16.6 for the
int8 pair, `--target-env vulkan1.3`); decode re-checked 5.06 ms/token 8/8. The rule that follows: a kernel's
`.spv` on a box is stale whenever its mtime precedes the source's last commit — check that before reading a
mismatch as a bug (twice now: Xavier tick 41, B70 tick 42). `nex_pos_add.spv` / `nex_pos_seed.spv` built on all
three boxes.

## Tick 43 (2026-09-20, C-1 / kernel): the prefill kdot's positions in registers — Xavier 545 → 292 ms

`kdot_f32_p.comp` kept `acc[MAXP]` / `mins[MAXP]` indexed by a runtime-bounded loop; on NVIDIA that is LOCAL
MEMORY (the trap the kernel's own q6 comment names). `-DPFIX=<P>` makes the position count a compile-time
constant (`kdot_f32_p<P>.spv`, P = 4 5 8 16 built on the three boxes; a mismatched `positions` writes a NaN
instead of a wrong number), and the activation is one `vec4` load per position per block instead of four
scalars. The generator's prefill mode names `kdot_f32_p<PF>.spv`.

| | before (tick 42) | constant P | + vec4 loads | vs decode |
|---|---|---|---|---|
| Xavier 12 L, 5 tokens | 174.4 ms | 106.3 | **99.5 ms** | 183 ms → **1.84×** |
| Xavier 40 L, 5 tokens | 545 ms | 317 | **292–308 ms** | 430 ms → **1.4–1.47×** |
| K16 12 L | 67.3 | — | 63.2–65.8 | 135 → 2.1× |
| B70 12 L | 10.3 | — | 9.69 | 25 → 2.6× |

Rows unchanged (Xavier 40 L `x rel` ≤ 1.35e-2, K16 ≤ 1.3e-5, B70 ≤ 2.7e-5), argmax = oracle everywhere. The
NVIDIA compiler was the one that needed the constant; RADV/ANV already kept the arrays in registers (4–6 %).

**`-DHALF` measured and not adopted**: the packed-f16 products (kdot_h2_r1's form) on top of constant P gave
Xavier 12 L 99.5 → 99.5 ms (nothing) and 40 L 317 → 296 ms (7 %) while the rows moved to `x rel` 3.7e-3 (12 L)
and **0.115 (40 L)** — the f16 rounding compounds through 40 layers of P-row activations. The kernel was
never issue-bound the way the decode h2 kernel is; it was spilling. The `HALF` arm stays in the source as the
measured negative (not built).

Xavier's 40-layer prefill is now 1.4× decode, so the prompt half of a chat request (21 tokens = 1.8 s fed
one step each) can drop toward ~1.3 s with batched prefill once it is in the resident protocol — which is the
next item, for all three boxes.

## Tick 44 (2026-09-20, C-1 / C-3-8): prefill in the resident protocol — the prompt as P-token steps

`… fn - resident-replay prefill:<P>`: the guest records TWO kept command buffers — 0 the decode step, 1 a
prefill step of P rows — and its `serve-loop` tells the message kinds apart by the one parse it has,
`WRITEDEC`'s word count: `"t,f"` (2 words) → `REPLAY 0`, `"t0,…,tP-1,f"` (P+1 words) → `REPLAY 1`. `ctl` now
takes `P.n` tokens (`tokbuf[pos+i] = c[i]`, flag at `c[n]`; decode's meta has n = 1, so it is unchanged). To
emit both, the generator's batch-dependent state became a PHASE: `PF`, `prefill?`, the kdot-p pipeline and
the 19 metas that depend on the batch are dynamic vars bound by `with-phase`; every activation buffer is sized
by `PMAX`; the layer bodies are emitted twice (`recurrent-layer-p` / `attention-layer-p` / `layers-p`). The
legacy modes regenerate to the same programs (K16 replay 0.340 s, standalone prefill 61.6 ms, both oracle).
`serve_http.cljk` takes `prefill-bucket` (arg 8) and feeds the prompt as chunks of P then single tokens;
`resident_drive.py` / `resident_mix.py` take the bucket as their last argument.

The bug the refactor exposed: `shlogit` (the shared-expert gate logit, one float per row) was still
`max(16, 4·PF)` bytes with the emission-time PF = 1 — 16 bytes, room for 4 rows — so P = 4 was exact and P = 8
read past the buffer (K16 `40923,56380` for the oracle's `4032,268`; the debug reply showed the tokens and
the position landing correctly, which pointed at the compute, and a handle-by-handle comparison of the
resident and standalone P = 8 programs found the one allocation that differed). Sized by PMAX now; the
grep `alloc!.*\bPF\b` is empty.

Measured (ids = oracle in every row; "steps" = messages):

| box, guest | prompt | chunked | decode only |
|---|---|---|---|
| K16 12 L, P = 4 | France 5 + 8 | 9 steps, 270 ms GPU, **0.281 s** | 12 steps, 326 ms, 0.339 s |
| K16 12 L, P = 4 | 12-token oracle prompt + 2 | 4 steps, 184 ms, **0.189 s** | 13 steps, 355 ms, 0.371 s |
| K16 12 L, P = 8 | 12-token + 2 | 6 steps, 219 ms, **0.225 s** | 13 steps, 355 ms |
| B70 12 L, P = 4 | France 5 + 8 | 9 steps, 49.1 ms, **0.052 s** | 12 steps, 60.7 ms, 0.065 s |
| Xavier 40 L, P = 8 | 12-token 40-L oracle prompt + 2 | 6 steps, 871 ms, **0.877 s** | 13 steps, 1143 ms, 1.157 s |

Mixed prompts with the bucket (K16, P = 4): 6/6. On a garbage prompt (`…,1,2,3,4`) the chunked and
decode-only Xavier runs agree for 6 generated tokens and then diverge — the prefill kdot is f32 where decode
is h2 (rows `x rel` ≤ 1.35e-2 at 40 L), so near-ties fall differently; on the oracle prompt they agree.

**Xavier's unit now runs `rp40-nv.bin` with `prefill-bucket 8`** (:8090): chat "What is the capital of France?
Answer in one word." (21 prompt tokens = 2 chunks + 5) → `"Paris"`, 11 steps, **1.65–1.70 s (tick 40: 2.26 s)**;
the haiku (17 tokens) 163 steps in 15.0 s. Prompt cost per token on Xavier is now ~292/8 ≈ 37 ms in the
chunks against 86 ms per decode step; a longer bucket (16) would take it further for long prompts.

## Tick 45 (2026-09-20, C-3-9): sampling in the resident protocol — temperature / top_p / seed per request

Every `resident-replay` guest now records a THIRD kept command buffer (2): the decode step with the
`nex_sample_*` chain (tick 19) in place of argmax, preceded by a `params` op that copies words 2..4 of the
control buffer into the sampler meta's `eps / scale / p0` (T, top_p, seed). The message is
`"t,f,Tbits,top_p_bits,seed"` — 5 words — so `serve-loop` routes by `WRITEDEC`'s count: 2 → `REPLAY 0`
(greedy), 5 → `REPLAY 2` (sampled), else → `REPLAY 1` (prefill; the generator refuses `prefill:4` and `:1`,
whose P+1 would collide). The draw is `u = hash(seed, position)` as before, so `decode_tokens_ref.py
--sample T top_p seed` is the oracle for any (T, top_p, seed).

K16 12 L, France prompt + 8, T 0.7 / top_p 0.9 / seed 42: the guest answers **80072, 80072, 35222, 35533,
143898, 131822, 194349, 157676 — the f64 oracle's eight picks, 8/8**, across 3 requests; greedy on the same
guest still 8/8; the sampled step costs 335 vs 326 ms per 12 steps (+0.75 ms/token). B70 12 L: greedy 8/8;
sampled 80072, 80072 then diverges (33546 …) — the int8 anv path's logits differ at KL 0.0054 and the draw
falls on the other side of a boundary; expected, the f32 path reproduces the oracle exactly.

`serve_http.cljk`: `temperature` (default 1.0; 0 = greedy), `top_p` (default 1.0), `seed` (default a fresh
random u32, echoed in the answer with `temperature` and `top_p`); the last prompt token and every generated
token ride the 5-word message, so a prefill chunk is taken only while strictly more than P prompt tokens
remain (the reply of the last prompt message is the first pick). Over HTTP on K16: T 0 → the greedy ids;
T 0.7 / 0.9 / seed 42 twice → the oracle's eight, identical; no seed → a different sequence with the seed
reported. `resident_drive.py` takes `T top_p seed` as its last three arguments.

**Xavier's head (:8090) runs the sampling guest** (`rs40-nv.bin`, 40 layers, P = 8): T 0 → `"Paris"` in 1.67 s
as before; the haiku at T 0.7 / top_p 0.9: seed 7 → a finished haiku in 22 tokens (2.9 s), seed 8 → 120
tokens of reasoning about syllables (11.5 s) — sampled steps cost ≈ 90–95 ms against 86 greedy. When the
120-token cap lands inside the think block, the whole text comes back as `content` (there was no `</think>`
to split on) — same as a truncated llama-server answer, noted.

## Tick 46 (2026-09-20, C-4): batching — B independent sequences in one step

`… resident-replay prefill:<P> batch:<B>` records kept command buffer 3, a decode step of B rows where the
rows are SEQUENCES: each has its own absolute position (`rowpos[row]`), token-buffer row (stride 4096), KV
cache slice (`row × 4096 × 512`), delta-net ring and state (`row × their single-sequence size`). Kernel twins
under `-DBATCH` (`nex_<op>_b.spv` for copy_at / rope_neox / attn_decode / argmax_partial / argmax_final /
pos_incr / ctl, `deltanet_fused_b.spv`, `embed_iq4xs_b.spv`): row = workgroup y, position from `pos[row]`,
per-row offsets; the B-row kdots are the prefill phase's (`kdot_f32_p<B>`, MoE experts with `8B` positions),
the lm_head runs `positions = B`, argmax keeps 64 slots per row (the pick at slot 61). The message is
`B tokens, B flags` (2B words: flag = rewind that row), so 2B ∉ {2, 5, P+1}; the reply is every row's 64 slots.
Buffers grow by NSEQ = B (rings, states, caches, token buffer, logits, argmax partials). `batch_drive.py` runs
B prompts with their own budgets; an idle row is fed token 0 with flag 1.

**Correct on all three boxes**: K16 B=2 (France + 8 and Hello + 2) both rows = their single-sequence oracle;
K16 B=4 with the two prompts duplicated → the duplicates produce identical sequences and all four match
(4/4); B70 B=2 2/2; Xavier B=2 2/2 and B=4 4/4 (the two continued Hello rows agree across boxes).

**Throughput, 12 layers, GPU ms per step** (the batch step's kdots are the f32 positions-inner-loop kernel, not
each backend's tuned decode layout — that is what the numbers say):

| box | single decode step | batch step B=1 | B=2 | B=4 | seq-tokens/s: single → B=2 → B=4 |
|---|---|---|---|---|---|
| K16 radv | 27.1 ms | 48.5 | 49.2 | 84.3 | 36.9 → 40.7 → 47.4 (+10 %, +29 %) |
| B70 anv (int8 decode) | 5.0 | 7.83 | 7.84 | — | 200 → 255 (+28 %) |
| Xavier nvgpu (h2 decode) | 36.6 | 77.7 | 77.4 | 135.3 | 27.3 → 25.8 → 29.6 (−5 %, +8 %) |

The batch step at B=1 is 1.6–2.1× a decode step: `kdot_f32_p` (one row per workgroup, f32) is what the batch
phase can use today, and it loses to the r8 / int8 / h2 decode layouts it replaces; B=2 costs the same as B=1
(weights read once), B=4 about 1.7×. So the mechanism is right and the kernel is the lever: a batch-aware kdot
per backend (positions inner loop on the r8 / x8r4 / i8 / h2 layouts) would put B=2 near 1.0× a decode step and
the throughput near 2×. That, and the shell's scheduler (rows as slots), are the next items. Wall time in the
harness includes the warm-up before the first message and is not the served figure.

## Tick 47 (2026-09-20, C-4): where the batch step's time went — the lm_head read B times

Profiling by diffing the decode and batch layer functions kernel-by-kernel (`recurrent-layer` vs
`recurrent-layer-b`): the layers were equivalent per row; the difference was outside them. The batch step ran
the lm_head — 248320 × 2048 Q6_K, **425 MB**, the largest tensor in the step — with the positions DISPATCH
dimension (workgroup y = row), which reads it B times: on K16 (46 GB/s) that is 9.2 ms per extra row. Reading it
once through the positions kernel (`kdot_f32_p<B>`, rows as the inner loop, `:lm-once` in the layout table for
radv and nvgpu):

| box | B | before | after | seq-tokens/s vs single |
|---|---|---|---|---|
| K16 | 2 | 49.2 ms | **36.9 ms** | 54.2 / 36.9 = **1.47×** |
| K16 | 4 | 84.3 | **58.1** | 68.9 / 36.9 = **1.87×** |
| Xavier | 2 | 77.4 | **60.8** | 32.9 / 27.3 = 1.20× |
| Xavier | 4 | 135.3 | **88.9** | 45.0 / 27.3 = **1.65×** |
| B70 | 2 | 7.84 | 8.62 (worse) | kept the positions dispatch: 255 / 200 = 1.28× |

ANV is not bandwidth-bound on the lm_head; its int8 x8r4 read twice beats the f32 kernel read once, so the flag is
per backend. All rows oracle-exact throughout (K16 4/4, Xavier 2/2 and 4/4, B70 2/2).

Also tried: `kdot_f32_p` with `-DROWS=8` (the r8 shape with the positions inner loop, `kdot_f32_p<P>r8.spv`,
`NEX_PROWS` / layout `:prows`): K16 B=2 50.3 vs 49.2 ms for the layer kdots, and 46.0 vs 36.9 when it also
took the lm_head — the r1 shape wins on radv for this kernel; kept in the source as a measured negative, default
`:prows 1`. What remains between the B=1 batch step (36.8) and a decode step (27.1) on K16: the MoE expert kdots
at 8B positions (their weights differ per position, ~3 ms), the delta-net's per-row state traffic (~1.5 ms), and
the rest of the row-doubled ops. Those are per-row costs, so they scale with B and cap the gain — B=4 at 1.87×
is near what this shape gives on K16.

## Tick 48 (2026-09-20, C-4): the shell scheduler — rows as slots

`serve_http.cljk … <prefill-bucket> <batch-rows>`: with `batch-rows` B (a `… batch:<B>` guest) the shell is a
scheduler. B rows are slots; an arriving request waits in `pending` and takes a free row at the next tick with
its reset flag; every tick is ONE 2B-word message that advances every occupied row (an empty row gets `0,1`);
a row leaves on `<|im_end|>` / `<|endoftext|>` (`stop`) or its `max_tokens` (`length`), and its promise
resolves — streaming per row works through the same `on-token`. The batch step is greedy and one token per
row per step, so batch mode uses neither prefill chunks nor sampling (the single-row steps share row 0's state
with the batch step and cannot be interleaved). `load_check.py` fires N concurrent requests.

K16, 12 layers, `rb12lm4.bin` (B = 4), prompts of 5 / 1 tokens + 8 generated, vs the serial shell (`rs12s.bin`,
prefill bucket 8):

| N concurrent | serial shell | batch scheduler (B = 4) | ratio |
|---|---|---|---|
| 1 | 0.376 s, 34.6 seq-tokens/s | 0.661 s, 19.7 | 0.57× |
| 4 | 1.155 s, 38.1 | 0.762 s, **57.7** | **1.51×** |
| 8 | 2.327 s, 37.8 | 1.276 s, **69.0** | **1.83×** |

Xavier, 40 layers, `rb40-nv.bin` (B = 4) on :8090 with the head unit stopped for the measurement (the primary
vLLM head was up; the unit was restarted and answered `"Paris"` in 1.69 s afterwards): N=1 3.9 seq-tokens/s
(the France request stops at "Paris." after 7 tokens), N=4 **14.8**, N=8 **15.8** — against the serial head's
single stream of 11.5 tokens/s, 1.3–1.4×. The batch guest's step always computes B rows, so a lone request pays
the B-row step and loses the prefill chunks: the serving policy that follows is "serial shell under light load,
batch shell under heavy load", or an adaptive guest with kept buffers for B ∈ {1, 2, 4} — that is the next item.
Ids in batch mode equal the greedy single-row ids on every request checked.

## Tick 49 (2026-09-20, C-4): adaptive batch — one kept step per B, the scheduler pays for the rows it occupies

`… resident-replay - batch:1,2,4`: an ADAPTIVE guest records one batch step per B into kept buffers 0, 1, 2 (the
single-row decode / prefill / sampled steps are left out — they share row 0's memory with the batch rows and
cannot be interleaved), with layer bodies per B (`recurrent-layer-b1` / `-b2` / `-b`) and the same row layout
(`rowpos`, token rows, KV slices, per-row ring / state), so a B=1 step advances row 0 and a B=4 step rows 0–3 of
the same state. `serve_http.cljk … 0 1,2,4`: each tick takes the smallest B that covers the highest occupied
row (admission fills the lowest free row), the message is 2B words, the reply is read for B rows.

K16, 12 layers, `ra12.bin`, `load_check.py` (prompts of 5 / 1 tokens + 8 generated):

| N | serial shell (tick 48) | B=4-only scheduler (tick 48) | **adaptive {1,2,4}** |
|---|---|---|---|
| 1 | 0.376 s, 34.6 seq-tokens/s | 0.661 s, 19.7 | **0.392 s, 33.2** |
| 2 | — | — | **0.436 s, 50.5** |
| 4 | 1.155 s, 38.1 | 0.762 s, 57.7 | **0.742 s, 59.3** |
| 8 | 2.327 s, 37.8 | 1.276 s, 69.0 | 1.25–1.49 s, 59–71 (3 runs) |

The lone request is back to a single-row step (0.96× the serial shell; the 4 % is the missing prefill chunk),
N=2 is 1.5×, N=4–8 1.6–1.9×; ids unchanged. The N=8 spread is the K16 iGPU's clock (three consecutive runs),
not the scheduler. Not measured on Xavier this tick (the head would have to stop again; its B=4 figures are
tick 48's). What batch mode still lacks against the serial head: prefill chunks per row and sampling — both
are per-row variants of steps that exist; the batch step's message would carry them per row.

## Tick 50 (2026-09-20, C-4): per-row sampling in the batch step

The batch step now ends with the `nex_sample_*` chain over B rows (`-DBATCH`: row = workgroup y, per-row T /
top_p / seed from a params buffer, position from `rowpos`, logits / p_i at `row·n`, scratch at `row·256`, the
pick at slot 61 of the row) after the argmax; a row with **T = 0 keeps its argmax pick** (every sampler op
returns early for it), so greedy and sampled rows share one step. The batch message is 5B words — tokens,
flags, then (T, top_p, seed) per row — written by a batch `params` op into the params buffer; 2B-word messages
still route (no sampler words = all greedy). The adaptive guest holds the three steps as before.

K16 12 L, `ra12s.bin` (`batch:1,2,4`), over HTTP through the scheduler: T 0 → the greedy oracle ids; T 0.7 /
top_p 0.9 / seed 42 → `80072, 80072, 35222, 35533, 143898, 131822, 194349, 157676` = the sampled f64 oracle, twice;
**four concurrent requests mixing two greedy and two seeded-42 rows in one step: all four rows exact**
(0.76 s for the four). The sampler adds ~1 ms to a 12-layer step.

Xavier 40 L, `ra40-nv.bin` on :8090 with the head stopped for the run (restored after; "Paris" 1.68 s): greedy
France 7 tokens in 0.81 s (B=1 step ≈ 118 ms — the f32 positions kdot is 1.37× the h2 decode step on Xavier),
N=4 15.7 and N=8 16.3 seq-tokens/s vs the serial head's 11.5 single stream (1.4×); the seeded haiku (T 0.7,
seed 7) came back in 21 tokens / 4.3 s. **The serial guest stays the Xavier head**: on this box the batch
guest's single-request path is 1.4× slower (kernel, not protocol) and lacks prefill chunks; the adaptive guest
is ready for a bandwidth-bound box (K16) where its B=1 step equals a decode step. The two items that remain
for the head switch on Xavier: an h2 batch kdot (positions inner loop on the h2 layout) and per-row prefill.

## Tick 51 (2026-09-20, C-4): the B=1 batch step is the decode step — the kdot form per B

Each batch step's non-MoE kdots now take one of two forms by B (`:batch-layout-upto`, default 1, env
`NEX_BATCH_LAYOUT_UPTO`): up to that B the backend's DECODE kernels with the rows as the positions dispatch
dimension (weights read B times; for B = 1 this is the decode step itself, int8 / h2 / r8 included — the int8 and
dual forms are enabled for the B = 1 step), above it the positions kernel (weights once, rows inner). Measured
12 layers, adaptive guests `batch:1,2,4`, GPU ms/step, rows oracle-exact throughout:

| box | decode step | B=1 positions → **decode form** | B=2 positions / decode form | B=4 positions / decode form |
|---|---|---|---|---|
| K16 radv | 27.1 | 36.8 → **29.1** | **36.7** / 44.4 | **57.8** / 77.4 |
| B70 anv | 5.0 | 7.8 → **5.23** (int8) | **9.02** / 9.55 | **13.3** / 17.3 |
| Xavier nvgpu | 36.6 | 45.6 → **39.7** (h2) | 60.8 / 61.7 | **88.5** / 108.4 |

So the lone request in the adaptive guest costs 1.05–1.08× a decode step (the difference is the sampler chain
and the batch ops), and B ≥ 2 keeps the positions form on every box. Xavier 40 layers (`ra40-nv.bin`, head
swapped for the run and restored): greedy chat 25 steps in 2.27–2.31 s = 91 ms/step (the serial head's 86 ms
decode + ~5 ms sampler; its 1.65 s comes from the prefill chunks the batch step still lacks), N=4 15.9 and
N=8 **16.7 seq-tokens/s** vs 11.5. The serial guest stays the Xavier head until per-row prefill lands — the
one remaining gap. The h2 positions-inner-loop kernel that tick 50 named is not needed: at B = 1 the h2 decode
kernel is the right form, and at B ≥ 2 the f32 positions kernel already wins on Xavier.

## Tick 52 (2026-09-20, C-4): per-row prefill in the batch step — the adaptive guest takes the Xavier head

`… resident-replay prefill:<P> batch:1,2,4`: the adaptive guest records one more kept buffer, a BATCH PREFILL —
P positions of the ONE sequence the message names (`P tokens, row, flag, pad` = P+3 words; the generator refuses
a P whose P+3 collides with a 2B / 5B message). `-DBPREFILL` kernel twins add the sequence's slice offsets to the
prefill kernels: `ctl` writes the P tokens into the row's token buffer at its base, rewinds it on the flag, and
leaves `rowsel = [base, row]`; `embed` reads `tokbuf[row·4096 + base + i]`; `copy_at` / `attn_decode` address the
row's KV slice (`row · 4096 · 512`); `pos_seed` seeds each layer's stepbuf `[base, 0, row]` and `deltanet_fused`
offsets its ring and state by `pos[2]`; `pos_add` advances `rowpos[row]` by P. The prefill's argmax lands in
row 0's slot as before (the shell ignores it unless the prompt ends there — it never does: chunks are taken
only while more than P tokens remain). The scheduler runs a prefill tick for one such row before each batch tick.

Two things had to give for the 40-layer program to compile: the single-row functions are not emitted for
adaptive guests (never called there), and the 733 `MAP` literals no longer each carry the weight file's path
(`(M "off len")` through one helper) — 66.7 → 49.1 KB of the 64 KiB string budget.

K16 12 L (`rap12.bin`, `batch_drive.py --prefill 8`): a 12-token prompt row (one 8-chunk + 4 singles) next to a
3-token row → `4032, 268` and `169222, 169484`, both = oracle, 6 steps / 267 ms vs 13 steps / 476 ms without
chunks; the same with the long prompts in rows 1 and 3 of a 4-row batch → 4/4. Over HTTP through the scheduler
(`… 8 1,2,4`): a 19-token prompt alone in 338 ms (2 chunks + 3 singles + 3 generated), three of them plus a short
one concurrently in 1.04 s, identical ids.

**Xavier's head unit now runs `rap40-nv.bin` (`prefill:8 batch:1,2,4`)** — the previous unit file is kept as
`murakumo-xavier-nex-native.service.serial`. Against the serial head on the same requests: greedy chat 21 prompt
tokens → `"Paris"` in **1.70–1.74 s** (serial 1.65–1.70), the seeded haiku (T 0.7 / top_p 0.9 / seed 7) → the
**same three lines** in 22 tokens / 3.05 s (serial 2.9 s), load N=4 15.8 and N=8 **17.2 seq-tokens/s** (serial
11.5). No feature is lost: greedy, sampling with seed, streaming, chunked prefill, and now batching (1.5× at N=8).

## Tick 53 (2026-09-20, C-4): int8 in the batch step on anv; the pipeline table

The batch steps' int8 forms (anv's `kdot_i8_x8r4` for the wide kdots and the lm_head) now work for B rows: the
B rows' activations are quantized as ONE vector (`quant_q8` over `B·n` elements; the int8 kernels index the
per-32 scale by element, so contiguous rows need nothing else), the int8 lm_head dispatches `positions = B`,
and the int8 / dual forms are enabled for batch steps up to `:batch-layout-upto`. B70, 12 layers, adaptive
guests (`prefill:8 batch:1,2,4`), GPU ms/step, rows oracle-exact:

| `:batch-layout-upto` | B=1 | B=2 | B=4 |
|---|---|---|---|
| 1 (int8 only at B=1) | 5.21 | 8.95 | 13.32 |
| **2** (anv default now) | 5.21 | **8.65** | **13.24** |
| 4 (int8 layout everywhere) | 5.21 | 8.66 | 15.57 |

So anv takes the int8 decode form up to B = 2 and the positions form above; seq-tokens/s 200 (single) → 231
(B=2) → **302 (B=4, 1.51×)**. The 425 MB lm_head read twice at B = 2 in int8 beats the f32 positions kernel
reading it once — the item tick 47 left open closes as a measurement, not a new kernel.

The adaptive anv guest hit the loader's `pipeline table full` (64): 23 ops + 13 batch twins + 5 batch-prefill
twins + the kdot layouts with their int8 forms + a positions kernel per phase + three embed / delta-net variants
+ the quantizer ≈ 70. amu #1039 raises `KGPU_MAX_PIPELINES` to 128; built on the three boxes as `kexe-loader-gpu7`
(promoted to `kexe-loader-gpu` when the PR lands). K16 and Xavier were under the old limit by a few entries.

## Tick 53 (2026-09-20): Q8_0 / Q4_0 / F16 in the K-quant kdots — measured on K16 against the f64 oracle

`kdot_f32_r1.comp` / `kdot_f32_r8.comp` / `kdot_f32_p.comp` take three more ggml types: **Q8_0 (8)**, **Q4_0 (2)**,
**F16 (1)**. They are not super-blocks: Q8_0 is 32-value blocks of 34 B (f16 d + 32 int8), Q4_0 32-value blocks of
18 B (f16 d + 16 B of nibbles, value j < 16 the low nibble of byte j, j + 16 the high nibble, code q − 8), F16 has
no blocks. `block_bytes_of()` answers bytes per 256 values (272 / 144 / 512), so the 256-group loop and `wb` are the
same; the thread's block sits at `wb + (index / 32) * 34` (or 18). Rows are **not** 256-multiples in the target
model (Qwen2.5-0.5B: cols 896 = 28 blocks), so for these types the group count is `ceil(cols / 256)`,
`row_bytes = ceil(cols / 32) * 34` (18 / 64) and the tail group is masked (`block*256 + index >= cols` → skip; the
check never fires for K-quant, whose cols are 256-multiples). Block starts are 2-byte aligned, so the codes go
through `weight_u32_at` (q6's unaligned read); the F16 halves are two aligned words. `kdot_ref.py` has `deq_q8_0`
/ `deq_q4_0` / `deq_f16` (256-group, in `BLOCK`) built on 32-value `BLOCK32` units, and `row_geometry()` picks the
native unit per type; `gen_kdot_guest.cljk` knows the three types and a `p` layout (`kdot_f32_p1.spv`, built
`-DPFIX=1`); `kdot_check.py` takes any tensor name plus the byte count.

Oracle sanity before trusting a green: the byte rule reproduces every tensor's gap to the next directory entry in
all three GGUFs; the Q8_0 rows dequantize to within 0.0042 × block-max of the F16 rows of the same weights
(1/254 = 0.0039 is the quantization step; corr 0.99998), Q4_0 within 0.125 (corr 0.995); the old K-quant
`.ref.npy` files are reproduced bit-identical. `Qwen/Qwen2.5-0.5B-Instruct-GGUF` q8_0 / q4_0 / fp16 in
`/root/kgpu/models/` on K16 (sha256 = the HF LFS etags: `ca59ca7f…`, `7671c0c3…`, `8e0ae260…`).

K16 (RADV, `kexe-loader-gpu7`), first 64 rows, `max |gpu − f64| / max(|f64|, 1e-2)`, 10 dispatches in one buffer:

| type | tensor (rows × cols, bytes) | r1 | r8 | p (PFIX=1) |
|---|---|---|---|---|
| Q8_0 | `blk.0.attn_q` (896 × 896, 853 KB) | **9.40e-6** 18.7 GB/s | 9.40e-6 11.8 | 9.40e-6 12.7 |
| Q8_0 | `blk.0.attn_k` (128 × 896, 122 KB) | 1.21e-6 | 1.21e-6 | 1.21e-6 |
| Q8_0 | `blk.0.ffn_down` (896 × 4864, 4.6 MB) | 3.11e-6 14.4 | 3.11e-6 **24.0** | 3.11e-6 12.5 |
| Q4_0 | `blk.0.attn_q` (896 × 896, 452 KB) | **1.01e-5** 9.1 | 1.01e-5 8.5 | 1.01e-5 14.3 |
| Q4_0 | `blk.0.attn_k` (128 × 896, 65 KB) | 1.32e-6 | 1.32e-6 | 1.32e-6 |
| Q4_0 | `blk.0.ffn_down` (896 × 4864, 2.5 MB) | 3.33e-6 11.3 | 3.33e-6 11.1 | 3.33e-6 11.0 |
| F16 | `blk.0.attn_q` (896 × 896, 1.6 MB) | 9.91e-6 10.4 | 9.91e-6 11.3 | **1.59e-5** 21.8 |
| F16 | `blk.0.attn_k` (128 × 896, 229 KB) | 9.42e-6 | 9.42e-6 | 3.46e-6 |
| F16 | `blk.0.ffn_down` (896 × 4864, 8.7 MB) | 9.85e-6 15.2 | 9.85e-6 **31.9** | 2.59e-6 23.1 |

Every cell is ≤ 1.01e-5 except F16 attn_q on the p kernel, 1.59e-5: that is row 12, whose true dot is −0.010037
(at the metric's 1e-2 floor); the absolute error is 1.59e-7 against r1's 0.99e-7, the max absolute error over the
64 rows is 4.49e-7 for all three kernels, and numpy's own f32 `dot` of the same row is 1.81e-5 off the f64 value —
the f32 accumulation floor, not the layout (the p kernel rounds `dot()` before `ws *` where r1 fuses `dot()` into
the accumulator; at ws = 1.0 that is the only difference). Q4_0 has no stated bound; 1.01e-5 is the same metric.
The rebuilt `kdot_f32_r1.spv` / `kdot_f32_r8.spv` / `kdot_f32_p1.spv` on K16 re-ran the Nex K-quant guests:
Q5_K attn_qkv 6.10e-6, IQ4_XS attn_gate 9.98e-6, Q6_K lm_head 1.55e-6 on r1 / r8 / p (unchanged; the K-quant
arms were not touched). Small-tensor GB/s (attn_k) is launch-bound and not listed. Not measured: a row whose
block count is odd (the last block's unaligned word read straddles the row end by 2 B — inside the buffer except
at the tensor's last row), Q4_K (12, no Nex tensor and no oracle), and the other two boxes.
## Dense oracle (2026-09-20): `dense_ref.py` — an architecture-generic f64 reference for GGUF dense decoders

`decode_tokens_ref.py` is the f64 oracle of one model (Nex-N2.5-mini, shapes hardcoded). The next models are dense
decoder-only transformers, so **`dense_ref.py`** reads everything from the GGUF: `general.architecture` (`qwen2` |
`llama`, anything else is `REFUSE`, exit 2), `<arch>.block_count / embedding_length / attention.head_count /
head_count_kv / feed_forward_length / rope.freq_base / attention.layer_norm_rms_epsilon`, head dim from
`attention.key_length` / `value_length` when present else `embedding_length / head_count`, `rope.dimension_count`
(default head dim). Per block: RMSNorm → Q/K/V (+ qwen2's `attn_{q,k,v}.bias` when the tensors exist) → RoPE →
causal softmax GQA over a growing KV cache → `attn_output` → RMSNorm → SwiGLU (`ffn_down(silu(gate)·up)`); final
norm; lm_head = `output.weight`, or `token_embd.weight` when it is absent (tied, as in Llama-3.2-1B). RoPE follows
llama.cpp's `llama_rope_type`: **LLAMA → NORM** (interleaved pairs), **QWEN2 → NEOX** (half-split pairs);
`rope_freqs.weight` (the llama3 scaling factors convert_hf_to_gguf precomputes, 32 values for head dim 64) divides
θ per pair when present, as ggml's `freq_factors` do. CLI is `decode_tokens_ref.py`'s:
`python3 dense_ref.py <gguf> <prompt-ids> <layers> <steps>` → per-step argmax, `dense_ref.npz`
(`tokens / xs / argmaxes / logits / prompt`); generated tokens = steps − (prompt − 1). Dequant is vectorised and
local: F32, F16, Q4_0, Q4_1, Q5_0, Q5_1, Q8_0, Q4_K, Q5_K, Q6_K, IQ4_XS (the three K-quants and IQ4_XS follow
`kdot_ref.py`'s layouts). Weights are cached in f64 when the whole file fits `--cache-gb` (default 6), else
dequantised per use. `--rope norm|neox` overrides the arch's type — a negative control, see below.

**`dense_check.py <server-url> <npz>`** compares against a CPU-only llama-server: (a) the greedy continuation
(`POST /completion`, prompt as the oracle's id list so no BOS is added twice, `temperature 0`, `return_tokens`),
(b) the full distribution at the last prompt position (`n_probs = vocab` — llama-server b10883 returns all 151,936 /
128,256 entries, 14 MB of JSON). llama-server's f32 logprobs sum to 1 + 3…6e-4, which made KL(oracle‖llama) come
out negative on the first run; the check renormalises them and prints the raw mass. Exit 0 match / 1 mismatch /
2 could not compare (says why).

Measured on K16 (`/root/kgpu/dense`, python3 + numpy 1.26, 16 cores; llama-server = the Vulkan build
`build-vulkan/llama-b10883/llama-server` run with `--device none -ngl 0 -t 8` on port 8098 — zero "Vulkan" lines in
its logs; stopped after each model, none left). Prompt `"The capital of France is"` via `POST /tokenize`
(`add_special: true`); files in `/root/kgpu/models/`, sha256 of each in this commit's message.

| model (GGUF) | tensor types | prompt ids | oracle argmax per step | continuation (oracle = llama.cpp) | last-prompt top-1 | KL(llama‖oracle) / KL(oracle‖llama) | oracle wall |
|---|---|---|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct q8_0 (24 layers) | F32, Q8_0 | 785,6722,315,9625,374 | 2701, 315, 279, 374, **12095, 13, 1084, 374** | `12095 13 1084 374` = `" Paris. It is"` MATCH | 12095 = 12095 MATCH | 1.56e-3 / 1.54e-3 nats | 5.0 s (weights cached, 4.7 GiB f64) |
| Qwen2.5-0.5B-Instruct q4_k_m | F32, Q4_K, **Q5_0**, Q6_K, Q8_0 | same | 2701, 315, 279, 374, **12095, 13, 1084, 374** | same, MATCH | MATCH | 2.84e-3 / 2.85e-3 | 9.6 s |
| Qwen2.5-0.5B-Instruct q4_0 | F32, Q4_0, Q8_0 | same | 220, 315, 279, 374, **12095, 11, 323, 432** | `" Paris, and it"` MATCH | MATCH | 1.08e-3 / 1.09e-3 | 7.2 s |
| Qwen2.5-0.5B-Instruct fp16 | F16, F32 | same | 2701, 315, 279, 374, **12095, 13, 1084, 374** | `" Paris. It is"` MATCH | MATCH | **1.19e-5 / 1.19e-5** | 4.9 s |
| Llama-3.2-1B-Instruct Q8_0 (16 layers, tied lm_head, `rope_freqs.weight` 1…32) | F32, Q8_0 | 128000,791,6864,315,9822,374 | 16309, 2768, 315, 9822, 374, **12366, 13, 578, 469** | `12366 13 578 469` = `" Paris. The E"` MATCH | 12366 = 12366 MATCH | 4.21e-4 / 4.33e-4 | 57 s (1.24 B params = 9.2 GiB f64 > budget → dequant per step; peak RSS 4.5 GB) |

Two things the table taught: the "q4_k_m" file of a model whose n_embd (896) is not a multiple of 256 is mostly
**Q5_0**, not Q4_K — the first run refused on ggml type 6 and Q5_0/Q5_1/Q4_1 were added; and the residual KL on
every quantised file (1…3e-3 nats, max |Δlogprob| ≈ 0.5 in the tail) drops **two orders of magnitude on the fp16
file** (1.2e-5), which is consistent with llama.cpp's CPU kernels quantising the activations for Q8_0/Q4_0/Q4_K
dots while the oracle dequantises the same weights exactly — a plausible reading, not a measurement of those
kernels (their source is not on the box). Greedy ids and top-1 agree on all five files.

Negative controls (the check must fail for the reason it names): the Qwen npz against the Llama server →
`REFUSE llama-server returned 128256 logprobs, vocab is 151936` (exit 2, continuation MISMATCH at step 0); the Llama
oracle with `--rope neox` (wrong type) → continuation `12366 11 279 3363` vs `12366 13 578 469`, MISMATCH at step 1,
KL 0.97 / 1.27 nats (the top-1 at position 5 still matched — the position is too early for RoPE to move it, which is
why the check compares the continuation and the whole distribution, not top-1 alone).

Not done: no GPU guest consumes `dense_ref.npz` yet (the oracle lands ahead of the dense guests, as
`decode_tokens_ref.py` did for Nex); `.cljk` twins of the two Python oracles remain debt, as for `kdot_ref.py`.
## Tick 58 (2026-09-20): the tokenizer follows `tokenizer.ggml.pre`; chat templates per family

The serving shell's text side no longer assumes Nex. `tokenizer_core.cljk` reads `tokenizer.ggml.pre` and takes the
regex list llama.cpp applies for it (spelled from `src/llama-vocab.cpp` at 911f6cdc, the checkout under
`~/models/llama.cpp-src`, not from memory): `qwen2`, `qwen35` (Nex-N2.5's actual pre — the old hardcoded qwen2
regex passed only because the corpus had no combining marks; `\p{M}` joins letters in qwen35), `llama-bpe`
(`\p{N}{1,3}`, `ignore_merges`: a piece that is itself a token is emitted whole, `add_bos` default true), `gpt-2` and
`default` (four regexes applied in sequence). The split keeps the text between matches as pieces of its own, as
llama.cpp's `unicode_regex_split` does (that is why the gpt-2 regex may end in `\s+(?!\S)` with no `\s+`); user-defined
tokens (type 4, gpt-neox's `"  "` indentation tokens) are matched verbatim even with `parse_special = false`, control
tokens (type 3) only with it — `encode` is `parse_special = true`, `encode*` takes the flag. Unknown pre → `REFUSE`
exit 2 naming the known set; `tokenizer.ggml.model` ≠ `gpt2` (`llama` = SentencePiece, `bert`, `t5`, `gemma4`) → `REFUSE`
exit 2 (SPM is not implemented, it is refused, not approximated). The core also exposes `bos-id` / `eos-id` /
`add-bos?` (the GGUF's `add_bos_token`, else llama.cpp's per-pre default) / `chat-template` and `encode-prompt`
(bos first when `add-bos?`). `gguf_tokenizer.cljk … meta` prints them.

`chat_templates.cljk` (`load-file` after the core) recognizes the family of `tokenizer.chat_template` by distinctive
substrings — `<|start_header_id|>` llama3, `<start_of_turn>` gemma, `[INST]` mistral, `<|im_start|>` + `<think>`
chatml-think, `<|im_start|>` chatml — and renders each with a hand-written function (no jinja). chatml-think is the
Nex rendering of tick 45 unchanged (plus the `|trim` the template applies to every content); chatml carries Qwen2.5's
default system prompt, read from the template's `{%- else %}` literal; llama3 renders the system header with
`Cutting Knowledge Date` and `strftime_now("%d %b %Y")`, and like llama.cpp strips the template's leading bos string
so the tokenizer adds the bos id once. `serve_http.cljk` delegates `render-chat` to it, tokenizes prompts with
`encode-prompt`, and takes its stop ids from `eos_token_id` + the family's stop-token list (prints one
`TEMPLATE\t<family>\tpre …\tadd_bos …\teog […]` line at startup). **gemma and mistral are written from their published
templates and UNVERIFIED** — no GGUF of either was measured; they are not claimed to match.

Measured (K16, node 18, `/opt/kbb-engine`; llama-server b10883 CPU-only `-ngl 0` on 8093 / 8094 for the two new models
and the box's existing Nex server on 8097, both spare servers stopped afterwards):

| GGUF | pre | `tokenizer_check` (corpus 18 lines: + numbers, contractions, Japanese, code, SQL, marks) | `chat_template_check` vs `/apply-template` (single user; system+user+assistant+user; whitespace stress) | `encode-prompt` vs `/tokenize add_special=true` |
|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct-Q8_0 | qwen2 | **18/18** | chatml **3/3** | equal (35 ids, no bos) |
| Llama-3.2-1B-Instruct-Q8_0 | llama-bpe | **18/18** | llama3 **3/3** | equal (41 ids, `<|begin_of_text|>` first) |
| Nex-N2.5-mini IQ4_XS | qwen35 | **18/18** | chatml-think **3/3** | equal (15 ids) |

Control: the old core (qwen2 regex, no `ignore_merges`) against Llama-3.2 on the same corpus is 13/18 (5 MISMATCH), so
the check bites. llama.cpp's own oracle (`tokenizer_oracle.cljk` over `models/ggml-vocab-*.gguf.inp/.out`,
`add_special = false, parse_special = false`): qwen2 **46/46**, llama-bpe **46/46**, gpt-2 **46/46**, qwen35 **50/50**;
`default` has no shipped oracle, so `oracles/ggml-vocab-gpt-neox.gguf.{inp,out}` (62 texts) was produced with
`llama-tokenize` and is **62/62**. The oracle goes red for the reason named: `ignore_merges` off → 45/46 (`"Cửa Việt"`),
`\p{N}{1,3}` → `\p{N}` → 35/46. Not done: SentencePiece (refused), gemma / mistral measurement, a jinja engine (by design).
## Tick 54 (2026-09-20, HF coverage 1): the generator reads the architecture — Qwen2.5-0.5B and Llama-3.2-1B run

Owner direction: reach toward the model families on huggingface.co/models. Three subagents worked in parallel
(their sections above: the Q8_0 / Q4_0 / F16 kdot arms with 896-column tails, the dense f64 oracle `dense_ref.py` /
`dense_check.py`, and the tokenizer families + `chat_templates.cljk`), and the generator grew an architecture recipe:

- **Every dimension from the GGUF**: `general.architecture` (`qwen35moe` = Nex, `qwen2`, `llama`), `embedding_length`,
  `head_count`, `head_count_kv`, head dim (dense: NE / NH), `feed_forward_length`, `rope.dimension_count` (default
  the head dim), `rope.freq_base`, rms eps, vocab from `output.weight` (or the tied `token_embd.weight`), the lm_head /
  embedding tensor TYPES, argmax partials = ceil(vocab / 4096) (61 / 38 / 32) and the pick slot from it, tensor byte
  counts for F32 / F16 / Q8_0 / Q4_0. The box weight file is the GGUF's basename (or `NEX_BOX_GGUF`; Nex runs pass
  `nex.gguf`). Nex regenerates to the same program (byte-identical before the pipeline list grew; oracle-exact after).
- **A dense block** `emit-dense-layer!`: rmsnorm → q / k / v kdots (+ bias via `add_bias`, zero stand-ins when the
  model has none) → rope (`p0 = 1` NORM pairs for llama, NEOX otherwise; `rope_freqs.weight` as per-frequency divisors
  when present — llama3 scaling) → KV copy → `attn_decode` with `p0 = 1` (no output gate) → o → residual + rmsnorm →
  SwiGLU → residual. The resident / adaptive-batch / batch-prefill machinery is shared: `WSTRIDE` 12 handles per layer,
  every layer an attention layer, KV slot = `NKV · HD`. `embed_iq4xs.comp -DQ8` reads a Q8_0 embedding row.
- Two bugs found by reading intermediates (`NEX_DEBUG_BUFS=x,h,dq,…` appends named READs to a fn-mode answer): the rope
  base came from the Nex-only key (nil → NaN θ from the second element on), and the final norm ran over 2048 elements
  for an 896-wide row (argmax-invariant — the fn guest matched the oracle's argmax chain anyway — but distribution-wrong,
  and rows ≥ 1 of a batch read the wrong offset). Both are now dims.

Measured on K16 (RADV), f64 oracle = `dense_ref.py` (which itself matched llama.cpp's greedy continuation and full
distribution at KL 1.5e-3 / 4.2e-4 nats, see the oracle section):

| model | prompt | native ids | oracle | `x rel` | GPU ms/token |
|---|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct Q8_0, 24 L | 785,6722,315,9625,374 | 2701,315,279,374, **12095,13,1084,374**, 279 | 8/8 | ≤ 1.9e-6 | **16.0** |
| Llama-3.2-1B-Instruct Q8_0, 16 L | 128000,791,6864,315,9822,374 | 16309,2768,315,9822,374, **12366,13,578,469** | 9/9 | ≤ 1.1e-6 | **34.5** |

Adaptive guests (`prefill:8 batch:1,2,4`): Qwen prefill-chunked row + plain row both oracle-exact (`--parts 38`), B=4
four rows exact at 17.8 ms/step (≈ 225 sequence-tokens/s), B=1 16.0; Llama prefill + plain rows exact at 36.3 ms/step.
**Served over HTTP** (`serve_http.cljk`, template recognized from the GGUF): Qwen chat "What is the capital of France?
Answer in one word." → `"Paris"` (llama-server on the same GGUF: `"Paris"`), completion "The capital of France is" →
`" Paris. It is the largest city in"` = llama-server, 215 ms; Llama-3.2 → `"Paris"` / `" Paris. The Eiffel Tower is"`
= llama-server. The K16 shells stay up on :8100 (Qwen) and :8101 (Llama) beside the Nex one on :8099.

Not done: B70 / Xavier runs of the dense guests (the anv kernels took the Q8_0 / Q4_0 / F16 arms in tick 55 below;
the nvgpu h2 layout `kdot_h2_r1` still has none, so on Xavier a dense model would fall to the f32 kernels), Q4_K_M
mixes with Q5_0 (type 6: kdot arm missing), SentencePiece models (refused by name), the Xavier head shell not yet
updated to the new tokenizer core.

## Tick 55 (2026-09-20): Q8_0 / Q4_0 / F16 in the anv kernels — `kdot_x8r8.comp` and `kdot_i8_x8r4.comp`, measured on B70

The two Intel Arc (ANV) kernels take the three non-K-quant types the way tick 53 gave them to `kdot_f32_*`: `block_bytes_of()`
answers 272 / 144 / 512 per 256 values, `blocks = ceil(cols / 256)` and `row_bytes = ceil(cols / 32) * 34` (18 / 64) for
these types, the tail group is masked, codes go through `weight_u32_at` (block starts are 2-byte aligned). On the x8 lane
mapping a lane's eight values never straddle a 32-value block (index is a multiple of 8), so one `d`, one block and — in the
int8 kernel — one activation scale serve both words. `kdot_x8r8.comp` (`-DROWS=4` → `kdot_x8r4.spv`, the anv `:wide` / `:lm`
f32 layout) has `q8_0_word_values` / `q4_0_word_values` / `f16_values`. `kdot_i8_x8r4.comp` (glslang 16.6,
`--target-env vulkan1.3`) has **Q8_0 = the signed int8 code word straight into `dotPacked4x8EXT`** (no offset, no mins),
**Q4_0 = the nibble word dotted and the −8 folded as `8 * ysum`** (Q6_K's −32 pattern), and **F16 = an f32 fallback inside
the kernel**: the halves are dotted against the dequantized int8 activation `xq * sx` (`i8_values`), so type 1 is answered
(not NaN) and carries the activation's quantization error and nothing else. `gen_kdot_guest.cljk` gained the `x8r4` /
`x8r8` layouts (box files `kdot_x8r4.spv` / `kdot_x8r8.spv`). Two oracle additions: `kdot_ref.py` also writes
`<tensor>.refq.npy`, the same f64 dot against the activation `quant_q8` produces (per 32: scale = max|x| / 127, q =
round(x / scale)), and `kdot_check.py` prints the error against it when present — the column that tells an int8 kernel's own
error (f32 accumulation, ~1e-5) from the activation quantization (~1e-1 under the 1e-2-floored max-rel metric).

**The `continue` cliff.** The first build masked the tail with `continue` inside the block loop, as `kdot_f32_*` do. On anv that
cost the f32 x8r4 kernel **35% on Q5_K (190 → 123 GB/s)** with bit-identical outputs; a per-lane loop bound was the same
(121). Bisected at the pinned clock on `blk.0.attn_qkv` Q5_K, 3 runs each: each arm alone 182–186, all three arms with a
uniform loop and no mask 182, no arms with the per-lane bound 185 — so neither the arms nor the mask alone, but divergent
control flow around the full body. Written as an `if` around the body (`maskC`) it measures 183 and is what landed; the
branch-free form (masked lanes read block 0 with y = 0) was 181 and not needed. The int8 kernel barely moved on any form
(206–211 vs 213). For ROWS = 8 the loss is the arms themselves (no-mask all-arms 136, any single arm 145–148, none 148,
old 152) and stays; `x8r8` is not in the anv layout set.

B70 (Arc, ANV, `kexe-loader-gpu`), `min_freq` pinned to 2800 for the GB/s column (the box idled at 400 and a ten-dispatch
bench does not ramp it — tick 20; restored to 400 afterwards; a vLLM engine was resident on the GPU throughout), first 64
rows, 10 dispatches in one buffer. `f64` = `max |gpu − f64| / max(|f64|, 1e-2)`; `q8act` = the same against the
`quant_q8`-activation oracle. Qwen2.5-0.5B-Instruct GGUFs copied from K16 (sha256 = the HF etags `ca59ca7f…` /
`7671c0c3…` / `8e0ae260…`, `/root/kgpu/models/`):

| type | tensor (rows × cols) | x8r4 f64 | x8r4 GB/s | x8r8 f64 | x8r8 GB/s | i8x8r4 q8act | i8x8r4 f64 | i8 GB/s |
|---|---|---|---|---|---|---|---|---|
| Q8_0 | `blk.0.attn_q` (896 × 896) | 5.42e-6 | 47.7 | 5.42e-6 | 39.2 | **4.77e-6** | 2.10e-1 | 48.9 |
| Q8_0 | `blk.0.attn_k` (128 × 896) | 3.74e-6 | 7.4 | 3.74e-6 | 5.9 | 1.50e-6 | 2.23e-1 | 7.5 |
| Q8_0 | `blk.0.ffn_down` (896 × 4864) | **1.18e-6** | **207.3** | 1.18e-6 | 155.6 | 1.21e-6 | 7.33e-1 | **217.9** |
| Q4_0 | `blk.0.attn_q` (896 × 896) | 2.62e-6 | 24.1 | 2.62e-6 | 20.0 | 4.45e-6 | 1.72e-1 | 25.2 |
| Q4_0 | `blk.0.ffn_down` (896 × 4864) | **8.34e-6** | 101.5 | 8.34e-6 | 70.7 | **1.31e-5** | 7.38e-1 | 112.6 |
| F16 | `blk.0.attn_q` (896 × 896) | 6.11e-6 | 87.9 | 6.11e-6 | 72.6 | 2.60e-6 | 2.09e-1 | 92.0 |
| F16 | `blk.0.attn_k` (128 × 896) | 5.48e-6 | 13.2 | 5.48e-6 | 10.2 | 1.06e-6 | 3.36e-1 | 14.0 |
| Q5_K control | Nex `blk.0.attn_qkv` (8192 × 2048) | 6.64e-6 | 182.8 | 6.64e-6 | 135.6 | 1.38e-5 | 2.04e-1 | 207.3 |

Every f32 cell ≤ 8.34e-6; every int8 cell ≤ 1.31e-5 against the quantized-activation oracle, the same class as the Q5_K
control's 1.38e-5 (its `f64` column, 2.04e-1, is the int8 kernel's pre-existing gap — the same value from the pre-q80 spv).
The `f64` column of the int8 rows is the activation quantization: ffn_down's 7.3e-1 is a 4864-term dot on rows whose true
value sits near the metric's 1e-2 floor, not a kernel defect (its `q8act` is 1.2e-6). Small tensors (attn_k, 122 KB) are
launch-bound at ~0.16 ms per 10 dispatches. **The K-quant path is unchanged**: the Nex Q5_K guest's 64 output floats are
byte-identical between the `.pre-q80` spv and the landed spv on all three kernels, and the pinned A/B is old / new x8r4
189.6 / 182.5, x8r8 152.5 / 136.3, i8x8r4 210.9 / 207.5 GB/s (means of 3 runs each). B70's `kdot_x8r4.spv` / `kdot_x8r8.spv` /
`kdot_i8_x8r4.spv` are the landed sources (previous three kept as `*.spv.pre-q80`, sources as `*.comp.pre-q80`); no other
spv on the box was touched. Not measured: a row with an odd block count (the 2 B straddle at the tensor's last row; Qwen's
28 / 152 blocks are even), Q4_K (12), the dense Qwen / Llama guests end to end on B70 (they need `gen_decode_tokens_guest`'s
anv layouts to be exercised with Q8_0 — the next tick), and whether the 4% x8r4 residual is code size or the tail `if`.


## Tick 53b (2026-09-20): Q4_1 / Q5_0 / Q5_1 in the K-quant kdots — measured on K16 against the f64 oracle

The same three kernels (`kdot_f32_r1.comp` / `kdot_f32_r8.comp` / `kdot_f32_p.comp`) take **Q4_1 (3)**, **Q5_0 (6)**
and **Q5_1 (7)**, in tick 53's style: 32-value blocks of 20 / 22 / 24 B (ggml-common.h `block_q4_1` = f16 d, f16 m,
16 nibble bytes, value d·q + m; `block_q5_0` = f16 d, u32 qh, 16 nibble bytes, value d·(q − 16); `block_q5_1` = f16 d,
f16 m, u32 qh, 16 nibble bytes, value d·q + m), `block_bytes_of()` answering 160 / 176 / 192 per 256 values, group
count `ceil(cols / 256)` with the tail mask, `row_bytes = ceil(cols / 32) × 20 (22 / 24)`, codes through
`weight_u32_at` (Q5_0 blocks are only 2-aligned; Q4_1 / Q5_1 are 4-aligned and go through the same read). Nibble
order is Q4_0's (value j < 16 the low nibble of byte j, j + 16 the high nibble of byte j − 16); the 5th bit of value j
is bit j of the little-endian u32 qh (`dequantize_row_q5_0`: `xh_0 = (qh >> j) << 4`, `xh_1 = (qh >> (j + 12)) & 0x10`),
so a thread's four values take bits `within .. within + 3` in one shift. The m term is `m · Σy` per block, carried on the
K-quant `mins` path with the sign flipped (`mins -= m · Σy`; the p kernel sets `wm = −m`). `kdot_ref.py` has
`deq_q4_1_32` / `deq_q5_0_32` / `deq_q5_1_32` in `BLOCK32` (and the 8-block wrappers in `BLOCK`), and
`check_q5x_against_dense_ref()` asserts they agree **bit for bit** with `dense_ref.py`'s `deq_q4_1` / `deq_q5_0` /
`deq_q5_1` (the oracle that matched llama-server's greedy continuation and full distribution on the q4_k_m file, which
is mostly Q5_0) — `kdot_ref.py <gguf> <tensor>` runs it on the tensor's first row and prints the block count compared
(28 / 152 blocks on the tensors below; 0 is not a pass). Negative control on the oracle: swapping the qh bit halves
(bit j + 16 for the low nibbles) makes the check raise for type 6 with max |Δ| 14288. `kdot_ref.py <gguf>` with no
tensor now lists the directory and the type histogram. `gen_kdot_guest.cljk` knows the three types;
`gen_decode_tokens_guest.cljk`'s `tensor-bytes` has the 20 / 22 / 24 B cases (evaluated on the real definition text:
501760 / 551936 / 602112 B for the three 896 × 896 attn_q tensors and 3268608 for the Q5_1 ffn_down = `kdot_ref.py`'s
byte counts; the generator itself still `REFUSE`s the q4_k_m file earlier, at the Q5_0 `token_embd.weight` — embed
kernels are IQ4_XS / Q8_0 only — so that branch is verified by evaluation, not by a decode run).

Files on K16: `/root/kgpu/models/qwen2.5-0.5b-instruct-q4_k_m.gguf` (sha256 `74a4da8c…`; types {Q5_0: 133, F32: 121,
Q8_0: 13, Q6_K: 12, Q4_K: 12} — there is **no Q5_0 tensor with 4864 columns** in it, every `ffn_down` is Q6_K, so the
large Q5_0 tensor below is `ffn_gate` with 4864 *rows* × 896 cols), and `qwen2.5-0.5b-instruct-q4_1.gguf` /
`-q5_1.gguf` (sha256 `585c212d…` / `a7e67b71…`) produced on the box with `build-vulkan/llama-b10883/llama-quantize <fp16> <out> Q4_1|Q5_1` (2.1 s / 1.9 s;
169 tensors of type 3 / 7 each, `output.weight` stays Q8_0 — "1 of 291 tensor(s) required fallback quantization").
The byte rule reproduces every type-3/6/7 tensor's gap to the next directory entry (133 / 169 / 169, 0 mismatches).
Dequantized attn_q rows against the fp16 file's: Q4_1 within 0.067 × block-max (corr 0.9951), Q5_0 within 0.0625
(= 1/16, the +max side clamped to 15 by llama.cpp's quantizer; corr 0.9980), Q5_1 within 0.033 (corr 0.9989).

K16 (RADV, `kexe-loader-gpu`), first 64 rows, `max |gpu − f64| / max(|f64|, 1e-2)`, GB/s from 10 dispatches in one
buffer (small tensors are launch-bound, GB/s omitted):

| type | tensor (rows × cols, bytes) | r1 | r8 | p (PFIX=1) |
|---|---|---|---|---|
| Q5_0 | `blk.0.attn_q` (896 × 896, 552 KB) | 5.80e-6 9.3 | 5.80e-6 13.8 | 5.80e-6 15.1 |
| Q5_0 | `blk.0.attn_k` (128 × 896, 79 KB) | 8.71e-7 | 8.71e-7 | 8.71e-7 |
| Q5_0 | `blk.0.ffn_gate` (4864 × 896, 3.0 MB) | 5.68e-6 4.8 | 5.68e-6 13.3 | 5.68e-6 **22.6** |
| Q4_1 | `blk.0.attn_q` (896 × 896, 502 KB) | 5.20e-6 8.9 | 5.20e-6 17.7 | 5.20e-6 11.1 |
| Q4_1 | `blk.0.ffn_down` (896 × 4864, 2.7 MB) | 6.06e-6 16.5 | 6.06e-6 **20.0** | 6.06e-6 11.0 |
| Q5_1 | `blk.0.attn_q` (896 × 896, 602 KB) | 3.84e-6 16.6 | 3.84e-6 9.0 | 3.84e-6 9.5 |
| Q5_1 | `blk.0.ffn_down` (896 × 4864, 3.3 MB) | **2.55e-5** 12.2 | 2.55e-5 16.8 | 2.55e-5 17.4 |

Every cell ≤ 6.06e-6 except Q5_1 `ffn_down`, 2.55e-5: that is row 3, whose true dot is −0.023186 (near the metric's
1e-2 floor); the absolute error there is 5.91e-7 and the max absolute error over the 64 rows is 7.95e-7. numpy's f32
`dot` of the same dequantized row is 9.0e-8 off the f64 value, so the kernel is ~6× worse than a plain f32 dot on
this row — the m · Σy path: for that row the 152 per-block terms sum to |18.04| in magnitude and cancel to −0.264, and
they are accumulated in f32 separately from d · q · y (`mins`), an absolute floor of order 18 × 2⁻²⁴ ≈ 1e-6. Not a
layout error (the three layouts agree to the last printed digit on every tensor, and Q5_1 `attn_q` is 3.84e-6); a
fused single accumulator would trade it for one more multiply per block and was not done. GB/s on a 0.5 MB tensor
varies run to run by 2× (launch-bound); the ffn cells are the only ones worth reading. Negative control at the GPU
level: the Q5_0 attn_q r1 guest run against the **pre-q5x** `kdot_f32_r1.spv` (no type-6 arm, `block_bytes_of` = 0)
returns NaN for every row — `kdot_check.py` prints `max rel err nan` (it does not exit red on NaN; a known gap, the
number is still unmistakable). Unchanged-numerics controls with the rebuilt shaders (`kdot_f32_r1 / r8 / p / p1 / p2
/ p4 / p5 / p8 / p16.spv`, previous ones kept as `*.spv.pre-q5x`): Q8_0 `blk.0.attn_q` of the q8_0 file **9.40e-6** on
r1 / r8 / p (= tick 53), Nex Q5_K `blk.0.attn_qkv` **6.10e-6** on r1 / r8 / p (= tick 53, 21.5 / 18.0 / 22.3 GB/s).

Not measured: a Q5_0 row with 4864 columns (none exists in the file; the 19-group loop was exercised by Q4_1 / Q5_1
`ffn_down` instead), the odd-block-count straddle of tick 53 (28 / 152 blocks per row are even here too), Q4_K
(type 12, 12 tensors of the q4_k_m file — no arm, no oracle), a Q5_0 embedding (`embed_iq4xs.comp` has no arm), the p kernel at PFIX > 1 (only the
`-DPFIX=1` binary ran; the others were rebuilt from the same source and compile), and the B70 / Xavier boxes.


## Tick 55 (2026-09-20, HF coverage 2, coordinator): the dense guests on B70 and Xavier; the Xavier head on the new tokenizer core

The f32 kdot layout (the RADV table: `kdot_f32_r8` / `_r1`, positions kernel `kdot_f32_p<P>`) is portable — the same
generator arguments with `nvgpu`'s loader and `aarch64-linux` target run Qwen2.5-0.5B-Instruct Q8_0 on every box,
because the Q8_0 arms landed in the f32 kernels (tick 53) and the dense recipe (tick 54) never touches the
int8 / h2 tables when the layout says f32. Adaptive guests `prefill:8 batch:1,2,4`, `NEX_BOX_GGUF=models/…`, oracle
= `dense_ref.py`, `batch_drive.py --parts 38`:

| box | guest | rows | B=1 ms/step | B=4 ms/step |
|---|---|---|---|---|
| B70 (anv, x86_64) | `qw24-f32b70.bin` @27185 | 4/4 oracle-exact | 5.37 | 4.04 (per step of 4 rows) |
| Xavier (nvgpu, aarch64) | `qw24-f32xv.bin` @29360 | 4/4 oracle-exact | 18.0 | 30.4 |
| K16 (radv, tick 54) | `qw24.bin` | 4/4 | 16.0 | 17.8 |

B70's f32 path is already 3× K16 and 3.4× Xavier at B=1 — the tuned int8 / h2 layouts on these boxes need Q8_0 arms in
`kdot_i8_x8r4` / `kdot_x8r8` (anv) and `kdot_h2_r1` / `kdot_s4_r1` (nvgpu) before a dense model gets their speed; those
arms are the three subagent sections that follow (anv, nvgpu, and Q4_1 / Q5_0 / Q5_1 in the f32 kernels for Q4_K_M mixes).

**Xavier head on the new shell** (`serve_http.cljk` + `tokenizer_core.cljk` + `chat_templates.cljk` + `gguf_tokenizer.cljk`,
old files kept in `/root/kgpu/shell.pre55/`): `systemctl restart murakumo-xavier-nex-native` → active; log
`TEMPLATE chatml-think pre qwen35 add_bos false eog [248044 248046]`; chat "What is the capital of France? Answer in one
word." → `"Paris"`, prompt_tokens 21, 1957 ms wall (1.70 s in tick 52 on the old shell; the two prompts and their token
counts were not the same, so the 250 ms is not yet attributed — measure the same request on both shells before
calling it the tokenizer core); seeded haiku (T 0.7 / top_p
0.9 / seed 7) → `"Autumn rain falls softly / Leaves drift down in crimson rivers / Earth breathes before sleep"`, 22
tokens — the same text the serial and the adaptive shells produced in ticks 50–52, so the token ids the new core feeds the
guest are the ids the old core fed it for this prompt. K16 :8099 (the 12-layer Nex prefix guest, same new core): greedy
and seeded completions oracle-exact (`128186,116769,…` / `80072,…`), chat text meaningless as it was under the old core
in tick 37 — a 12-layer prefix of a 40-layer model is not the model; the shell is judged on the ids.

### Tick 55, after the anv arms landed: the dense guests on the anv layout (B70)

With `kdot_x8r4` / `kdot_i8_x8r4` reading Q8_0 (section above), the generator's `anv` layout runs the dense recipe end
to end. Oracle = `dense_ref.py` 9-token continuations (the same four Qwen prompts and two Llama prompts as below; a
12-token prompt exercises the prefill-8 chunk), `batch_drive.py --prefill 8 --parts 38|32`, GPU frequency not pinned:

| model, box | layout | B=1 ms/step | B=2 | B=4 | rows |
|---|---|---|---|---|---|
| Qwen2.5-0.5B Q8_0 24 L, B70 | f32 (radv table) | 5.37 | 4.62 | 4.08 | 4/4 |
| same | anv as tuned for Nex (int8 lm B times, decode form to B=2) | **4.28** | 6.81 | 6.56 | 4/4 |
| same | anv + `:lm-once` + `:batch-layout-upto 1` (now the dense rule) | **4.28** | **4.64** | **4.06** | 4/4 |
| Llama-3.2-1B Q8_0 16 L, B70 | anv (dense rule) | **6.08** | 7.77 | 5.78 | 1/1, 2/2, 4/4 |

Two of the anv table's Nex-tuned choices reverse on a dense model, and the reason is the lm_head: Qwen's 151936 × 896
Q8_0 is 145 MB against 24 layers of 12 small tensors, so the B-times int8 lm_head read (`:lm-i8`) is the batch step's
largest term — B=4 6.56 → 4.06 ms/step once the positions kernel reads it once — and the int8 decode form at B=2 pays
the same weights twice (6.18 → 4.64 with `kdot_f32_p2`). Layer kdots keep `x8r4` (B=1 4.28 vs the f32 kernels' 5.37,
−20%); the int8 `:wide-i8` class is not used by the dense recipe (it names Nex's qkv / gate / q). The rule lives in the
generator as `(if (and dense? (= backend "anv")) (assoc layouts* :lm-once true :batch-layout-upto 1) layouts*)`; the
Nex anv guest regenerates byte-identical (4 L control), and the dense anv guest with the rule is byte-identical to the
hand-made `anv-lmonce` + `NEX_BATCH_LAYOUT_UPTO=1` guest it was measured with.

Per token, B70 now runs Qwen2.5-0.5B at 4.3 ms and Llama-3.2-1B at 6.1 ms natively (K16: 16.0 / 34.5). Qwen rows:
prompts `785,6722,315,9625,374` → `12095,13,1084,374,279,7772,3283,304,4505`; `9707,11,847,829,374` →
`8515,323,358,1079,264,3162,15754,13,358`; `16,17,18,19` → `20,21,22,23,24,15,16,17,18`;
`785,3974,13876,38835,34208,916,279,15678,5562,13,576,6722` → `315,9625,374,12095,13,3555,374,279,6722`. Llama rows:
`128000,791,6864,315,9822,374` → `12366,13,578,469,3168,301,22703,374,7559`; `128000,9906,11,856,836,374` →
`35266,323,358,2846,264,6908,8571,315,701`. `kdot_check.py` now exits 1 on a non-finite row or rel > 1e-3 (the
quantized-activation oracle's error when `.refq.npy` exists) — the Q5_0-vs-old-shader NaN control had printed `nan`
and exited 0; verified on synthetic ok / NaN / 1 % inputs (0 / 1 / 1).

## Tick 55 (2026-09-20): Q8_0 / Q4_0 / F16 in the nvgpu kernels (`kdot_h2_r1` / `kdot_s4_r1`) — measured on the Xavier

The three iteration-53 arms (Q8_0 type 8, Q4_0 type 2, F16 type 1; 32-value blocks of 34 / 18 B or none, rows
`ceil(cols / 32)` blocks, group count `ceil(cols / 256)`, tail group masked) are now in the two nvgpu one-row
kernels: `kdot_s4_r1.comp` (the exact f32 row, `nvgpu-exact`) and `kdot_h2_r1.comp` (the packed-half row; both
`kdot_h2_r1.spv` and `-DQ6_HALF` → `kdot_h2q6_r1.spv` build and carry the arms). **Staging**: these types stage
nothing (`hwords = 0`) — the per-32 `d` sits inside the block and is read through `weight_half` — so
`hdr[16][5]` keeps its 16-block capacity and Qwen's ffn_down (cols 4864 = 19 groups) never touches it; the
two-groups-per-iteration loop gets a trailing single for the odd 19th group and a per-thread tail mask. The
K-quant loop is untouched. h2 dequant: Q4_0 by the exponent trick with the −8 folded into the bias (1032); F16
loaded as `f16vec2` directly; **Q8_0 by `float16_t(int8)` conversion (I2F)** — the exponent trick for signed bytes
(`s ^ 0x80` then `0x6400 |`, minus 1152) is kept behind `-DQ8_TRICK` and produces bit-identical outputs, but the
binary that carries it runs *every* arm slower and erratically on nvgpu (below), the same whole-binary effect as
iteration 21's Q6 arm. `gen_kdot_guest.cljk` gains the layouts `s4r1` / `h2r1` / `h2q6r1` and `KDOT_SPV_DIR`
(measure a rebuilt kernel from a side directory before it replaces the installed one). Xavier holds
`kdot_{h2,h2q6,s4}_r1.spv.pre-q80`; the Qwen GGUFs are in `/root/kgpu/models/` (sha256 = the HF etags
`ca59ca7f…` / `7671c0c3…` / `8e0ae260…`; root fs 4.5 → 3.2 GB free).

Xavier, nvgpu, GPU at 1377 MHz, first 64 rows, `max |gpu − f64| / max(|f64|, 1e-2)` against `kdot_ref.py`, GB/s
from 10 dispatches in one buffer. **The production resident head (`rap40-nv.bin`, :8090) was on the GPU during
every number here**; attn_k is launch-bound and its GB/s is not listed.

| type | tensor (rows × cols) | s4r1 exact | s4 GB/s | h2r1 | h2 GB/s |
|---|---|---|---|---|---|
| Q8_0 | `blk.0.attn_q` (896 × 896) | **6.42e-6** | 22.3 | 3.70e-2 | 20.6 |
| Q8_0 | `blk.0.attn_k` (128 × 896) | 4.73e-6 | — | 3.93e-3 | — |
| Q8_0 | `blk.0.ffn_down` (896 × 4864, 19 groups) | 2.19e-6 | 44–47 | 1.28e-2 | 42–43 |
| Q4_0 | `blk.0.attn_q` | 7.75e-6 | 11.7 | 1.80e-2 | 11.2 |
| Q4_0 | `blk.0.ffn_down` | 3.88e-6 | 20.2 | 7.71e-3 | 20.8 |
| F16 | `blk.0.attn_q` | 2.83e-6 | 26.2 | 3.22e-2 | 38.6 |
| F16 | `blk.0.ffn_down` | 3.64e-6 | 63.3 | 4.04e-3 | **74.6** |

s4 is exact to the f32-accumulation floor (≤ 7.75e-6, K16's f32 kernels gave ≤ 1.01e-5 on the same tensors). The
h2 column is the half format's budget, in the band of the existing arms (Q5_K attn_qkv on the same box and metric:
3.97e-2): rel-RMS against the f64 dot is 1.8e-4 – 2.2e-4 for all six h2 cells, of which rounding `x` to f16
alone is 1.4e-4 – 2.1e-4; max |Δ| 1.3e-3 on attn_q (|dot| ≤ 5.8). An emulation of the kernel's arithmetic
(x → f16 RN or RTZ, products in f16 or f32, f32 sums) did **not** reproduce the GPU bit-for-bit (1e-2-level
differences either way, each as far from f64 as the GPU is) — the driver's f32 → f16 conversion / product
rounding could not be pinned; the addressing is verified by the exact kernel, which shares it.

**Unchanged-numerics control** (same guests, installed pre-q80 spv vs the rebuilt spv, outputs compared as hex):
Q5_K `blk.0.attn_qkv` h2r1 **bit-identical** (3.97e-2; 20.9 → 21.5 GB/s), s4r1 bit-identical (6.64e-6; 18.6 → 19.2),
Q6_K `output` h2q6r1 bit-identical (3.37e-3; 26.3 / 25.0 / 24.8 pre vs 25.6 / 24.5 / 24.9 new — noise). The
40-layer × 6-token `fn` guest (prompt 9707,198,220): hidden states and final logits **bit-identical** across all
eight runs (argmax 198, 410, 471, 220, 16, 15).

**Q8_0 I2F vs exponent trick, whole-binary effect** (same source otherwise; spv files swapped under each other's
path to separate kernel content from the guest): the trick binary — fp16 ffn_down 40.8 / 44.3 GB/s (77.3 once),
Q4_0 ffn_down 11.6 – 25.2, Q8_0 ffn_down 19.6 – 29.4 (41.3 once), Q8_0 attn_q 5.7 – 8.3 (19.0 once), Q5_K control
17.1 / 20.9; the I2F binary — fp16 76.5 / 75.6 / 74.6, Q4_0 19.7 / 20.5 / 20.8, Q8_0 ffn_down 41.3 – 43.1, attn_q
19.4 – 20.6, Q5_K 21.5 / 21.6, stable run to run. Installed = I2F.

**40-layer token A/B, 3 pairs, not a conclusion.** ms/step (mean of steps 1–5) pre-q80 → new: 85.7 → 88.6,
89.2 → 90.3, 87.7 → 89.7 (the trick build: 87.4, 89.5). The spread inside one side (85.7 vs 89.2) is as large as
the gap; the pairs ran beside the production head, and two 40-layer guests do not fit the box: the head was
SIGKILLed (status 9/KILL, load 24) at 12:37 and 12:46 JST while a pair loaded — the runs were stopped, no more
40-layer guests are to be run on Xavier (a token-level control there is the 12-layer guest at most), and the
head's 12:46:25 restart loaded the **pre-q80** spv (in place at that moment for the interleaved pair); the new
spv were re-installed after it, so the running head keeps pre-q80 pipelines until its next restart. Not measured:
the new binaries under the production head, Q4_0 / F16 attn_k, an odd-block-count row (as in tick 53), B70 / K16
(these kernels are nvgpu-only). Scratch on the box: `/root/kgpu/q80wip/` (sources, spv variants, guests, outputs).

## Tick 56 (2026-09-20, HF coverage 3): the dense guests on the nvgpu (h2) layout — Xavier

With `kdot_h2_r1` / `kdot_h2q6_r1` reading Q8_0 (section above), the generator's `nvgpu` table (`:wide` / `:narrow`
h2, `:lm` h2q6, `:lm-once`) runs the dense recipe on Xavier. Same four Qwen oracle rows as tick 55, `batch_drive.py
--prefill 8 --parts 38`, 24-layer guest beside the resident 40-layer head (20 GB of 31 in use), clocks not pinned:

| Qwen2.5-0.5B Q8_0 24 L, Xavier | B=1 ms/step | B=4 | rows |
|---|---|---|---|
| f32 layout (tick 55) | 18.0 | 30.4 | 4/4 |
| nvgpu h2 layout | **15.97** | 29.84 | 4/4 |

Every generated token equals the f64 oracle's although the h2 kernels round the activation to f16 (rel-RMS ~2e-4 per
kdot, see the nvgpu section) — for these 36 argmax decisions the margin was larger than the error; this is the same
"argmax-exact, distribution-approximate" status the Nex h2 path has had since iteration 21 and it should be read that
way (a distribution comparison against `dense_ref.npz` logits is the check that would say more). The B=4 step barely
moves (30.4 → 29.8): on Xavier the batch step is issue-bound in the positions kernel, which is f32 and unchanged.

Head note: the production head restarted at 12:46:25 JST from the pre-q80 spv (the swap was mid-flight); the new
`kdot_{h2,h2q6,s4}_r1.spv` were installed at 12:47 and the K-quant outputs are bit-identical between the two, so the
running head is correct and will pick the new files up at its next restart — no restart forced for that.

## Tick 57 (2026-09-20, HF coverage 4): a Q4_K_M file end to end — mixed types per layer

Qwen2.5-0.5B-Instruct **Q4_K_M** (llama.cpp's default download quant) is a mix: `token_embd` Q5_0, `output` Q8_0, attention
and gate/up Q5_0, `attn_v` **Q8_0 in layers 0–1 and Q5_0 from layer 2**, `ffn_down` **Q6_K in 12 layers and Q4_K in 12**
(types `{8: 13, 6: 133, 0: 121, 14: 12, 12: 12}`). Two things stood between the generator and this file:

1. **The embedding kernel** had IQ4_XS / Q8_0 / PTQ1 arms only. `embed_iq4xs.comp -DB32=<type>` now dequantises the four
   legacy 32-value block types (2 Q4_0, 3 Q4_1, 6 Q5_0, 7 Q5_1) as `ggml-quants.c` does (5th bit of value j = bit j of the LE
   u32 `qh`, `-8` / `-16` offsets, `m` for the `_1` types), `embed_q40|q41|q50|q51{,_b,_bp}.spv` built on K16 (glslang,
   vulkan1.1). First build wrote only blocks 0–23 of a 28-block row: the IQ4_XS early return `t >= blocks*8` (blocks = cols/256
   = 3) was still in front of the new arm — found because the debug `x` matched the oracle's row for the first 768 values and
   was 0 after (`NEX_DEBUG_BUFS=x`, oracle `dense_ref.rows_of`). The installed Q8 / IQ4_XS spv were rebuilt and disassembled
   against the installed ones: identical past debug names / the target-env `Block` decoration.
2. **The dense kdot metas were typed from layer 0** (`(:type (T* "blk.0.attn_v.weight"))` for every layer): every layer
   read `attn_v` as Q8_0 and `ffn_down` as Q6_K → NaN from layer 2 on (found by a 3-layer debug guest: `dv` had 55 NaN of 128
   while a standalone `kdot_f32_r1` guest on the same `blk.2.attn_v.weight` was exact at 2.6e-6 — the tensor and kernel were
   fine, the meta was not). A uniform file (the Q8_0 Qwen / Llama runs of ticks 54–56) never showed it.

   Fix: one meta buffer per `[phase shape [pf ipe], role, distinct type]` (`dense-metas`), a per-layer **type signature**
   (`dense-sigs`, distinct type vectors over the 6 kdot roles; 2 for this file), and the shared layer function derives its
   layer's signature from its weight base — `(let [sig (sig-of (quot (- w0 W0) 12))] …)`, `sig-of` an if-chain over layers
   — and a role whose type varies picks its meta with `(if (= sig k) …)` (8 such sites in the adaptive guest; a uniform file
   emits none and its guests differ from before only in meta handle numbers). Two roads not taken: per-layer meta buffers
   (720 WRITE lines, 150 KB source, over the literal budget) and a 6th function parameter (`:kotoba.error/max-parameters`:
   the native ABI carries 5).

Measured on K16 (RADV, f32 kernels), oracle = `dense_ref.py` on the Q4_K_M file (its continuations for these prompts equal
the Q8_0 file's, so the x rel column — not the ids — is what shows the Q4_K / Q5_0 / Q6_K weights were read):

| guest | result |
|---|---|
| fn, 24 L, prompt 785,6722,315,9625,374, 13 steps | **13/13 argmax, x rel 3.2e-6 … 1.4e-5**, 17.2 ms/token |
| adaptive `prefill:8 batch:1,2,4`, 4 oracle rows (one 12-token) | **4/4**, B=1 16.24 ms/step, B=4 19.25 |
| control: Q8_0 file, same generator, B=4 | 4/4, 18.56 ms/step |
| control: Nex anv adaptive 4 L guest | byte-identical to the tick-55 generator's |

`decode_tokens_check.py` slices the 2048-wide shared row buffer to the model's width (dense rows are 896). The x rel band
(≤ 1.4e-5) is wider than Q8_0's (≤ 1.9e-6) — the Q4_K / Q6_K super-block paths accumulate in f32 over 256-value blocks;
same class as the Nex K-quant kdots (Q5_K 6.1e-6). Not done: Q4_K_M on B70 / Xavier (the anv / nvgpu kernels have no Q5_0 /
Q4_K arms — a Q4_K_M model would need the f32 layout there), the h2 distribution check, SentencePiece, gemma / mistral.

## Tick 58 (2026-09-20, HF coverage 5): the h2 dense path measured on its distribution — and replaced by the exact table

Tick 56 left the nvgpu (h2, f16-activation) dense result as "argmax-exact, distribution-approximate". `parity_check.py` now
runs without the llama-server json (oracle-only; exit 1 when the top-1 differs) and slices dense rows out of the 2048-wide
buffer. Qwen2.5-0.5B Q8_0, 24 L, fn guests, prompt 785,6722,315,9625,374, 14 steps, Xavier (head co-resident):

| layout | x rel per step | last-step logits max\|diff\| | KL(oracle‖gpu) | ms/step |
|---|---|---|---|---|
| `nvgpu` (h2 / h2q6) | 2.3e-3 … 6.9e-3 | 9.4e-3 | **1.06e-7** nats | 15.7–16.0 |
| `nvgpu-exact` (s4) | 3.3e-6 … 2.4e-5 | 1.8e-5 | **9.2e-13** nats | 14.6–14.8 |

Both 14/14 argmax, top-1 323 = oracle. The h2 KL of 1e-7 is four orders below llama.cpp's own deviation from the f64 oracle on
this file (KL 1.5e-3, dense-oracle section) — the f16 activation path is not a quality problem here. But it is also **not a
speed win on a dense 896-wide model**: the s4 kernels are faster at every B once the exact table also reads the lm_head once
(`:lm-once`, added to `nvgpu-exact`): adaptive guests `prefill:8 batch:1,2,4`, four oracle rows —

| Xavier, Qwen 24 L | B=1 | B=2 | B=4 | rows |
|---|---|---|---|---|
| h2 (tick 56) | 15.72 | 19.17 | 29.84 | 4/4 |
| s4 exact, no lm-once | 14.69 | — | 35.61 (lm_head read 4×) | 4/4 |
| **s4 exact + lm-once** | **14.83** | **19.15** | **29.60** | 4/4 |

The h2 table was tuned on Nex (iteration 21: 2048-wide, bandwidth-bound tensors, where halving the activation bytes paid); a
0.5B dense layer is launch-bound and the f16 conversions are pure overhead. The generator's dense rule now sends `nvgpu` to
the exact table (`(and dense? (= backend "nvgpu")) → (layout-table "nvgpu-exact")`); the Nex nvgpu guest regenerates
byte-identical and the dense nvgpu guest is byte-identical to the `nvgpu-exact` guest measured above. Three boxes, dense
Qwen B=1, all oracle-exact in distribution too: B70 4.28 / K16 16.0 / Xavier 14.8 ms/token. Not done: the same distribution
check for the anv int8 path on B70 (its lm_head is f32 x8r4 for dense, so the logits are exact by construction — the
activation quantisation sits in Nex's `:wide-i8` class, unused by the dense recipe), SentencePiece, gemma / mistral.

## Iteration 66 (2026-09-20): Ternary Bonsai 2 27B PTQ1_0 native E2E on B70

The 64-layer `qwen35` path now reads the hybrid dimensions and Prism Hadamard contract from GGUF, maps PTQ1_0 folded
weights directly, applies signed normalized 1024-wide transforms around embeddings and every folded projection, runs the
48 recurrent plus 16 full-attention blocks, and serves the resident-replay guest through the OpenAI-compatible HTTP shell.
The correctness defect found by the first full run was in the GGUF reader: `prism.hadamard.sign_values` is an `INT32`
array, but type 5 was read as unsigned, turning −1 into 4294967296. Fixing signed metadata restored finite activations.

Reference = Prism llama.cpp `prism-b10709-9a9394a`; model =
`Ternary-Bonsai-2-27B-PTQ1_0.gguf` sha256 `53107f53…`; target = B70 / Intel BMG G31, Mesa 25.2.8 Vulkan ANV. Raw greedy
`Hello` produces **8/8 identical** token ids `11, 353, 2688, 264, 5286, 303, 279, 3694`
(`", I'm a student in the University"`) in both engines. The tokenizer is **18/18** corpus lines equal to
llama-server `/tokenize`; Qwen3.5's template (including its default xhigh system instruction) is **3/3** message shapes
byte-equal to `/apply-template`. A warm chat E2E, “What is the capital of France? Answer in one word.”, runs 64 prompt +
36 completion tokens in **12.609 s**, answers **Paris**, and stops at the EOG token; GPU time is **125.223 ms/step**.

HTTP concurrency used identical `Hello`, 8-token greedy requests after warmup:

| concurrent requests | total completion tokens | wall s | aggregate completion tok/s | p50 / max latency s |
|---:|---:|---:|---:|---:|
| 1 | 8 | 1.0623 | 7.5308 | 1.0614 / 1.0614 |
| 2 | 16 | 2.0098 | 7.9610 | 1.5073 / 2.0092 |
| 4 | 32 | 4.0195 | 7.9612 | 2.5124 / 4.0186 |
| 8 | 64 | 8.0362 | **7.9639** | 4.5209 / 8.0347 |

The HTTP surface accepts concurrency, but this Bonsai guest has `batch-rows = 0`: requests queue behind one sequence and
one token is aggregated per replay. Throughput therefore saturates near 8 tok/s and tail latency grows linearly. The next
throughput lever is qwen35 batched decode and transformed prefill; neither is claimed here. The deployed local surface is
`murakumo-b70-bonsai-native.service` on `127.0.0.1:8092`, model id
`prism-ml/Ternary-Bonsai-2-27B-PTQ1_0`. Full machine-readable evidence and the unmeasured boundaries are in
`verify/evidence/ternary-bonsai-ptq1-native-e2e-20260920.json`.
