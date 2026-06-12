"""Active-App context shared by App, Function, and llm (avoids import cycles).

``llm.invoke`` needs a node client but takes no client argument (Modal-shaped).
We resolve it from the App that is "active" — set inside ``Function.local(...)``
and ``with app.run_local():``. A contextvar keeps this correct across threads
and asyncio tasks.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from ._app import App
    from ._function import Function

from ._errors import NoActiveAppError

_active_app: "contextvars.ContextVar[Optional[App]]" = contextvars.ContextVar(
    "kotoba_modal_active_app", default=None
)
# The Function whose body is currently executing — lets llm.invoke pick up the
# function's max_new_tokens default without threading it through every call.
_active_fn: "contextvars.ContextVar[Optional[Function]]" = contextvars.ContextVar(
    "kotoba_modal_active_fn", default=None
)


def active_app() -> "App":
    app = _active_app.get()
    if app is None:
        raise NoActiveAppError(
            "no active kotoba_modal App. Use Function.local(...), "
            "`with app.run_local():`, or call app.client.infer(...) directly."
        )
    return app


def active_fn() -> "Optional[Function]":
    return _active_fn.get()


@contextlib.contextmanager
def activate(app: "App", fn: "Optional[Function]" = None):
    t_app = _active_app.set(app)
    t_fn = _active_fn.set(fn)
    try:
        yield app
    finally:
        _active_fn.reset(t_fn)
        _active_app.reset(t_app)
