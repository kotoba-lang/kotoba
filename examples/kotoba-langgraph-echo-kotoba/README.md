# kotoba-langgraph-echo-kotoba

The **Kotoba-WASM port** of the componentize-py LangGraph echo agent
([`../kotoba-langgraph-echo/agent.py`](../kotoba-langgraph-echo/agent.py)) —
the migration path off `py/kotoba_langgraph`. The same actor, compiled by the
`kotoba wasm` toolchain instead of bundling CPython.

## Graph

```
START → echo → END        ; echo: {"response": state["prompt"]}
```

`agent.kotoba` mirrors the Python actor piece by piece:

| Python (`py/kotoba_langgraph`)                  | Kotoba (`agent.kotoba`)                        |
|--------------------------------------------------|------------------------------------------------|
| `StateGraph(EchoState)` + `add_node`/`add_edge`  | `defgraph echo-graph :entry/:nodes/:edges`     |
| `_echo` returns partial `{"response": prompt}`   | `echo` returns a partial update map            |
| reducer-free TypedDict channels (override)       | `:state {:prompt :override :response :override}` |
| `handle_invoke` CBOR `InvokeContext` decode      | `ctx-prompt` / `ctx-thread-id` (`cbor-map-seek`) |
| `thread_id = args.get("thread_id", session_cid)` | `ctx-thread-id` fallback chain                 |
| `input_state = args.get("input", args)`          | `ctx-prompt-via-input` → `ctx-prompt-direct`   |
| `json.dumps(result)` → CBOR `{"ok": json}`       | `state-json` + `ok-result` (`cbor-enc-*`)      |
| `KotobaCheckpointer.save` → kqe quad             | `ckpt-save!` → `kqe-assert!`                   |

Both emit the identical wire bytes: input is the CBOR `InvokeContext`
(`{"graph", "session_cid", "args": {"input": {"prompt"}, "thread_id"}}`),
output is CBOR `{"ok": "{\"prompt\": \"…\", \"response\": \"…\"}"}` (including
`json.dumps`' default separators and key order), and the checkpoint quad is
`lgraph/ckpt / <thread_id> / state / {"Text": <JSON state>}`.

## Build + run

No componentize-py, no venv, no 18 MB CPython bundle. The public build path is
Kotoba source → `kotoba wasm`; the regression test compiles the example source
itself and drives it through the runtime's real `WasmExecutor`:

```sh
kotoba wasm build agent.kotoba -o agent.wasm
cargo test -p kotoba-clj --test langgraph_echo
```

(`kotoba wasm` / `compile_kais_component_str(prelude() + agent.kotoba)` →
kotoba-node component → `WasmExecutor::execute` → `run(ctx_cbor)`.)

## Size

| build | component size |
|---|---|
| componentize-py (`../kotoba-langgraph-echo/agent.wasm`) | **18,481,059 bytes (~18 MB)** |
| Kotoba wasm (this agent + full prelude)                 | **4,811 bytes (~4.7 KB)** |

≈ **3,840× smaller**, because the Kotoba source compiles to wasm directly
instead of shipping an interpreter.

## Subset gaps vs the Python actor

Faithful except where the current Kotoba/WASM subset can't express it yet:

- **No JSON string escaping** — `state-json` splices the prompt verbatim; a
  prompt containing `"` or `\` would produce different (invalid) JSON than
  `json.dumps`. Fine for the liveness-probe role.
- **Checkpointer `load` is not implemented** — `KotobaCheckpointer.load` parses
  the persisted JSON back into a dict; the subset has no JSON parser, so prior
  thread state is not rehydrated. For the echo graph this is semantically
  invisible (both channels are overwritten every turn); a stateful port would
  persist the state as CBOR (decodable in-guest via `cbor-map-seek`) instead of
  JSON. `save` (the `kqe-assert!` write) is fully implemented.
- **No `{"err": traceback}` path** — Python wraps node exceptions into an
  `{"err": …}` CBOR result; the compiled subset has no exceptions (a trap
  surfaces as the executor's own error), so only the `{"ok": …}` shape is
  emitted.
- **`MAX_STEPS` / interrupts / `stream()`** — graph.py's step cap and streaming
  API have no counterpart; the `defgraph` runner loops until the `:end`
  terminator (irrelevant for a single-node linear graph).
