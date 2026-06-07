"""Public exception types for kotoba_murakumo.

These are part of the API contract: callers MAY catch them; the package will
not change their hierarchy or class names without an ADR amendment.
"""

from __future__ import annotations


class MurakumoError(Exception):
    """Base class for all kotoba_murakumo errors."""


class FleetUnreachable(MurakumoError):
    """Raised when no fleet endpoint can satisfy a routing decision.

    R0+ surfaces the attempted endpoint chain rather than silently substituting
    another vendor (ADR-2605282000 N4).
    """

    def __init__(self, message: str, *, attempted: list[str] | None = None) -> None:
        super().__init__(message)
        self.attempted = list(attempted) if attempted else []


class CharterViolation(MurakumoError):
    """Raised when Charter Rider §2(a)-(h) scan finds a major-severity issue.

    R0 hook is advisory; R1 flips to enforce per ADR-2605282000 §"Charter Rider
    §2 scan hook".
    """

    def __init__(self, message: str, *, side: str, severity: str) -> None:
        super().__init__(message)
        self.side = side
        self.severity = severity


class MurakumoCompatNotImplemented(MurakumoError, NotImplementedError):
    """Raised when a Modal-API surface is intentionally unsupported on Murakumo.

    Examples (R0): ``Image.from_registry`` (commercial registry forbidden),
    ``web_endpoint`` (use yoro / kotoba-server XRPC instead), ``Sandbox`` (no
    container runtime in fleet — use WASM Component).

    Carries the canonical constitutional / routing reason so callers can decide
    whether to refactor or escalate.
    """

    def __init__(self, surface: str, reason: str) -> None:
        super().__init__(f"{surface}: {reason}")
        self.surface = surface
        self.reason = reason
