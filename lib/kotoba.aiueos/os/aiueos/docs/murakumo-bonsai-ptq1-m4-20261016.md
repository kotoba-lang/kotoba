# M4 result: Amu-generated Kotoba Native is 3.34–3.56× faster on a real Bonsai PTQ1 matvec

On an Apple M4, an Amu-generated Kotoba Native AArch64 kernel processed the real first-layer `blk.0.ffn_down.weight` tensor from Ternary Bonsai 2 27B PTQ1_0 in 3.34–3.56× less time than the measured C reference. All 5,120 outputs matched bit for bit.

This is a **single matvec-kernel result**. It is not a whole-model inference measurement or a comparison against other inference runtimes, so it does not establish that Murakumo is the fastest inference system.

## What was measured

- Artifact: [`Ternary-Bonsai-2-27B-PTQ1_0.gguf`](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf), 5,946,648,928 bytes, SHA-256 `53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3`.
- Tensor: `blk.0.ffn_down.weight`, GGUF shape `[17408, 5120]`, type 143 (PTQ1_0), 19,496,960 bytes at absolute file offset `585748832`.
- Work per timed sample: 5,120 output rows × 17,408 input elements × 4 repeats = 356,515,840 multiply-accumulate elements.
- Both implementations used the same deterministic F32 input vector and the tensor's real packed weights.
- C baseline: `clang -O3 -mcpu=native`, row dequantization followed by four-lane scalar dot reduction. The PTQ1 reference decoder is included with the harness and follows the AIUEOS C decoder's PTQ1_0 layout and arithmetic.
- Kotoba Native: captured Amu-generated AArch64 code, running the fused PTQ1_0 decode, scaling, multiply, and accumulation path. It does not materialize a dequantized F32 row.
- Execution: standalone arm64 benchmark harness on the M4. This did not boot the complete AIUEOS image.

## Results

Each trial had two warmup rounds per implementation, seven timed samples, and alternated which implementation ran first. The reported result is each trial's median. A third run used the exact base64-published code blob and the listed build command.

| Trial | C median | Kotoba Native median | Kotoba Native vs C |
|---:|---:|---:|---:|
| 1 | 845.148 ms | 243.023 ms | 3.477× |
| 2 | 889.927 ms | 250.001 ms | 3.560× |
| 3 | 760.918 ms | 228.142 ms | 3.335× |

Every one of the 5,120 output values had the same F32 bits in the C and Kotoba Native paths (`parity-maxdiff=0`).

### Raw samples

| Trial | Sample | C (ms) | Kotoba Native (ms) |
|---:|---:|---:|---:|
| 1 | 1 | 796.487 | 243.023 |
| 1 | 2 | 809.921 | 231.640 |
| 1 | 3 | 850.222 | 272.739 |
| 1 | 4 | 818.045 | 250.420 |
| 1 | 5 | 845.148 | 232.432 |
| 1 | 6 | 992.708 | 227.925 |
| 1 | 7 | 955.397 | 282.206 |
| 2 | 1 | 1602.428 | 407.400 |
| 2 | 2 | 1679.113 | 342.928 |
| 2 | 3 | 889.927 | 250.001 |
| 2 | 4 | 912.322 | 241.793 |
| 2 | 5 | 819.888 | 258.793 |
| 2 | 6 | 797.447 | 248.552 |
| 2 | 7 | 757.269 | 228.047 |
| 3 | 1 | 769.699 | 287.674 |
| 3 | 2 | 760.918 | 248.764 |
| 3 | 3 | 752.882 | 228.142 |
| 3 | 4 | 742.869 | 229.530 |
| 3 | 5 | 773.564 | 216.725 |
| 3 | 6 | 778.923 | 216.372 |
| 3 | 7 | 726.999 | 217.856 |

## Reproduce the kernel comparison

Run on an Apple M4 or another arm64 macOS host. The model download is about 5.9 GB.

```sh
curl -L --fail \
  -o Ternary-Bonsai-2-27B-PTQ1_0.gguf \
  'https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/main/Ternary-Bonsai-2-27B-PTQ1_0.gguf'
shasum -a 256 Ternary-Bonsai-2-27B-PTQ1_0.gguf

python3 -c 'import base64,pathlib; pathlib.Path("qwen35-matvec-a64-fused.bin").write_bytes(base64.b64decode(pathlib.Path("os/aiueos/tests/fixtures/qwen35-matvec-a64-fused.bin.base64").read_text()))'
shasum -a 256 qwen35-matvec-a64-fused.bin

clang -O3 -mcpu=native \
  os/aiueos/tests/qwen35-matvec-real-gguf-a64.c \
  os/aiueos/tests/qwen35-ptq1-reference.c \
  -o qwen35-matvec-real-gguf-a64

./qwen35-matvec-real-gguf-a64 \
  ./qwen35-matvec-a64-fused.bin 32264 \
  ./Ternary-Bonsai-2-27B-PTQ1_0.gguf 585748832
```

The GGUF checksum pins the tensor table and therefore the payload offset used by this command. The captured native-code blob is 41,704 bytes with SHA-256 `04e372a41cf5f29efe862fad5d6a9f65365da62c435063d341a15622501cd7a4`.

## Limits

The C comparison is against this explicit C reference path, not a tuned general-purpose inference runtime. No prompt processing, token generation, tokens/second, energy, or memory comparison was measured. The full AIUEOS image exceeded its low-region link limit by 147,456 bytes in this experiment, so the kernel result must not be presented as a completed booted Murakumo inference result or as a fastest-inference record.
