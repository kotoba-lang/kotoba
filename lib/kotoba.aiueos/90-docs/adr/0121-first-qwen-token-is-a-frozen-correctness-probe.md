# ADR-0121: The first native Qwen token is a frozen correctness probe

Date: 2026-08-30
Status: accepted; first token passed on physical K16, multi-token decode pending

## Context

ADR-0120 admits the exact 866-tensor Qwen3.5 graph carried by the SHA-pinned
Qwen3.8 27B GGUF. Admission alone is not inference. Before optimizing AVX2,
threading, recurrent state or multi-token decode, AIUEOS needs one output that
can be compared with an independent implementation using the same artifact and
input.

The smallest complete computation is the BOS token at sequence position zero.
At that position every Gated DeltaNet convolution/recurrent state is zero and
each full-attention softmax has one element. The path still executes all 64
trunk layers, all dense feed-forward blocks and the 248,320-row output head, so
it is a real model result rather than a parser or transport marker.

## Decision

1. The first native correctness probe is frozen to BOS token `248044`. The
   expected top token is `2005`; token `17` is the expected runner-up.
2. AIUEOS implements all fourteen quantized tensor formats present in the
   artifact plus F32. The dequantizers and codebooks are derived from
   llama.cpp commit `3173a56471c1753650cd806694145ffd6dcace67` and retain MIT
   provenance in source.
3. The runtime is scalar and single-core. It executes the 48 zero-state Gated
   DeltaNet layers, 16 one-token full-attention layers, every dense SwiGLU FFN,
   output norm and vocabulary head. The optional MTP layer is not part of the
   main-token pass.
4. The parsed graph and tensor workspace occupy 19 and 74 allocator pages,
   respectively. They are contiguous volatile RAM and are never written to an
   internal disk. Dead link sections are removed so the existing low-2MiB W^X
   bootstrap boundary remains valid.
5. The screen and serial log report layer progress, output-head progress, the
   top two tokens and raw TSC cycles. Cycles are not converted to seconds or
   tokens/s until the physical K16 clock is calibrated.

## Evidence and limits

Using the exact 10,934,860,704-byte artifact, the AIUEOS host runtime returned
token `2005` with logit `8.9886446` and token `17` with logit `8.66631413`.
The pinned llama.cpp Metal reference returned the same ranking with logits
`8.98845387` and `8.66601849`. All fourteen quantized row decoders matched the
corresponding llama.cpp decoder bit-for-bit on real rows from the artifact.
The split-model QEMU boot remains green after the runtime was linked.

These are same-artifact host and virtual-boot results. They do not prove that
the K16 has generated the token, establish K16 throughput, preserve recurrent
or KV state for a second token, or submit the result as a Murakumo job. Those
claims remain closed until their physical evidence exists.

## 2026-08-31 physical follow-up

The K16 advanced to `FAILED AT TOKEN 02`. The generation path emits that state
only after token 1 equals the frozen `2005` reference, so physical first-token
correctness is now observed. No decode token completed, therefore decode tok/s
remains unavailable rather than zero.

The failure exposed an output/workspace alias in full attention. The key
projection wrote into `dequantized`, which is also `matvec_range`'s BSP row
buffer. Each new weight row overwrote earlier key outputs while the AP wrote
the other half. Position zero could not reveal this because a one-element
softmax always assigns the cached value weight one; position one is the first
step that compares keys. The decoder now gives key projection, value
projection, and gate temporary disjoint ranges and rejects non-finite state at
the layer that creates it. Physical retry remains required before calling the
eight-token sequence, its rate, or its Murakumo post complete.

The next physical image made the remaining failure precise:
`T02 L04 SOFTMAX`. That is the first full-attention layer at sequence position
one. The decoder therefore keeps the primary key cache under a per-entry hash,
writes a physically separate shadow key plane, repairs only a primary entry
whose shadow still matches, and fails as `KV CACHE` if neither copy is intact.
Finite Q/K operands are accumulated as double products for the bounded
eight-position softmax, so float-product overflow cannot masquerade as cache
corruption; invalid query and cache inputs have separate screen stages.

The same audit found that the recurrent 16-to-48 Q/K-to-value expansion used
`head % 16`. Qwen3.5 specifies `repeat_interleave(48 / 16)`, so each Q/K head
feeds three adjacent value heads. The native mapping is now `head / 3`, with a
48-head host check. This is a decoder correctness fix, not a performance claim.
The corrected eight-token image still requires physical K16 evidence before a
decode rate or successful Murakumo result may be recorded.

## 2026-09-01 reference supersession

The frozen token 2005 belonged to the earlier cyclic `head % 16` execution and
cannot gate the corrected adjacent repeat-interleave graph. A physical K16
layer-hash diagnostic ran the current cache-free position-zero path and
observed token 248046 (the model EOS) for BOS 248044. The current runtime gate
is therefore 248046. The earlier 2005 runs remain historical evidence for the
old graph and are not rewritten as corrected-graph results. Multi-token decode,
its rate, and the Murakumo result remain pending until the corrected graph
produces and posts the complete bounded sequence.
