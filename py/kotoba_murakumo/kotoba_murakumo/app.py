"""App — Modal-compatible Stub equivalent bound to one fleet + one caller DID."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

from . import cls as cls_mod
from . import economy as economy_mod
from .fleet import FleetView, load
from .function import Function, FunctionSpec
from .gpu import GpuSpec
from .image import Image
from .secret import Secret
from .volume import Volume

T = TypeVar("T", bound=type)


@dataclass
class App:
    """One Modal-compatible application.

    Parameters
    ----------
    name:
        Application name (free-form, used in logs).
    fleet:
        Path to ``fleet.toml``. Default resolves the repo-canonical path
        relative to the package install location; override for tests.
    did:
        Caller DID. R0 records it; R1 binds CACAO chain auth.
    gateway_node:
        Tribe name of the LiteLLM gateway node. Default ``"judah"`` per
        CLAUDE.md.
    """

    name: str
    fleet: str | Path = "50-infra/murakumo/fleet.toml"
    did: str = "did:web:unknown.etzhayyim.com"
    gateway_node: str = "judah"
    # R1.3b — economy injection points. None = use in-process defaults
    # (Tariff: economy.default_tariff(); balance: "unlimited" sentinel).
    # R1.3d-wiring will replace these with CACAO-verified XRPC pulls.
    tariff: economy_mod.Tariff | None = None
    balance_lookup: Callable[[str], int] | None = None

    _fleet_view: FleetView = field(init=False, repr=False)
    _functions: dict[str, Function] = field(init=False, default_factory=dict, repr=False)
    _classes: dict[str, type] = field(init=False, default_factory=dict, repr=False)
    _tariff: economy_mod.Tariff = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Load the fleet eagerly so misconfigurations surface at App construction,
        # not on the first .remote() call.
        self._fleet_view = load(self.fleet)
        self._tariff = self.tariff if self.tariff is not None else economy_mod.default_tariff()

    # ---- decorators ----------------------------------------------------------

    def function(
        self,
        *,
        gpu: GpuSpec | str | None = None,
        model: str | None = None,
        image: Image | None = None,
        timeout: int = 300,
        retries: int = 0,
        secrets: list[Secret] | None = None,  # noqa: ARG002 (R1)
        volumes: dict[str, Volume] | None = None,  # noqa: ARG002 (R1)
        max_cost_mkoto: int | None = None,
        concurrency_limit: int | None = None,  # noqa: ARG002 (R2 wiring)
    ) -> Callable[[Callable[..., Any]], Function]:
        """Modal-compatible ``@app.function(...)`` decorator.

        ``max_cost_mkoto`` is the Modal-equivalent per-call spend cap (R1.3b).
        When set, ``.remote()`` raises
        :class:`kotoba_murakumo.economy.BudgetExceeded` BEFORE HTTP if the
        pre-flight cost estimate exceeds the cap.

        ``concurrency_limit`` matches Modal's per-container cap; R2 wires it
        through the ThreadPoolExecutor used by ``.map()`` / ``.spawn()``.
        """
        def deco(fn: Callable[..., Any]) -> Function:
            spec = FunctionSpec(
                name=fn.__name__,
                fn=fn,
                gpu=gpu,
                model=model,
                image=image,
                timeout=timeout,
                retries=retries,
                max_cost_mkoto=max_cost_mkoto,
            )
            wrapped = Function(
                spec,
                app_name=self.name,
                caller_did=self.did,
                fleet=self._fleet_view,
                gateway_node=self.gateway_node,
                tariff=self._tariff,
                balance_lookup=self.balance_lookup,
            )
            self._functions[fn.__name__] = wrapped
            return wrapped
        return deco

    def cls(
        self,
        *,
        gpu: GpuSpec | str | None = None,
        image: Image | None = None,
        container_idle_timeout: int = 300,
        volumes: dict[str, Volume] | None = None,  # noqa: ARG002 (R1)
        secrets: list[Secret] | None = None,  # noqa: ARG002 (R1)
    ) -> Callable[[T], T]:
        """Modal-compatible ``@app.cls(...)`` decorator.

        R0 records the class and its @enter/@exit/@method markers. R1 will
        instantiate persistent containers per Modal semantics.
        """
        def deco(klass: T) -> T:
            enter_fns = [
                m for _, m in vars(klass).items()
                if callable(m) and cls_mod.is_enter(m)
            ]
            exit_fns = [
                m for _, m in vars(klass).items()
                if callable(m) and cls_mod.is_exit(m)
            ]
            method_fns = [
                m for _, m in vars(klass).items()
                if callable(m) and cls_mod.is_method(m)
            ]
            # Attach metadata for future container scheduling.
            setattr(klass, "__kotoba_murakumo_meta__", {
                "gpu": gpu,
                "image": image,
                "container_idle_timeout": container_idle_timeout,
                "enter": [f.__name__ for f in enter_fns],
                "exit": [f.__name__ for f in exit_fns],
                "method": [f.__name__ for f in method_fns],
            })
            self._classes[klass.__name__] = klass
            return klass
        return deco

    def local_entrypoint(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Modal-compatible ``@app.local_entrypoint()`` — no-op decorator at R0."""
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn
        return deco

    # ---- introspection -------------------------------------------------------

    @property
    def fleet_view(self) -> FleetView:
        return self._fleet_view

    def registered_functions(self) -> list[str]:
        return sorted(self._functions)

    def registered_classes(self) -> list[str]:
        return sorted(self._classes)

    # ---- economy (R1.3b — see ADR-2605282100) -------------------------------

    def balance(self, did: str | None = None) -> int:
        """Return the caller's current mKOTO balance.

        R1.3b — defaults to "unlimited" (returns 2**62) when no
        ``balance_lookup`` is wired. R1.3d-wiring will replace this with a
        CACAO-verified XRPC call to ``com.etzhayyim.kotoba.economy.balance``.
        """
        target = did or self.did
        if self.balance_lookup is not None:
            return self.balance_lookup(target)
        return 2 ** 62

    def get_tariff(self) -> economy_mod.Tariff:
        """Return the active tariff schedule.

        R1.3b returns the in-process default; R1.3d-wiring will fetch from
        XRPC ``com.etzhayyim.kotoba.economy.tariff`` and verify the Council
        signing chain via kotoba-auth CACAO before trusting the rows.
        """
        return self._tariff
