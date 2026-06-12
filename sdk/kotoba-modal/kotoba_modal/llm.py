"""``modal.llm`` — call inference from inside a function body, in both worlds.

The same body line `modal.llm.invoke(prompt)` binds to a different backend
depending on where the body runs:

  * **inside the WASM guest** (`.remote()` → componentized body on the node):
    the `kotoba:kais/llm` WIT import (`llm.infer(model_cid, prompt_bytes)`), which
    the host routes to the node's engine / Murakumo fleet.
  * **in CPython** (`.local()` / dev): HTTP `infer.run` via the active App's
    client.

The WIT branch only resolves inside a componentize-py guest (the `wit_world` /
`kotoba_kais` bindings exist there, not in plain CPython), so only the HTTP
branch is exercised by this repo's tests; the WIT branch is a binding seam.
"""

from __future__ import annotations

from typing import List, Optional, Union

from ._context import active_app, active_fn

Messages = Union[str, List[dict]]


def _wit_llm():
    """Return the kotoba:kais/llm WIT import if running inside a guest, else None."""
    try:
        from wit_world.imports import llm as _l  # type: ignore

        return _l
    except Exception:
        try:
            from kotoba_kais.imports import llm as _l  # type: ignore

            return _l
        except Exception:
            return None


def invoke(
    messages: Messages,
    *,
    model_cid: str = "",
    max_new_tokens: Optional[int] = None,
) -> str:
    """Run a prompt (or chat-style message list) through inference.

    `model_cid` is a kotoba Vault CID; "" lets the host use its configured
    default (MURAKUMO_DEFAULT_MODEL). `max_new_tokens` falls back to the
    enclosing `@app.function(max_new_tokens=...)` default (HTTP path only).
    """
    prompt = _to_prompt(messages)

    wit = _wit_llm()
    if wit is not None:  # in-component: kotoba:kais/llm
        out = wit.infer(model_cid, prompt.encode("utf-8"))
        return out.decode("utf-8") if isinstance(out, (bytes, bytearray)) else str(out)

    # CPython / dev: HTTP infer.run via the active App.
    if max_new_tokens is None:
        fn = active_fn()
        if fn is not None:
            max_new_tokens = fn.max_new_tokens
    return active_app().client.infer(prompt, max_new_tokens=max_new_tokens)


# LangChain/Modal-style alias.
generate = invoke


def _to_prompt(messages: Messages) -> str:
    if isinstance(messages, str):
        return messages
    parts: List[str] = []
    for m in messages:
        if isinstance(m, dict):
            parts.append(str(m.get("content", "")))
        else:
            parts.append(str(getattr(m, "content", m)))
    return "\n".join(p for p in parts if p)
