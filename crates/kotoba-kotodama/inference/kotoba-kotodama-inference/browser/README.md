# Browser inference

This directory is the browser entrypoint for `kotoba-kotodama-inference`.
The Rust crate builds to wasm and runs WebGPU kernels through `wgpu`.

The language-facing API is not JavaScript-first. The portable surface is CLJC
and is built on the existing `kotoba-lang/torch` + `kotoba-lang/num` stack:

- `torch` describes the neural/module graph as EDN data.
- `num` provides the tensor compute contract and the WGSL/WebGPU backend spec.
- `kotodama.inference.runtime` describes LLM sessions/generation as EDN data
  and carries both `:kotodama/model-graph` and `:kotodama/compute-backend`.
- `kotodama.inference.ports/IModelRuntime` is the injected host port. Browser
  hosts bind this to a `num` backend (`:num/wgsl`, `:num/webgpu`, or a
  host-provided `:num/webgl`) plus model artifacts; local hosts may bind native
  Rust inference.
- `kotodama.inference.core/llm-infer` is the host-side shape for kototama's
  `(llm-infer model prompt)` capability.

Backend policy:

- `:torch-transformer` is the primary runtime. It uses a torch-clj model graph
  and num-clj compute backend.
- `:webgpu` should use `:num/wgsl` or `:num/webgpu`.
- `:webgl` is a compatibility target only when a host provides `:num/webgl`.
- Rust `wgpu` browser kernels are WebGPU/WGSL.

CLJC example:

```clojure
(require '[kotodama.inference.core :as infer]
         '[kotodama.inference.runtime :as rt])

(def session
  (infer/load-model host-runtime
                    (rt/transformer "tiny-random-gpt2"
                                    {:kotodama/backend :webgpu
                                     :kotodama/compute-backend :num/wgsl})))

(infer/generate host-runtime session "hello" {:kotodama/max-new-tokens 16})
```

Build the wasm package:

```sh
wasm-pack build --target web --no-default-features --out-dir pkg-web
```

Use the client from an app:

```js
import { KotodamaInferenceClient } from "./browser/kotodama-inference-client.js";

const inference = new KotodamaInferenceClient();
await inference.init();

const caps = await inference.probe();
console.log(caps);

const result = await inference.matmul(
  new Float32Array([1, 2, 3, 4]),
  new Float32Array([1, 0, 0, 1]),
  2,
  2,
  2,
);
console.log([...result.output]);
```

For real model inference, fetch weights into the worker:

```js
await inference.loadWeightsUrl("/models/hayate-v5/model.safetensors");
const { logits } = await inference.forward(new Uint32Array([1, 42, 128]));
```

The app must be served from a secure context (`https://` or `localhost`) and the
browser must expose WebGPU (`navigator.gpu`). The worker intentionally owns the
model weights and GPU device; kotoba guest wasm should call this through the
`kotoba:kais/llm@0.1.0` host capability instead of touching WebGPU directly.

Live local-model verification:

```sh
clojure -M:verify-maturity
clojure -M:verify-torch-num
clojure -M:verify-gguf
clojure -M:verify-maturity-run
clojure -M:verify-maturity-run --include-local-model
clojure -M:verify-ollama
```

`verify-maturity` checks that the coverage/maturity gate is wired to the
expected artifacts and commands. `verify-torch-num` proves a minimal torch-clj
graph can be executed by a host backend using num-clj tensor ops.
`verify-gguf` resolves the local `gemma4:e4b` Ollama model to its GGUF blob and
reads the artifact header/metadata directly, including Gemma architecture,
tensor count, model dimensions, tokenizer merge-table presence, tensor type
distribution, required weight shapes, payload byte windows, and F32 weight
samples.
`verify-maturity-run` executes the required gates, and only runs the local
`gemma4:e4b` model when `--include-local-model` is passed. `verify-ollama`
expects a local Ollama model named `gemma4:e4b`.
It verifies the model identity (`gguf`, `gemma4`, `8.0B`, `Q4_K_M`, and the
expected digest) before generation. Ollama is only a local host adapter for
proving the `IModelRuntime` generate boundary with a real model; it is not the
portable inference foundation.
