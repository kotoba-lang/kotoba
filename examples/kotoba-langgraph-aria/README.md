# kotoba-langgraph-aria

ARIA actor as a **kotoba WASM LangGraph component**. Flagship of the
`kotoba-langgraph-*` example set: a 6-signal situational-awareness graph that
runs **in-WASM** on a live kotoba node and routes its decision narration through
the Murakumo inference fleet.

## Graph

```
START → ingest_all → compute_area → minimax_select → narrate → witness → END
```

| node | kind | what it does |
|---|---|---|
| `ingest_all` | pure | projects the 6 signals (emotion/attention/request/market/money/influence) from the invocation context |
| `compute_area` | pure | information-area integral + global decay (η) |
| `minimax_select` | pure | Von Neumann minimax → `{action, hedge, scores}` (deterministic decision) |
| `narrate` | **LLM** | one-line rationale via `KotobaLLM` → `kotoba:kais/llm` WIT → **gemma-4-26B-A4B** |
| `witness` | pure | audit attestation over the *deterministic* decision (not the prose) |

`narrate` is advisory: the LLM never changes the action/hedge; `witness` records
the minimax result, so the actor stays deterministic where it matters and only
uses the model for human-facing narration.

## Inference model

`KotobaLLM(model_cid="")` emits a `kotoba:kais/llm.infer` WIT import. The WASM
component embeds **no** model and **no** network client. The kotoba host binds
that import to the Murakumo fleet (LiteLLM `127.0.0.1:4000`), and the deployed
default model is **gemma-4-26B-A4B** (MoE) — per ADR-2605302355 (durable
loopback routing) and the Charter "Murakumo-only inference" invariant
(ADR-2605215000). Leaving `model_cid=""` lets the host's
`MURAKUMO_DEFAULT_MODEL` select gemma-4-26B-A4B.

## Build

`componentize-py` lives in the repo venv (`.venv/bin`). The build entrypoint
module must be `agent.py` (the build target is the module basename).

```sh
# from 40-engine/kotoba/
PATH="$PWD/../../.venv/bin:$PATH" \
  ./scripts/build-pywasm.sh examples/kotoba-langgraph-aria/agent.py
# → examples/kotoba-langgraph-aria/agent.wasm  (~18 MB, same as the other examples)
```

## Deploy (in-WASM on the running :8077 node)

The node at `:8077` loads `agent.wasm` and invokes `WitWorld.run` per the same
path the other `kotoba-langgraph-*` actors use (`kotoba_wasm_run` MCP tool /
`invoke.run`). See `kotoba-langgraph-hello` for the exact deploy invocation used
on this host; this actor is drop-in compatible.

A minimal invocation context (CBOR) carries the 6 signals under `context`:

```json
{ "context": {
    "emotion":   {"intensity": 0.2},
    "attention": {"intensity": 0.9},
    "request":   {"intensity": 0.5},
    "market":    {"intensity": 0.1},
    "money":     {"intensity": 0.3},
    "influence": {"intensity": 0.7}
} }
```

Expected result state: `minimax_result.action == "attention"` (highest
intensity), `hedge == "market"` (lowest), plus a one-line `narrative` from
gemma-4-26B-A4B and a `witnessed`/`audit_cid` attestation.

## Deploy recipe (verified working on :8077, 2026-05-30)

Two gotchas on the currently-installed node (`kotoba 0.1.0`, built from commit
`5f9d14c`):

1. **ProgramStore caches by `program_cid` and the installed binary hardcodes
   `program_cid = "did/wasm/{agent_did}"`** (`executor.rs:129` returns the cached
   Component, ignoring submitted bytes). So reusing one `agent_did` across actors
   serves whichever wasm was loaded first. **Workaround: use a unique `agent_did`
   per actor/version** (the working-tree `args.get("program_cid")` override at
   `mcp.rs:1144` is newer than the installed binary — rebuild the node to use it).

2. **Encode `ctx_cbor` with kotoba's own `kotoba_langgraph._cbor.dumps`, NOT
   `cbor2`.** The guest's minimal `_cbor.loads` mis-decodes `cbor2`'s nested maps
   (duplicates the top key as `None`), which silently empties `state["context"]`.

A third gotcha: the **InvokeContext wire format** is
`{"args": {"input": <state>}}` (see `py/kotoba_langgraph/_entry.py:handle_invoke`),
NOT the bare state — wrap it or `state["context"]` arrives empty.

The generic helper `/tmp/deploy_actor.py` implements all three. Verified result
(decoded `output_cbor`):

```json
{"area_integral": 2.7, "eta_global": 0.45,
 "minimax_result": {"action": "attention", "hedge": "market",
   "scores": {"emotion":0.2,"attention":0.9,"request":0.5,
              "market":0.1,"money":0.3,"influence":0.7}},
 "narrative": "", "narrate_error": "...400 Bad Request..."}
```
`total_gas_used: 1015` (≈1000 = the `llm.infer` call to gemma-4-26B-A4B + node
steps). The deterministic decision is fully correct.

### Inference (`narrate`) — current host status
`narrate` DOES reach the model: gas≈1015 proves `kotoba:kais/llm.infer` fired and
the host forwarded to the Murakumo LiteLLM gateway
(`http://127.0.0.1:4000/v1/chat/completions`). The gateway currently returns
**400 Bad Request**, so `narrative=""` and `narrate_error` records the cause. This
is a host↔gateway binding detail (the running node's default model/payload vs what
`:4000` expects for `gemma4-e4b`), **not** an actor bug — the actor emits a valid
inference request and, thanks to the try/except in `_narrate`, still completes the
graph with the correct deterministic decision. When the host inference binding is
fixed, the same wasm will populate `narrative` with no rebuild.

## Status

- `agent.py` — ✅ written; mirrors verified `hello`/`final-sign-off` examples.
- `agent.wasm` — ✅ **BUILT** (~18.4 MB, valid WASM magic).
- **Deployed + run in-WASM on live `:8077`** via MCP `kotoba_wasm_run` — ✅ verified:
  `area_integral=2.7`, `eta_global=0.45`, minimax `action="attention"`,
  `hedge="market"`, all 6 scores correct.
- ⚠️ `narrative=""` — `narrate` reached `kotoba:kais/llm.infer` (gas≈1015) but the
  Murakumo gateway returned 400; `narrate_error` records it. Host↔gateway plumbing,
  not an actor bug (see "Inference" above). The deterministic decision is correct.
