"""Function wrapper — live dispatch + Modal .remote / .remote_async / .spawn / .map / .stream.

R1.1: replaces R0 stubs with httpx-backed dispatch to the Murakumo fleet.

Charter Rider §2(a)-(h) scan runs on both the input prompt and the returned
text. When ``KOTOBA_MURAKUMO_CHARTER_ENFORCE`` is on and severity >= major,
:class:`CharterViolation` raises **before** the result is returned to the
caller (constitutional invariant per ADR-2605192200 + ADR-2605282000).

Every dispatch emits one NDJSON line to
``~/.kotoba_murakumo/invocations.ndjson`` carrying caller DID, resolved
endpoint, model, latency, and Charter scan severities. R1.2 will promote this
to the ``com.etzhayyim.murakumo.invocation`` Lexicon record on the caller's
PDS.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from . import charter, economy
from ._internal import ndjson, routing
from .exceptions import FleetUnreachable, MurakumoCompatNotImplemented
from .fleet import FleetView
from .gpu import GpuSpec
from .image import Image

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    name: str
    fn: Callable[..., Any]
    gpu: GpuSpec | str | None
    model: str | None
    image: Image | None
    timeout: int
    retries: int
    # R1.3b — Modal-equivalent per-call spend cap. None = unbounded.
    # When set, .remote() raises BudgetExceeded BEFORE HTTP if the
    # pre-flight cost estimate exceeds this cap.
    max_cost_mkoto: int | None = None


class FunctionCall(Generic[T]):
    """Async handle returned by :meth:`Function.spawn`.

    Modal-shaped: callers either ``await``-the-handle (Modal pattern uses
    ``.get()``) or call :meth:`get` synchronously to block.
    """

    def __init__(self, *, call_id: str, future: concurrent.futures.Future[T]) -> None:
        self.call_id = call_id
        self._future = future

    def get(self, timeout: float | None = None) -> T:
        """Block until the spawned dispatch finishes; return its result."""
        return self._future.result(timeout=timeout)

    def cancel(self) -> bool:
        return self._future.cancel()

    def done(self) -> bool:
        return self._future.done()


# Module-level executor used by .spawn and .map sync paths. Threads are cheap
# (each call is one outbound HTTP), and the LiteLLM gateway already handles
# server-side concurrency limits.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=32,
    thread_name_prefix="kotoba-murakumo",
)


class Function:
    """One ``@app.function``-decorated callable bound to an App + fleet."""

    def __init__(
        self,
        spec: FunctionSpec,
        *,
        app_name: str,
        caller_did: str,
        fleet: FleetView,
        gateway_node: str = "judah",
        tariff: economy.Tariff | None = None,
        balance_lookup: Callable[[str], int] | None = None,
    ) -> None:
        self._spec = spec
        self._app_name = app_name
        self._caller_did = caller_did
        self._fleet = fleet
        self._gateway_node = gateway_node
        # R1.3b — tariff defaults to in-process schedule when none injected.
        # R1.3d-wiring will replace this with a CACAO-verified XRPC pull.
        self._tariff = tariff if tariff is not None else economy.default_tariff()
        # R1.3b — balance lookup defaults to "unlimited" so existing call sites
        # are unaffected. App.balance() callers can inject a real lookup that
        # talks to kotoba-server com.etzhayyim.kotoba.economy.balance.
        self._balance_lookup = balance_lookup or (lambda _did: 2**62)

    # ---- introspection passthrough -------------------------------------------

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self._spec.name

    @property
    def __wrapped__(self) -> Callable[..., Any]:
        return self._spec.fn

    # ---- public Modal-shaped API ---------------------------------------------

    # ---- economy hooks (R1.3b — see ADR-2605282100) ------------------------

    @property
    def tariff(self) -> economy.Tariff:
        return self._tariff

    def estimate(self, *args: Any, **kwargs: Any) -> economy.UsageEstimate:
        """Pre-flight cost estimate — Modal dashboard parity.

        Resolves the same route the live dispatch would take, then computes
        a backend-tariff-aware UsageEstimate. No HTTP traffic; safe to call
        from cost-budgeting UIs.
        """
        prompt = self._extract_prompt(args, kwargs)
        route = routing.resolve(
            self._spec.gpu, self._spec.model, self._fleet,
            gateway_node=self._gateway_node,
        )
        return economy.estimate(
            tariff=self._tariff,
            backend=route.backend,
            prompt_chars=len(prompt),
        )

    def _budget_preflight(
        self,
        *,
        prompt: str,
        route: "routing.ResolvedRoute",
    ) -> economy.UsageEstimate:
        """Run the budget + balance preflight; raise before HTTP if either fails.

        Constitutional invariant: external callers MUST have non-zero balance
        before the .remote() dispatch goes out (ADR-2605282100 N3). When the
        injected balance_lookup yields > 2^60, treat as "unlimited" (default
        for tests + non-economy-aware call sites).
        """
        est = economy.estimate(
            tariff=self._tariff,
            backend=route.backend,
            prompt_chars=len(prompt),
        )
        cap = self._spec.max_cost_mkoto
        if cap is not None and est.cost_mkoto_est > cap:
            raise economy.BudgetExceeded(
                cap_mkoto=cap,
                estimated_mkoto=est.cost_mkoto_est,
                fn_name=self._spec.name,
            )
        balance = self._balance_lookup(self._caller_did)
        # 2^60 sentinel = "no economy lookup wired" (default). Skip check.
        if balance < (2 ** 60) and balance < est.cost_mkoto_est:
            raise economy.InsufficientCredit(
                did=self._caller_did,
                balance_mkoto=balance,
                required_mkoto=est.cost_mkoto_est,
            )
        return est

    # ---- public Modal-shaped API -------------------------------------------

    def local(self, *args: Any, **kwargs: Any) -> Any:
        """Run the wrapped body in-process, bypassing dispatch entirely."""
        return self._spec.fn(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Modal semantics: direct call inside a remote container is local()."""
        return self.local(*args, **kwargs)

    def remote(self, *args: Any, **kwargs: Any) -> str:
        """Synchronous fleet dispatch. Returns assistant text."""
        return self._dispatch_sync(args, kwargs)

    async def remote_async(self, *args: Any, **kwargs: Any) -> str:
        """Async fleet dispatch. Returns assistant text."""
        return await self._dispatch_async(args, kwargs)

    def spawn(self, *args: Any, **kwargs: Any) -> FunctionCall[str]:
        """Fire-and-forget dispatch. Returns a :class:`FunctionCall` handle.

        The handle resolves to the same string :meth:`remote` would return.
        """
        future = _EXECUTOR.submit(self._dispatch_sync, args, kwargs)
        return FunctionCall(call_id=uuid.uuid4().hex, future=future)

    def map(
        self,
        iterable: Iterable[Any],
        *,
        concurrency: int = 8,
        order_outputs: bool = True,
    ) -> Iterable[str]:
        """Modal-compat batch map.

        R1.1: thread-pool over up to ``concurrency`` in-flight HTTP calls.
        R2 will fan out across fleet nodes via kotoba-net.

        ``order_outputs=True`` returns results in input order (Modal default).
        Set ``False`` for as-completed iteration.
        """
        items = list(iterable)
        if not items:
            return iter(())

        if order_outputs:
            results: list[str | BaseException] = [None] * len(items)  # type: ignore[list-item]
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, concurrency),
                thread_name_prefix="kotoba-murakumo-map",
            ) as ex:
                fut_to_idx = {
                    ex.submit(self._dispatch_sync, (item,), {}): i
                    for i, item in enumerate(items)
                }
                for fut in concurrent.futures.as_completed(fut_to_idx):
                    idx = fut_to_idx[fut]
                    try:
                        results[idx] = fut.result()
                    except BaseException as e:  # noqa: BLE001
                        results[idx] = e
            for r in results:
                if isinstance(r, BaseException):
                    raise r
                yield r  # type: ignore[misc]
            return

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, concurrency),
            thread_name_prefix="kotoba-murakumo-map",
        ) as ex:
            futs = [ex.submit(self._dispatch_sync, (item,), {}) for item in items]
            for fut in concurrent.futures.as_completed(futs):
                yield fut.result()

    def starmap(
        self,
        iterable: Iterable[tuple[Any, ...]],
        *,
        concurrency: int = 8,
        order_outputs: bool = True,
    ) -> Iterable[str]:
        """Like :meth:`map` but each item is a tuple unpacked into ``*args``."""
        # Reuse map's threading by adapting items into a single-arg form;
        # _dispatch_sync extracts the prompt from positional args.
        def _adapt(t: tuple[Any, ...]) -> Any:
            return t[0] if t else ""
        return self.map(
            (_adapt(t) for t in iterable),
            concurrency=concurrency,
            order_outputs=order_outputs,
        )

    async def stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
        """Async SSE stream. Yields assistant tokens as they arrive.

        Routes only through OpenAI-compatible endpoints (LiteLLM gateway,
        EVO-X2 LiteLLM, EVO-X2 ollama, own-node ollama). ComfyUI image-gen
        and R2 WASM Component dispatch do not support token streaming.
        """
        from .client import litellm as litellm_client

        prompt = self._extract_prompt(args, kwargs)
        scan_in = charter.scan(prompt, side="input")
        charter.enforce(scan_in)

        route = routing.resolve(
            self._spec.gpu, self._spec.model, self._fleet,
            gateway_node=self._gateway_node,
        )
        if route.kind not in {"openai-compatible", "ollama-native"}:
            raise MurakumoCompatNotImplemented(
                f"Function.stream ({self._spec.name})",
                f"streaming not supported on {route.kind!r} backends "
                f"(resolved to {route.backend})",
            )

        bearer = routing.bearer_token(route)
        t0 = time.monotonic()
        result_chars = 0
        try:
            async for tok in litellm_client.chat_completions_stream(
                url=route.url,
                model=route.model,
                messages=[{"role": "user", "content": prompt}],
                auth_bearer=bearer,
                max_tokens=1024,
                timeout_s=float(self._spec.timeout),
            ):
                result_chars += len(tok)
                yield tok
        finally:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            ndjson.emit(self._record_dict(
                route=route, prompt=prompt, result_chars=result_chars,
                latency_ms=elapsed_ms, phase="stream",
                charter_in=scan_in.severity, charter_out="n/a-stream",
            ))

    # ---- internal dispatch ---------------------------------------------------

    def _dispatch_sync(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        from .client import litellm as litellm_client
        from .client import ollama as ollama_client

        prompt = self._extract_prompt(args, kwargs)
        scan_in = charter.scan(prompt, side="input")
        charter.enforce(scan_in)

        route = routing.resolve(
            self._spec.gpu, self._spec.model, self._fleet,
            gateway_node=self._gateway_node,
        )
        # R1.3b — budget + balance preflight; raises BudgetExceeded /
        # InsufficientCredit BEFORE HTTP per ADR-2605282100 §"Per-call debit flow".
        est = self._budget_preflight(prompt=prompt, route=route)
        bearer = routing.bearer_token(route)

        t0 = time.monotonic()
        try:
            if route.kind == "openai-compatible":
                result = litellm_client.chat_completions(
                    url=route.url, model=route.model,
                    messages=[{"role": "user", "content": prompt}],
                    auth_bearer=bearer, max_tokens=1024,
                    timeout_s=float(self._spec.timeout),
                )
            elif route.kind == "ollama-native":
                result = ollama_client.chat_completions(
                    url=route.url, model=route.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    timeout_s=float(self._spec.timeout),
                )
            elif route.kind == "comfyui-native":
                raise MurakumoCompatNotImplemented(
                    f"Function.remote ({self._spec.name})",
                    "ComfyUI image-gen dispatch lands R1.2 per ADR-2605282000",
                )
            else:
                raise FleetUnreachable(
                    f"unsupported backend kind {route.kind!r} on route {route.backend}",
                    attempted=[route.url],
                )
        except httpx_error_classes() as e:  # type: ignore[misc]
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            ndjson.emit(self._record_dict(
                route=route, prompt=prompt, result_chars=0,
                latency_ms=elapsed_ms, phase="sync-error",
                charter_in=scan_in.severity, charter_out="n/a-error",
                error=type(e).__name__,
            ))
            raise FleetUnreachable(
                f"{route.backend} dispatch failed: {e}",
                attempted=[route.url],
            ) from e

        scan_out = charter.scan(result, side="output")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        usage = economy.actual(
            tariff=self._tariff, backend=route.backend,
            prompt_chars=len(prompt), completion_chars=len(result),
            latency_ms=elapsed_ms,
        )
        ndjson.emit(self._record_dict(
            route=route, prompt=prompt, result_chars=len(result),
            latency_ms=elapsed_ms, phase="sync",
            charter_in=scan_in.severity, charter_out=scan_out.severity,
            cost_mkoto=usage.cost_mkoto,
            tariff_version=usage.tariff_version,
            cost_estimated_mkoto=est.cost_mkoto_est,
        ))
        charter.enforce(scan_out)
        return result

    async def _dispatch_async(
        self, args: tuple[Any, ...], kwargs: dict[str, Any],
    ) -> str:
        from .client import litellm as litellm_client
        from .client import ollama as ollama_client

        prompt = self._extract_prompt(args, kwargs)
        scan_in = charter.scan(prompt, side="input")
        charter.enforce(scan_in)

        route = routing.resolve(
            self._spec.gpu, self._spec.model, self._fleet,
            gateway_node=self._gateway_node,
        )
        est = self._budget_preflight(prompt=prompt, route=route)
        bearer = routing.bearer_token(route)

        t0 = time.monotonic()
        try:
            if route.kind == "openai-compatible":
                result = await litellm_client.chat_completions_async(
                    url=route.url, model=route.model,
                    messages=[{"role": "user", "content": prompt}],
                    auth_bearer=bearer, max_tokens=1024,
                    timeout_s=float(self._spec.timeout),
                )
            elif route.kind == "ollama-native":
                result = await ollama_client.chat_completions_async(
                    url=route.url, model=route.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    timeout_s=float(self._spec.timeout),
                )
            elif route.kind == "comfyui-native":
                raise MurakumoCompatNotImplemented(
                    f"Function.remote_async ({self._spec.name})",
                    "ComfyUI image-gen dispatch lands R1.2 per ADR-2605282000",
                )
            else:
                raise FleetUnreachable(
                    f"unsupported backend kind {route.kind!r}",
                    attempted=[route.url],
                )
        except httpx_error_classes() as e:  # type: ignore[misc]
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            ndjson.emit(self._record_dict(
                route=route, prompt=prompt, result_chars=0,
                latency_ms=elapsed_ms, phase="async-error",
                charter_in=scan_in.severity, charter_out="n/a-error",
                error=type(e).__name__,
            ))
            raise FleetUnreachable(
                f"{route.backend} dispatch failed: {e}",
                attempted=[route.url],
            ) from e

        scan_out = charter.scan(result, side="output")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        usage = economy.actual(
            tariff=self._tariff, backend=route.backend,
            prompt_chars=len(prompt), completion_chars=len(result),
            latency_ms=elapsed_ms,
        )
        ndjson.emit(self._record_dict(
            route=route, prompt=prompt, result_chars=len(result),
            latency_ms=elapsed_ms, phase="async",
            charter_in=scan_in.severity, charter_out=scan_out.severity,
            cost_mkoto=usage.cost_mkoto,
            tariff_version=usage.tariff_version,
            cost_estimated_mkoto=est.cost_mkoto_est,
        ))
        charter.enforce(scan_out)
        return result

    # ---- helpers -------------------------------------------------------------

    @staticmethod
    def _extract_prompt(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        if args and isinstance(args[0], str):
            return args[0]
        for k in ("prompt", "text", "input"):
            v = kwargs.get(k)
            if isinstance(v, str):
                return v
        return ""

    def _record_dict(
        self, *, route: "routing.ResolvedRoute", prompt: str,
        result_chars: int, latency_ms: int, phase: str,
        charter_in: str, charter_out: str,
        error: str | None = None,
        cost_mkoto: int | None = None,
        cost_estimated_mkoto: int | None = None,
        tariff_version: str | None = None,
    ) -> dict[str, Any]:
        rec = {
            "app": self._app_name,
            "fn": self._spec.name,
            "caller_did": self._caller_did,
            "endpoint": route.url,
            "backend": route.backend,
            "model": route.model,
            "prompt_chars": len(prompt),
            "result_chars": result_chars,
            "latency_ms": latency_ms,
            "phase": phase,
            "charter_in": charter_in,
            "charter_out": charter_out,
        }
        if cost_mkoto is not None:
            rec["cost_mkoto"] = cost_mkoto
        if cost_estimated_mkoto is not None:
            rec["cost_estimated_mkoto"] = cost_estimated_mkoto
        if tariff_version is not None:
            rec["tariff_version"] = tariff_version
        if error:
            rec["error"] = error
        return rec


# ---- internal: httpx error classes lazy import (so the module imports cleanly
# even before httpx is installed by tests that monkeypatch dispatch) ----------

def httpx_error_classes() -> tuple[type[BaseException], ...]:
    try:
        import httpx
        return (httpx.HTTPError, httpx.ConnectError, httpx.ReadTimeout)
    except ImportError:
        return (OSError,)
