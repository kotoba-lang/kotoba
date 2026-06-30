# kotoba-langgraph-echo

Smallest possible **kotoba WASM LangGraph actor** — returns the input `prompt`
verbatim. Deterministic liveness probe / canonical clean example of the
actor-as-kotoba-WASM pattern. Port of kotodama's Python layer now hosted in
`kotoba-lang/kotodama-py`.

## Graph
```
START → echo → END        # _echo: {"response": state["prompt"]}
```

## Build
```sh
cd 40-engine/kotoba
export PATH="$PWD/../../.venv/bin:$PATH"
export KOTOBA_SITE_PKG="$PWD/../../.venv/lib/python3.12/site-packages"
./scripts/build-pywasm.bb examples/kotoba-langgraph-echo/agent.py
# → agent.wasm (~18 MB)
```

## Deploy + run (verified on live :8077, 2026-05-30)
Use the generic helper (`/tmp/deploy_actor.py`) or the recipe in
`../kotoba-langgraph-aria/README.md`. Two node-side gotchas it handles:
1. unique `agent_did` per actor (ProgramStore caches by
   `program_cid=did/wasm/{agent_did}`, ignoring submitted bytes);
2. encode `ctx_cbor` with `kotoba_langgraph._cbor.dumps` (the guest's `_cbor.loads`
   mis-decodes `cbor2` nested maps).

```sh
.venv/bin/python /tmp/deploy_actor.py \
  40-engine/kotoba/examples/kotoba-langgraph-echo/agent.wasm \
  '{"prompt":"hello kotoba wasm"}'
```

Verified result:
```
gas: 11
OUTPUT: {"response": "hello kotoba wasm"}
```

## Status
✅ Built, deployed, and run in-WASM on `:8077`; output `response == prompt` confirmed.
