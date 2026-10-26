# ADR-0120: The exact Qwen35 GGUF graph is admitted before any tensor executes

Date: 2026-08-30
Status: accepted; host and QEMU qualified, extended by ADR-0121

## Context

The K16 has now booted a pure-AIUEOS image which reconstructs the exact
Qwen3.8 27B GGUF from three FAT32 files, verifies its full SHA-256, maps it
read-only/NX and reaches Murakumo over the native RTL8125/TLS path. That proves
artifact transport and kernel admission. It does not prove that the bytes form
the graph the planned runtime expects, and it certainly does not prove a
generated token.

The artifact identifies its architecture as `qwen35`. It is a dense hybrid,
not an ordinary all-attention Qwen3 stack: the 64-layer trunk is 48 Gated
DeltaNet layers and 16 full-attention layers, followed by one optional MTP
block. Guessing the older graph from the model name would execute valid bytes
with the wrong semantics.

## Decision

1. The native kernel parses GGUF v3 with a bounded, allocation-free reader.
   Metadata strings and the large tokenizer arrays are skipped in place; no
   model payload is copied.
2. Admission is exact for this immutable artifact: byte length, metadata and
   tensor counts, table/data offsets, architecture constants, tokenizer
   cardinality and IDs, all 866 tensor roles and dimensions, and the complete
   distribution of 15 GGML tensor types must match.
3. Tensor storage size is computed from the declared dimensions and block
   type. Offsets must be contiguous after 32-byte alignment and the last
   tensor must end at the exact artifact byte length. An overlap, gap,
   duplicate role, unknown role, unsupported type or truncated table refuses
   the graph.
4. Only a complete mapping may bind tensor pointers. A host gate may parse the
   10,996,640-byte header prefix, but that prefix is not allowed to fabricate
   pointers into absent weight bytes.
5. The framebuffer says `QWEN35 GRAPH READY` only after this gate. Load,
   prefill, decode and first-token timing remain unmeasured until real
   generation exists.

## Evidence and limits

The self-contained gate constructs the exact 50-entry metadata and 866-entry
tensor-table shape without embedding 10.9 GiB of weights. It passes the valid
case and refuses truncation, wrong artifact length and wrong architecture. The
same parser also accepts the first 10,996,640 bytes fetched by range from the
SHA-pinned production artifact. The existing split-FAT32 QEMU boot remains
green with its explicitly named tiny transport fixture.

This ADR remains the graph-admission boundary and does not itself claim
inference. ADR-0121 records the later same-artifact scalar first-token proof.
Physical K16 execution, SIMD/threading, persistent recurrent/KV state and
Murakumo job execution remain separate gates.
