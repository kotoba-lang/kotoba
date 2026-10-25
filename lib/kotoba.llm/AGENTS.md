# etzhayyim-project-llm — llm.etzhayyim.com

**LLM inference gateway — currently no backend.** The Linode GPU Ollama path was pruned 2026-04-22 (LKE GPU node pool removed, `inference` namespace deleted). CF Workers AI + OpenRouter fallbacks were pruned earlier (2026-04-15). Callers hitting `/v1/chat/completions` now receive a structured 200 with `finish_reason: "error:inference_unavailable"` and empty content, so upstream UIs can render honest state rather than timing out. Murakumo (hayate + qwen3.5-4b translation) is unaffected — that path is separate in host-sdk `llm.ts`.

## Status

| Path | State |
|---|---|
| `/v1/chat/completions` (non-stream) | 200 `error:inference_unavailable` |
| `/v1/chat/completions` (stream) | identical error |
| Credits gate | still enforced (`x-credits-did` required unless `x-kotodama-verified: true`) |
| hayate-v4/v5 → Murakumo | active |
| Translation (qwen3.5-4b) → Murakumo direct | active (i18n.etzhayyim.com → murakumo.etzhayyim.com) |

To restore inference, re-wire a backend inside `runInference()` in `src/app.ts` and redeploy. The retained `pvc/ollama-models` 50Gi Linode block-storage volume still has the pre-pulled gemma4:e2b/e4b models and can be re-mounted if a new GPU pool is added.

## Architecture (retained for reference, non-LLM paths still live)

```
App (host-sdk llm.ts)
  ├─ hayate-v4/v5 model → Murakumo (on-prem MLX fleet) — active
  ├─ translation (qwen3.5-4b) → Murakumo direct — active
  └─ other models      → llm.etzhayyim.com → [no backend] error:inference_unavailable
```

## Model Tier Strategy

| Tier | Model | Backend | Use Case | Cost |
|---|---|---|---|---|
| 0a GPU pod | `gemma4:e2b` | Ollama LKE GPU pod (`ollama.etzhayyim.com`) | heartbeat, shinka, react, general, simple, social, convo | $0 |
| 0b GPU pod | `gemma4:e4b` | Ollama LKE GPU pod (`ollama.etzhayyim.com`) | kyumei-koji, japanese, structured, extraction, json | $0 |

Both GPU pod models warm simultaneously in VRAM (OLLAMA_MAX_LOADED_MODELS=2, ~12 GiB / 20 GiB).
`gemma4:e2b` = exact Ollama equivalent of `@cf/google/gemma-4-e2b-it` (released 2026-04-02, Apache 2.0, 128K ctx).
`gemma4:e4b` replaces qwen3-30b CF routing for structured/japanese at zero cost.
Ollama 不達時は `finishReason: "error:ollama_unavailable"` を返す (no fallback)。

## Routing Rules

- `model: "hayate-v4"` or `"hayate-v5"` → Murakumo (MLX fleet, host-sdk llm.ts が routing)
- `use_case: "heartbeat"` → **gemma4:e4b** (Ollama, $0)
- `use_case: "shinka"` / `"react"` / `"general"` / `"simple"` / `"social"` / `"convo"` → **gemma4:e4b**
- `use_case: "kyumei-koji"` / `"extraction"` / `"json"` → **qwen3-30b** (Ollama, $0)
- `use_case: "japanese"` / `"structured"` → **gemma4:e4b**
- Default → **gemma4:e4b** (Ollama)

## Credits Gate

Credits service (credits.etzhayyim.com) への pre-check は **graceful degradation** — HTTP 402 (insufficient_balance) のみブロック。
credits service 不達・unknown method・その他エラーはスルー (credits は AT Protocol commit pipeline で事後請求)。

## Commands (6)

| Command | Description |
|---|---|
| `converse` | LLM converse (host-sdk compatible, role 0-3) |
| `chat_completions` | OpenAI-compatible chat completions (tools/tool_choice + SSE streaming 対応) |
| `list_models` | List available models with capabilities |
| `recommend_model` | Recommend model for use case |
| `health_check` | Ping all model endpoints |
| `verify_celler_ai` | 10-language multilingual voice AI verification (Celler integration test) |

## Integration

`@etzhayyim/kotodama-host-sdk` `llm.ts`:
- `llmAsk(prompt)` → Ollama Tier 0 (gemma4:e4b)
- `llmCall(system, user, "hayate-v5")` → Murakumo
- `agentConverseAsync(msgs, { use_case: "heartbeat" })` → Ollama Tier 0 gemma4:e4b
- `agentConverseAsync(msgs, { use_case: "kyumei-koji" })` → llm.etzhayyim.com Ollama qwen3-30b

**Key env vars:**
- `MURAKUMO_CHAT_URL = "http://ollama.etzhayyim.com/v1/chat/completions"` (llm.ts SSOT)
- `OLLAMA_URL = "http://172-236-133-64.ip.linodeusercontent.com"` (wrangler.jsonc `vars`, LLM Worker Tier 0 — Linode NB hostname; `ollama.etzhayyim.com` gray-cloud is intercepted by routing-gateway Worker for CF Worker subrequests)
- `EMBED_URL = "http://embed.etzhayyim.com"` (graph Worker, self-hosted TEI — CF AI fallback pruned)

## OpenAI-Compatible API

**`/v1/chat/completions`** — SSE streaming (`stream: true`) + non-streaming 両対応。外部ツール (Continue, Open WebUI 等) から直接利用可能。

```yaml
# Continue (VS Code) config.yaml
- name: LLM Gateway (Ollama)
  provider: openai
  apiKey: dummy
  model: gemma4:e4b
  apiBase: https://llm.etzhayyim.com/v1
```

## Build & Deploy

**account-level Worker (`etzhayyim-llm`)** — dispatcher `SERVICE_BINDING_DOMAINS` 経由。

```bash
cd appview/etzhayyim-wasm-llm-llm8cf4ai
# account-level Worker deploy (llm.etzhayyim.com route)
mkdir -p build && npx esbuild src/app.ts --bundle --outfile=build/worker.mjs --format=esm --platform=browser --target=es2022 --external:cloudflare:workers
pnpm wrangler deploy

# App Worker deploy (llm8cf4ai.etzhayyim.com) — frontend migrated from
# SvelteKit to ClojureScript (2026-09-08, see appview/etzhayyim-wasm-llm-llm8cf4ai/cljs/
# and that dir's wrangler.jsonc header comment). The `--no-svelte` flag
# below is stale now that svelte/ is gone; this line and whatever
# `etzhayyim deploy` actually does with it are UNVERIFIED by this
# migration (the tool itself is not in this repo checkout).
etzhayyim deploy --smoke-url https://llm8cf4ai.etzhayyim.com/health
```
