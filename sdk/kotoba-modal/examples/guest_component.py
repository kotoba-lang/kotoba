"""Sample kotoba_modal guest component (py→wasm→kotoba).

Build to a kotoba-node WASM component:

    COMPONENTIZE_PY=.venv/bin/componentize-py \
        scripts/build-pywasm.bb examples/guest_component.py -o /tmp/generate.wasm

The resulting component exports `run(ctx-cbor) -> result<list<u8>>` and is
dispatched by the node via `invoke.run`. From the client side:

    @app.function(wasm_path="/tmp/generate.wasm")
    def generate(prompt: str) -> str: ...
    generate.remote("hello")        # runs THIS component on the node

The module-scope imports are required: componentize-py's static analysis does
not follow lazy imports, so the glue (and the llm WIT import) must be bundled
explicitly or the component traps at call time with ModuleNotFoundError.
"""

import wit_world
import wit_world.imports.llm  # noqa: F401 — bind kotoba:kais/llm
import kotoba_modal.guest  # noqa: F401 — bundle the glue
import kotoba_modal._codec  # noqa: F401
import kotoba_modal._cbor  # noqa: F401

from kotoba_modal import llm
from kotoba_modal.guest import handle_invoke


def generate(prompt: str) -> str:
    # In-guest, modal.llm.invoke binds to the kotoba:kais/llm WIT import.
    return llm.invoke(prompt)


class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, generate)
