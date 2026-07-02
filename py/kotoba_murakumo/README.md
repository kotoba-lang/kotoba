# kotoba_murakumo

Modal-compatible Python facade for the **etzhayyim Murakumo Mac mini fleet**.

Backed by [kotoba](../../) (canonical religious-corp storage substrate per
ADR-2605262130). Inference routes exclusively to the Murakumo fleet endpoints
declared in `50-infra/murakumo/fleet.toml`, never to commercial GPU rental
(constitutional invariant per ADR-2605215000 + ADR-2605262200 §2(i)(2)).

**Status**: R1.1 live dispatch. See ADR-2605282000.

## Usage

```python
from kotoba_murakumo import App, gpu

app = App(
    name="my-inference",
    fleet="50-infra/murakumo/fleet.toml",
    did="did:web:my-actor.etzhayyim.com",
)

# LLM via LiteLLM gateway (judah :4000) — routes by model name
@app.function(gpu=None, model="gemma4:e4b")
def summarize(text: str) -> str: ...

# Heavy LLM via EVO-X2 ollama (100.75.169.8:11434)
@app.function(gpu=gpu.EvoX2(prefer="ollama"), model="llama3.3:70b")
def deep_analyze(prompt: str) -> str: ...

# Own-node ollama gemma4:e4b (fast, local — picks a specific tribe)
@app.function(gpu=gpu.MacMini(node="judah"), model="gemma4:e4b")
def quick_classify(text: str) -> str: ...

# Live dispatch
result = summarize.remote("...")                # sync
result = await summarize.remote_async("...")    # async
handle = summarize.spawn("...")                 # fire-and-forget → handle.get()
results = list(summarize.map(corpus))           # batch (thread pool)
async for tok in summarize.stream("..."):       # SSE token stream
    print(tok, end="", flush=True)
```

## Modal compatibility

```python
# Drop-in for many Modal apps — change one import line:
import kotoba_murakumo.modal_compat as modal

stub = modal.App("my-inference", fleet="50-infra/murakumo/fleet.toml")

@stub.function(gpu="A10G")          # → routed to EVO-X2 with honest warning
def f(prompt: str) -> str: ...
```

What works in R1.1:
`App`, `@app.function`, `@app.cls`, `@enter`, `@exit`, `@method`, `Image`
identity ops, `Volume.from_name`, `Secret.from_name` / `from_dict`,
`gpu.{EvoX2, MacMini, WebGPU, T4, L4, A10G, A100, H100}`, `.local()`,
`.remote()`, `.remote_async()`, `.spawn()` (with `FunctionCall.get()`),
`.map()` (sync, ordered or as-completed), `.starmap()`, `.stream()` (async
generator over OpenAI SSE).

What raises `MurakumoCompatNotImplemented`:
`Image.from_registry` (commercial registries forbidden per Charter Rider
§2(c)+(e)), `Image.from_dockerhub`, `web_endpoint`, `asgi_app`,
`fastapi_endpoint`, `Sandbox`, `Queue`, `Dict`, `Function.from_dockerhub`,
ComfyUI image-gen dispatch (lands R1.2), `gpu.WebGPU()` dispatch (lands R2
via `kotoba-vm` WASM Component).

What is **permanently** forbidden (never lands):
Any call to `modal.com` / `api.modal.com`, any `Image.from_registry` of a
commercial container registry, any silent fallback to a vendor not in
`fleet.toml`. CI grep gate at
`70-tools/scripts/lint/verify_no_modal_labs_calls.py` enforces this.

## Charter Rider §2 scan

Every `.remote()` runs the Charter Rider §2(a)-(h) scanner (bound to the
canonical `etzhayyim_organism.sensors.charter_rider.scan` when available,
otherwise a local fallback) on both the input prompt and the returned text.

Set `KOTOBA_MURAKUMO_CHARTER_ENFORCE=1` to flip from advisory to enforce —
any severity ≥ `major` raises `kotoba_murakumo.exceptions.CharterViolation`
**before** the result is returned to the caller (constitutional invariant
per ADR-2605192200 + ADR-2605282000).

## Invocation log

Every dispatch appends one NDJSON line to
`~/.kotoba_murakumo/invocations.ndjson` (override with
`KOTOBA_MURAKUMO_LOG=...`):

```json
{"ts":"...","app":"my-inference","fn":"summarize","caller_did":"did:web:...",
 "endpoint":"http://100.113.200.45:4000","backend":"litellm-gateway",
 "model":"gemma4:e4b","prompt_chars":42,"result_chars":138,"latency_ms":312,
 "phase":"sync","charter_in":"clean","charter_out":"clean"}
```

R1.2 will promote this to an `com.etzhayyim.murakumo.invocation` Lexicon
record posted to the caller's PDS.

## Tests

```sh
# 42 unit tests (mocked HTTP via httpx.MockTransport) — fast, no network
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/

# 2 live-fleet smoke tests — skipped unless you're on the Murakumo LAN
KOTOBA_MURAKUMO_LIVE_FLEET=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` works around a global-site-packages
pydantic-core/pydantic version mismatch in the langsmith pytest plugin on
this dev box; harmless to remove if your env is clean.

## Trademark notice

Modal® is a registered trademark of Modal Labs Inc. This package is
API-compatibility only (Google v. Oracle 2021 API fair-use precedent —
analogous to ADR-2605261800 §D10 `nv_compat`). `kotoba_murakumo` does not
distribute Modal Labs code or contact Modal Labs servers, enforced
mechanically by the CI grep gate above.

## License

Apache-2.0 — see [`/LICENSE`](../../LICENSE).
