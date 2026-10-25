# Inference speed and environment analysis (2026-09-24)

This report records observed results and their boundaries. Autoregressive decode, diffusion generation, long-prompt prefill, and hosted request throughput are separate metrics and are not ranked together.

## Recorded cases

| Model and artifact | Host / runtime | Measured result | Qualification |
|---|---|---:|---|
| MiMo-V2.6-Distill-Qwen-9B Q4_K_M | 6600hs-2, Ryzen 7 7735HS / Radeon 680M, llama.cpp Vulkan | 8.10 decode tok/s; 95.51 prompt tok/s | 128 prompt + 128 generated tokens, 3-run mean; 33/33 GPU layers |
| MiMo-V2.6-Distill-Qwen-9B Q8_0 | Same | 5.29 decode tok/s; 91.02 prompt tok/s | Same condition; Mishima was co-resident but healthy; weights fit GPU memory |
| DiffusionGemma-26B-A4B-it Q4_K_M | Same 680M, diffusion-specific Vulkan runner, TTM cap raised to 21 GiB | 2.2 tok/s, 256 output tokens, 21 diffusion steps | Completed GPU run; peak GTT 22.47/22.55 GB and host available RAM about 0.6 GiB |
| Nex-N2.5-mini uncensored APEX-Mini Q3_K_M GGUF | Same 680M, llama.cpp Vulkan | 18.14 decode tok/s; 38.69 prompt tok/s | Two long-document runs, 1,061 output tokens combined; not the requested AutoRound W4A16 artifact |
| Nex-N2.5-mini W4A16 AutoRound | Intel Arc Pro B70, vLLM 0.29.0 XPU | No qualified speed | Model loaded at 19.18 GiB XPU memory, but only a 10-token smoke preceded device loss during arithmetic probe |
| Ternary Bonsai 2 27B PTQ1_0 | Apple M1 Max 32 GB, Prism llama.cpp Metal | 9.55 decode tok/s mean; 9.34 aggregate tok/s for one HTTP slot | Three 64-token `llama_bench` runs; concurrency reduced aggregate generation rate |
| Ternary Bonsai 2 27B PQ2_0, hosted AWS L4 | HF Dedicated Endpoint, Prism fork, TurboQuant KV | 605.81 prompt tok/s at 32K; 304.45 at 128K | One cold prefill; two concurrent requests at 128K caused 502/503 |
| Same PQ2_0, hosted AWS T4 | HF Dedicated Endpoint, Prism fork, TurboQuant KV | 250.13 prompt tok/s at 32K; 163.49 at 128K; 110.36 at 261,632 | Long context completed, but endpoint later remained unavailable for 34 minutes |

Detailed records: [MiMo](mimo-v2.6-distill-qwen-9b-amd680m-20260924.json), [DiffusionGemma](diffusiongemma-26b-680m-20260924.json), [Nex](nex-n25-680m-and-b70-20260924.json), [Bonsai hosted](ternary-bonsai-hosted-turbo4-20260920.json), [Bonsai M1 Max and Murakumo component measurements](ternary-bonsai-2-27b-m1max-20260920.json).

## What affected speed and whether the run completed

### Shared-memory GPU capacity and TTM

The Ryzen 7 7735HS host has about 22 GiB usable system RAM and a Radeon 680M iGPU. With the default Linux TTM setting, the exposed GTT was about 11.38 GiB. That was enough for the 9B Q4/Q8 artifacts, but not enough for DiffusionGemma's approximately 16.8 GB Q4 weights and associated buffers. The 26B model failed before generation at the default, 18 GiB, and 20 GiB caps. At a 21 GiB TTM cap, Vulkan accepted all 31 layers and inference completed, but peak GTT nearly exhausted the 22.55 GB capacity and available host RAM fell to about 0.6 GiB. This is a successful measurement with little memory headroom, not a safe general-purpose default.

The 21 GiB cap is evidence for this specific host and kernel. Reuse it only after checking physical RAM, existing services, driver-reported GTT, and peak inference allocation on the target machine.

### Runtime compatibility and quantization

MiMo's GGUF Q4_K_M and Q8_0 ran through stock llama.cpp's Vulkan backend, with every layer assigned to the 680M. Q4_K_M decoded about 1.53 times as fast as Q8_0 in the measured 128-token workload; prompt processing differed by about 5%. Larger weights increased memory use but did not prevent all-layer placement in this case.

DiffusionGemma uses block-diffusion generation and needs `llama-diffusion-cli` from llama.cpp PR #24423. Its 2.2 tok/s includes a 21-step diffusion run; it is not directly comparable with token-by-token autoregressive decode. Its Q8_0 artifact was not measured.

Nex's requested W4A16 checkpoint is AutoGPTQ and the card names vLLM/SGLang support. The B70 vLLM XPU run loaded the model but lost the device during the follow-up probe, so no stable throughput was established. The 18.14 tok/s result is from a different Q3_K_M APEX-Mini GGUF artifact on the 680M. It demonstrates that this related GGUF ran on that runtime; it does not measure W4A16 AutoRound.

Ternary Bonsai needs the Prism llama.cpp implementation for its PTQ1_0/PQ2_0 formats. The hosted L4/T4 records use PQ2_0 weights and TurboQuant `turbo4` K/V; the M1 Max record uses PTQ1_0 and a different native/runtime path. The L4/T4 values are cold prompt-prefill throughput, whereas the M1 figures are generation decode throughput. These do not constitute a direct GPU ranking. Long-context hosted concurrency also exposed replica failures and post-run recovery problems that the nominal slot count did not predict.

## Practical conclusions

- For 9B on this 680M host, Q4_K_M was faster for decode than Q8_0 in the same measured workload and both used the GPU. Keep prompt and decode rates separate.
- DiffusionGemma can run on the 680M only after a substantial TTM increase in the measured configuration. At 21 GiB it generated at 2.2 tok/s, while leaving about 0.6 GiB of host RAM available. Repeat with more headroom before treating it as a stable serving profile.
- Do not assign a speed to the AutoRound Nex checkpoint from either the failed B70 smoke or the APEX Q3_K_M result. A stable run must use the exact W4A16 artifact and a supported runtime with an exclusive, adequately sized GPU allocation.
- For 27B, identify weight format, KV quantization, runtime fork, hardware, and metric before comparing. The L4/T4 prefill results cannot be compared numerically to M1 Max decode tok/s.
- No end-to-end Murakumo production decode rate is recorded for the 27B PTQ1_0 model. The existing Murakumo file reports measured matmul-component accumulation and labels it an optimistic upper bound because the complete 64-layer token recipe is not wired.

## Source model cards

- [Xiaomi MiMo-V2.6-Distill-Qwen-9B](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B) and [bartowski GGUF quantizations](https://huggingface.co/bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF)
- [DiffusionGemma GGUF](https://huggingface.co/unsloth/diffusiongemma-26B-A4B-it-GGUF)
- [Nex AutoRound W4A16](https://huggingface.co/com-kotobalabs/Nex-N2.5-mini-Uncensored-W4A16-AutoRound) and [APEX-Mini GGUF](https://huggingface.co/vikrant1123/Nex-N2.5-mini-Uncensored-APEX-GGUF)
- [Ternary Bonsai 2 27B PQ2_0](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) and [Kotoba refusal-steering derivative](https://huggingface.co/com-kotobalabs/Ternary-Bonsai-2-27B-Refusal-Steering-GGUF)

The source cards describe different artifacts and ownership. The model measurements here do not imply that the upstream model repositories themselves performed or endorsed these tests.
