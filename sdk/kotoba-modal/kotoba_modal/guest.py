"""Guest-side entry glue for kotoba_modal functions compiled to WASM.

A kotoba-node WASM component exports `run(ctx-cbor: list<u8>) -> result<list<u8>,
string>` (see `kotoba/crates/kotoba-runtime/wit/world.wit`). When a
`@app.function` body is componentized with `componentize-py`, the generated
`WitWorld.run` delegates to `handle_invoke` here, which decodes the same ctx
envelope the client (`Function.remote`) produced, calls the body, and encodes the
return.

Typical componentize-py boilerplate (the build emits something like this — it
needs the `wit_world` bindings, so it only imports/runs **inside** the guest):

    import wit_world
    import wit_world.imports.llm          # bind kotoba:kais/llm
    from kotoba_modal.guest import handle_invoke
    from my_app import generate           # the @app.function body

    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, generate)

`handle_invoke` itself is pure CPython and unit-tested against the client codec.
"""

from __future__ import annotations

from typing import Callable

from ._codec import decode_ctx, encode_error, encode_result


def handle_invoke(ctx_cbor: bytes, fn: Callable) -> bytes:
    """Decode the ctx envelope, call `fn`, return the encoded response envelope.

    Never raises across the WASM boundary: a body exception is captured into an
    error envelope so the host always gets well-formed `output` bytes.
    """
    try:
        _name, args, kwargs = decode_ctx(ctx_cbor)
    except Exception as e:  # malformed ctx — report, don't trap
        return encode_error(f"ctx decode failed: {type(e).__name__}: {e}")
    try:
        result = fn(*args, **kwargs)
    except Exception as e:
        return encode_error(f"{type(e).__name__}: {e}")
    try:
        return encode_result(result)
    except Exception as e:
        return encode_error(f"result encode failed ({type(e).__name__}: {e})")


def make_run(fn: Callable) -> Callable[[bytes], bytes]:
    """Return a `run(ctx_cbor) -> bytes` bound to `fn`, for the WitWorld export."""

    def run(ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, fn)

    return run
