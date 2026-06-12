"""Modal-compatible class decorators: @enter / @exit / @method.

These are module-level decorators (same as Modal). The actual class
registration is done by ``App.cls`` in :mod:`kotoba_murakumo.app`; these
decorators only mark the methods so ``App.cls`` can find them.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_ENTER_MARK = "__kotoba_murakumo_enter__"
_EXIT_MARK = "__kotoba_murakumo_exit__"
_METHOD_MARK = "__kotoba_murakumo_method__"


def enter() -> Callable[[F], F]:
    """Mark a method as the cold-start hook (Modal's ``@enter``)."""
    def deco(fn: F) -> F:
        setattr(fn, _ENTER_MARK, True)
        return fn
    return deco


def exit() -> Callable[[F], F]:  # noqa: A001 (Modal name)
    """Mark a method as the shutdown hook (Modal's ``@exit``)."""
    def deco(fn: F) -> F:
        setattr(fn, _EXIT_MARK, True)
        return fn
    return deco


def method() -> Callable[[F], F]:
    """Mark a method as a remotely-callable RPC entry (Modal's ``@method``)."""
    def deco(fn: F) -> F:
        setattr(fn, _METHOD_MARK, True)
        return fn
    return deco


def is_enter(fn: Any) -> bool:
    return bool(getattr(fn, _ENTER_MARK, False))


def is_exit(fn: Any) -> bool:
    return bool(getattr(fn, _EXIT_MARK, False))


def is_method(fn: Any) -> bool:
    return bool(getattr(fn, _METHOD_MARK, False))
