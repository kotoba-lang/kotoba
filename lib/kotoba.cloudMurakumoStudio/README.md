# murakumo-studio

A local inference desktop app (like [LM Studio](https://lmstudio.ai/)) built on
[`kotoba-lang/inference`](https://github.com/kotoba-lang/inference) — manage
local GGUF models, chat with them, expose an OpenAI-compatible local server for
other apps, and optionally announce your node to the
[murakumo](https://github.com/kotoba-lang/murakumo) fleet economy.

Design/architecture: `90-docs/adr/2607032700-murakumo-studio-local-inference-desktop-app.md`
in the [com-junkawasaki](https://github.com/com-junkawasaki/com-junkawasaki)
superproject (this repo is registered there via
[west](https://docs.zephyrproject.org/latest/develop/west/)).

## Status (v1, Phase 1 of the ADR's roadmap)

- **Chat generation is wired to real `kotoba-lang/inference` and verified
  working end-to-end — but output quality isn't there yet.** `/v1/chat/completions`
  calls `kotodama.inference.host.jvm/generate`
  ([inference#5](https://github.com/kotoba-lang/inference/pull/5), merged),
  a stable JVM entry point that loads the real GGUF, runs the full 42-layer
  CPU forward pass with a verified-correct KV-cache (identical output
  with/without — pure optimization, ~2.76× speedup measured upstream), and
  returns real generated text.

  **The incoherent-output note that stood here was measured on 2026-07-03 and
  is out of date.** It reported prompt "The capital of France is" →
  `"يبهيبهيبهيبه"` and an open deep-layer numerical drift. Upstream
  `kotoba-lang/inference` then landed the real Gemma4 PLE architecture, QK/V
  norms, NEOX RoPE, KV-sharing and the KV-cache through 2026-07-13.

  Re-measured 2026-08-13 against the same real `gemma4:e4b` GGUF, on a prompt
  outside inference's fixed probe:

  | | |
  |---|---|
  | prompt | `The largest planet in our solar system is` |
  | Ollama 0.31.1, greedy | `Jupiter` |
  | `kotodama.inference`, 42 real blocks, greedy | `" Jupiter. Jupiter is a gas"` |

  Coherent, factually right, and the first token matches Ollama exactly. This
  is one prompt at six tokens — evidence that the drift is gone, not a proof
  of logit-level parity across prompts, which inference's own maturity ledger
  still lists as incomplete.

  The `murakumo_studio/quality_note` field and the ⚠ banner should be revisited
  against this; they currently warn about a defect that has been fixed.
  If `kotodama.inference.host.jvm/generate` isn't resolvable at all (e.g. an
  older pinned `inference` build), chat requests get a clear `503`/`500`
  instead of crashing the sidecar; every other feature (model manager,
  download, fleet announce) works independently of that.
- **Generation is slow.** Measured 2026-08-13 with the Metal K-dot path, the
  six tokens above took 6.9–15.5 s each. That is NOT a clean benchmark: this
  workstation's load average moved between roughly 8 and 176 during the run,
  from unrelated processes. Treat it as "still seconds per token", not as a
  figure to compare against. The structural cost is unchanged — GGUF weights
  are re-read and dequantized per session (no weight caching or session reuse
  across chat turns; each `/v1/chat/completions` call opens and closes its
  own session). `Settings → max tokens`
  defaults to 32, not the more conventional 256, to keep replies from taking
  many minutes. GPU/WebGPU (ADR-2607032700 Phase 2) is the real fix.
- **Model management (local scan, HF Hub search/browse/resumable download),
  streaming chat (SSE, `/v1/chat/completions` with `stream: true` — real
  token-by-token via `:kotodama/on-token`, not simulated), local
  OpenAI-compatible server, and fleet announce are real and tested**
  (see `test/murakumo_studio/models_test.cljk`, live browser session testing
  of `src/murakumo_studio/ui.cljk` against the real running engine, and manual
  end-to-end verification of `src/murakumo_studio/engine.cljk` via `curl`,
  including a real ~6.5min/4-token generation run against the actual
  `gemma4:e4b` GGUF).
- **Fleet participation is announce-only.** Joining as a `murakumo.infer`
  compute worker (did:key/CACAO identity, actual shard-plan participation) is
  Phase 3, not implemented here.
- **Packaging is dev-only.** The app runs the JVM sidecar from a `clojure`
  binary on `PATH` and finds its source tree by walking up for `deps.edn`
  (`MURAKUMO_STUDIO_REPO` to override). Bundling a JVM into a distributable
  `.app`/`.dmg` is not attempted yet.
- **No Rust.** The Tauri crate was removed 2026-08-11. It registered no Tauri
  commands and its own header said "No business logic lives in Rust"; it opened
  a window and supervised the sidecar, both of which `kotoba-lang/shell` owns.
  What is left is `app.kotoba.edn`. `murakumo-studio.tauri` went with it —
  nothing required it, because the UI's whole data path is HTTP to 127.0.0.1.

## Architecture

```
kotoba-lang/shell (native window host + sidecar supervision, app.kotoba.edn)
 └─ webview: ClojureScript (shadow-cljs + reagent), kotoba-ui.core + appkit.core
      talks HTTP/JSON to ↓
JVM engine sidecar (src/murakumo_studio/engine.cljk, declared in app.kotoba.edn)
 ├─ murakumo_studio.models  — local GGUF scan (~/.murakumo-studio/models,
 │                             ~/.ollama/models) + HF Hub download
 ├─ murakumo_studio.fleet   — announce-only client for
 │                             gftdcojp/cloud-murakumo-fleet's /infer/* API
 └─ kotodama.inference.host.jvm/generate (kotoba-lang/inference, resolved
                             dynamically — see Status above)
```

## Prerequisites

- [Clojure CLI](https://clojure.org/guides/install_clojure) (`clojure`/`clj` on `PATH`)
- [nbb](https://github.com/babashka/nbb) for the task registry (`scripts/tasks.edn`).
  babashka is **not** required — it was retired repo-wide by ADR-2607173000.
- Node.js + npm, for shadow-cljs
- [`kotoba-lang/shell`](https://github.com/kotoba-lang/shell) for the desktop
  host (`bin/kotoba-shell app run`). No Rust toolchain.

If checked out inside the `com-junkawasaki` west superproject (sibling to
`orgs/kotoba-lang/inference`, `orgs/kotoba-lang/appkit`, etc.), use the `:dev`
alias to pick up `:local/root` sibling deps instead of the published git pins:
`kbb -M:dev:engine`, and set `MURAKUMO_STUDIO_ENGINE_ALIAS=:dev:engine`
before launching (the overrides a host may apply are declared in
`app.kotoba.edn` under `:sidecar/env-overrides`).

## Dev loop

```bash
npm install
npm run gui:watch &        # amu compile --target wasm32-browser → desktop/dist/js/main.js
kotoba-shell app run --target macos --manifest app.kotoba.edn --execute
```

`ui-css` — which generated `desktop/dist/vendor/kotoba-ui.css` — is
**unavailable**. It was a babashka-hosted `(load-file "scripts/gen_kotoba_ui_css.cljk")`
body, so the bb→nbb conversion could not express it and dropped it
(ADR-2608131600); the recovered form is in `scripts/tasks-complex.edn`. Restoring
it is a port, not a conversion. The one task that IS registered is
`kbb --backend sci scripts/run-task.cljk test` (6 tests / 14 assertions, measured 2026-08-13).

The host spawns the JVM engine sidecar on startup
(`kbb -M:engine`, `http://127.0.0.1:8721` by default — override with
`MURAKUMO_STUDIO_PORT`). You can also run the sidecar standalone for
frontend-only iteration:

```bash
kbb -M:engine    # or -M:dev:engine inside the west superproject
curl localhost:8721/health
```

## Tests

```bash
kbb -M:test     # murakumo_studio.models (local + Ollama manifest scan)
```

## License

TBD.
