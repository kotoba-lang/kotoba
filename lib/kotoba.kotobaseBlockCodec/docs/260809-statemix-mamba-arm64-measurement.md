# StateSMix / Mamba host experiment — 2026-08-09

## Boundary

This is a cold-path experiment, not a new `core/frame` format.  The measured
upstream source is pinned to
`f9a55efd861610ce0232bbd0307317541d094bbd`.  The host was Apple Silicon
ARM64, while upstream requires x86-64 AVX2/FMA/OpenMP, so compilation and
execution used Docker `--platform linux/amd64` with `gcc:14-bookworm`.  Timing
therefore includes emulation and is not a native throughput estimate.

## Measured sample

- input: upstream `README.md`
- bytes: 4,561
- SHA-256: `75d811e4c2ba6b50a2069452b92a59491144f3d0e7a3f6e2023c7f336c094463`
- StateSMix model: DM=32, DS=16, DI=64, NL=2, GPT-NeoX BPE
- model seed: 0 (upstream fixed zero-initialised global; not user-selectable)

Actual file sizes include the codec header and vocabulary map.  Thus the bpb
below is `8 * output_bytes / 4561`, not StateSMix's separately printed model
cross-entropy estimate.

| codec | bytes | ratio | actual bpb | wall time |
|---|---:|---:|---:|---:|
| StateSMix full | 2,031 | 0.4453 | 3.562 | 46.12 s |
| Mamba SSM + count (`ABLATION=1`) | 2,136 | 0.4683 | 3.747 | 114.33 s |
| Brotli 11 | 1,836 | 0.4025 | 3.220 | 1.23 s |
| zstd 19 | 2,179 | 0.4777 | 3.822 | 0.93 s |
| gzip 9, no filename/time | 2,184 | 0.4788 | 3.831 | <0.01 s |
| xz 9e | 2,208 | 0.4841 | 3.873 | 0.93 s |
| bzip2 9 | 2,297 | 0.5036 | 4.029 | <0.01 s |

On this very small English/Markdown sample, full StateSMix was 7.0% smaller
than gzip and the Mamba-only ablation was 2.2% smaller than gzip.  Brotli was
9.6% smaller than StateSMix.  This sample is useful for wiring validation but
is not representative of Common Crawl.

## Lossless gate and OpenMP finding

The first independent `d` attempt under upstream's unconstrained OpenMP setup
failed with `malloc(): corrupted top size`. StateSMix repeats online training
during decoding, so a different parallel floating-point reduction order can
change the probability sequence and corrupt arithmetic decoding.

With `OMP_NUM_THREADS=1` and `OMP_DYNAMIC=FALSE`, a fresh independent process
decoded the 2,031-byte stream to exactly 4,561 bytes. Both files had SHA-256
`75d811e4c2ba6b50a2069452b92a59491144f3d0e7a3f6e2023c7f336c094463`.
Measured model-loop times in that verified run were 0.3 s compression and 0.6
s decompression; container wall time was approximately 4.2 s and 5.3 s.

The adapter now enforces both environment values, snapshots the input to avoid
concurrent-write races, uses a private candidate file, invokes an independent
decoder, compares every byte, and atomically publishes only after equality.
Failed or timed-out runs publish nothing.

The completed adapter itself was then run inside the amd64 container. It
reported `input-bytes=4561`, `output-bytes=2031`, `bits-per-byte=3.5623767`,
`compress-duration_ms=4814`, `decompress-duration_ms=4339`, the SHA-256 above,
`:roundtrip-verified? true`, and `:published-after-verification? true`. No
candidate or recovered temporary file remained after publication.

Before production adoption, repeat on native x86-64 at 1 MB and 10 MB, pin the
tokenizer hash and container digest, and produce cross-host golden streams.
