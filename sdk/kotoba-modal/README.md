# kotoba-modal

A **Modal-shaped** authoring SDK for kotoba nodes. Write functions with the
ergonomics you know from [modal.com](https://modal.com) — `App`,
`@app.function`, `.remote()`, `.map()` — and have them **execute on the kotoba
node as WASM components** (py→wasm→kotoba). Inference runs on the **Murakumo Mac
mini fleet** (ADR-2605202345 / ADR-2605215000).

```python
import kotoba_modal as modal

app = modal.App("infer")

@app.function(gpu="mac-mini")        # gpu hint → routed to the fleet
def generate(prompt: str) -> str:
    return modal.llm.invoke(prompt)

generate.remote("hello")  # body runs ON the node as WASM (invoke.run)
generate.local("hello")   # body runs in CPython for dev (llm → HTTP infer.run)
```

## Execution model: py→wasm→kotoba

The designed execution path is the kotoba-node WASM component model (the same one
the `kotoba-langgraph-*` examples use):

```
@app.function def body
      │  componentize-py  (build)
      ▼
  WASM component  (exports run(ctx-cbor) -> result<list<u8>>)
      │  invoke.run  {program_cid | wasm_b64, ctx_b64}
      ▼
  kotoba node  → runs body → llm.invoke binds to kotoba:kais/llm WIT import
```

`.remote()` and `.local()` are **not** equivalent:

| | `.remote()` | `.local()` |
|---|---|---|
| where the body runs | on the node, as WASM | in your CPython process |
| `modal.llm.invoke` binds to | `kotoba:kais/llm` WIT import | HTTP `infer.run` |
| dispatch | `invoke.run` | — |
| use for | production execution | development / tests |

The decorated body is the single source compiled for both worlds.

## What "Modal互換" means here

**Authoring compatibility, not wire compatibility.** The official Modal
client↔server transport is a closed, versioned gRPC protocol; reimplementing it
is an unbounded commitment and is out of scope. `kotoba_modal` gives you the
Modal *programming model* on kotoba's own dispatch surface. See
`docs/adr/2606060004-kotoba-modal-compatible-sdk.md`.

## The ctx contract (owned on both ends)

The call context flows through `invoke.run`'s opaque `ctx_b64`; the **guest**
defines its meaning. kotoba_modal owns *both* ends, so the contract is symmetric
and unit-tested in pure CPython (no wasm needed to verify it):

- **client** (`Function.remote`) → `_codec.encode_ctx` →
  `{"v":1,"fn","args","kwargs"}` (bundled CBOR, `_cbor.py` — standard CBOR, no
  third-party dep; readable by any kotoba host that implements the WIT
  contract).
- **guest** (`kotoba_modal.guest.handle_invoke`) → `decode_ctx` → calls the body
  → `encode_result` / `encode_error` → `{"v":1,"ok",...}`.
- **client** decodes the response with `decode_result` (raises `RemoteError` on
  an error envelope).

The componentize-py guest's `WitWorld.run` is a one-liner over this glue. Note
the module-scope imports: componentize-py's static analysis does **not** follow
lazy imports, so the glue modules must be imported at module scope or the built
component traps at call time with `ModuleNotFoundError` (the same reason the
`kotoba-langgraph-*` examples carry `# noqa: F401` imports):

```python
import wit_world
import wit_world.imports.llm          # bind kotoba:kais/llm
import kotoba_modal.guest             # noqa: F401  — bundle the glue
import kotoba_modal._codec            # noqa: F401
import kotoba_modal._cbor             # noqa: F401
from kotoba_modal.guest import handle_invoke
from my_app import generate

class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, generate)
```

> This `WitWorld` wrapper is **not auto-generated**: `_build.build_component`
> shells out to your `build-pywasm.bb` against the entry module as-is, so the
> entry module must already define this `run` export. Emitting the wrapper
> automatically is a follow-up.

## Building the component (bundled toolchain)

The py→wasm build is **bundled**: `wit/world.wit` (the `kotoba-node` world) and
`scripts/build-pywasm.bb` ship with the package and drive `componentize-py`.

```bash
pip install -e '.[build]'          # componentize-py
COMPONENTIZE_PY=componentize-py \
  scripts/build-pywasm.bb examples/guest_component.py -o generate.wasm
# → "Component built successfully"  (a real kotoba-node WASM component)
```

A guest entry is a Python module defining `class WitWorld` over the glue (see
`examples/guest_component.py`); the build has been verified end-to-end (the
`test_build_sample_component_compiles` integration test compiles it for real when
componentize-py is installed).

`invoke.run` **always requires the component bytes** — there is no by-CID
program lookup on this path (the node returns `400 "wasm_b64 required for wasm
programs"` otherwise), and `program_cid=` is only optional metadata forwarded to
the node, **not** a dispatch shortcut. `.remote()` obtains the bytes in this
order:

1. `@app.function(wasm=b"…")` / `@app.function(wasm_path="generate.wasm")` — a
   pre-built component (no build step at call time).
2. otherwise build via the bundled `scripts/build-pywasm.bb` (used automatically
   when `componentize-py` is resolvable), or an explicit
   `KOTOBA_PYWASM_BUILD` / `builder=`, invoked as `<script> <entry.py> -o
   <out.wasm>` and sent as `wasm_b64`.
3. if neither is available → `ToolchainNotFound`.

`.remote()` also requires a valid `agent_did` (the node's `validate_did` rejects
empty / non-`did:` values) — set `KOTOBA_AGENT_DID` or `App(agent_did=…)`.

> **Node feature requirement:** `invoke.run` is compiled only when the node is
> built with the `wasm-runtime` feature. A lean node build serves a stub that
> rejects the call regardless of the client. `.local()` (HTTP `infer.run`) does
> not need it.

For development without the toolchain, use `.local()`.

## Configuration

| env | meaning |
|---|---|
| `KOTOBA_NODE_URL` | base URL of the kotoba node (required) |
| `KOTOBA_OPERATOR_TOKEN` | operator JWT — `Authorization: Bearer` (sub == operator DID) |
| `KOTOBA_INTERNAL_SECRET` | `x-internal-trust` secret — direct LAN/pod access only |
| `KOTOBA_AGENT_DID` | default agent DID for invokes |
| `KOTOBA_PYWASM_BUILD` | path to the py→wasm build script |

## Install & test

```bash
pip install -e '.[dev]'    # editable + pytest + coverage + componentize-py
pytest                     # 60 tests, pure CPython (no network)
                           # incl. a real wasm-build integration test
                           # (skipped if componentize-py is absent)
python examples/infer_app.py "hello"   # uses .local()
```

## Verified vs. unverifiable here

- **Verified against the host contract**: wasm bytes are always required,
  `agent_did` must be a bare DID, `ctx_b64` is passed to the guest `run`
  verbatim, and `output_b64` is the guest's raw return. The request/response
  **shapes** and these guards are tested in CPython via a node simulator, plus
  the ctx CBOR contract end-to-end (client encode ↔ guest `handle_invoke` decode
  ↔ client decode), auth headers, the `ToolchainNotFound` gate, and the HTTP
  `llm` seam.
- **Build verified** (with `pip install '.[build]'`): the bundled
  `wit/` + `scripts/build-pywasm.bb` compile `examples/guest_component.py` to a
  real kotoba-node WASM component (`test_build_sample_component_compiles`).
- **Still unverifiable here (no live node):** real on-node WASM *execution* and
  the `kotoba:kais/llm` WIT binding at runtime — they need a running
  `wasm-runtime` node. The simulator runs the body in CPython, so it tests the
  *client* contract, not the WASM runtime.

## Limitations (MVP, v0.1.0)

- **Not wire-compatible** with the Modal CLI/SDK (by design).
- `.map()` is sequential; each call dispatches independently to the node.
- No `Volume` / `Dict` / `Queue` / `Sandbox` — kotoba's Vault / QuadStore /
  Journal are the native equivalents; bindings TBD.
