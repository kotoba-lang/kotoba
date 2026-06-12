"""kotoba_modal app — execution model is py→wasm→kotoba.

    export KOTOBA_NODE_URL=http://127.0.0.1:8080
    export KOTOBA_OPERATOR_TOKEN=<operator-jwt>
    export KOTOBA_AGENT_DID=did:key:z...        # required for .remote()
    # only if the node sets KOTOBA_INTERNAL_SECRET (direct LAN/pod access):
    export KOTOBA_INTERNAL_SECRET=<secret>

Development (body runs in CPython; llm.invoke → HTTP infer.run on the fleet):

    python examples/infer_app.py "Explain CIDs in one sentence."

Production (body runs ON the node as a WASM component via invoke.run; the
llm.invoke inside the compiled body binds to the kotoba:kais/llm WIT import).
invoke.run always needs the component BYTES (no by-CID lookup) and a node built
with the `wasm-runtime` feature:

    # pre-built component (works without the build toolchain):
    @app.function(wasm_path="generate.wasm")
    # or build on demand:
    export KOTOBA_PYWASM_BUILD=/path/to/build-pywasm.bb
"""

import sys

import kotoba_modal as modal

app = modal.App("infer")


@app.function(gpu="mac-mini", max_new_tokens=256)
def generate(prompt: str) -> str:
    # Same body for both worlds: modal.llm.invoke binds to the WIT import when
    # compiled to WASM and run on the node, or to HTTP infer.run under .local().
    return modal.llm.invoke(prompt)


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Say hello from the Murakumo fleet."
    # .local() works without the wasm toolchain; .remote() runs on the node.
    print(generate.local(prompt))
