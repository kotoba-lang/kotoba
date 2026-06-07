"""mKOTO economy + Modal billing-parity surface.

R1.3b — see ADR-2605282100 for the 6-layer charter. This module ships:

* :class:`Tariff` + :class:`TariffRow` — versioned, signed schedule
* :class:`UsageEstimate` — pre-flight cost estimate (Modal dashboard parity)
* :class:`UsageActual` — post-call billing record (Modal dashboard parity)
* :class:`BudgetExceeded` / :class:`InsufficientCredit` — pre-dispatch
  exceptions raised BEFORE HTTP goes out so callers can surface a donation
  prompt UI without burning compute

R1.3b binds to a **local default tariff** loaded from
:data:`DEFAULT_TARIFF_PATH` (development convenience). R1.3d-wiring replaces
the loader with a CACAO-verified read from kotoba-server XRPC
``com.etzhayyim.kotoba.economy.tariff``. The Python API signature is stable;
only the data source changes.

Charter §1.5 + §2(b) compliance: mKOTO is an internal accounting Datom unit,
not a service price. External callers see "donation acknowledged → mKOTO
credit posted" — never "subscribe for $X/month". See ADR-2605282100 N1-N8.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .exceptions import MurakumoError

Mkoto = int  # uint-64 saturated to i64::MAX at Quad boundary (kotoba native unit)

# 1 KOTO = 10^6 mKOTO (matches kotoba-server::attestation.rs)
MKOTO_PER_KOTO: Mkoto = 1_000_000


# ---------- exceptions --------------------------------------------------------


class EconomyError(MurakumoError):
    """Base class for economy-related errors."""


class BudgetExceeded(EconomyError):
    """Pre-dispatch: ``max_cost_mkoto`` cap exceeded by the estimate.

    Carries the cap + estimate so callers can surface a UI ("this call would
    cost X mKOTO; cap is Y; raise cap or split into smaller calls").
    """

    def __init__(self, *, cap_mkoto: Mkoto, estimated_mkoto: Mkoto, fn_name: str) -> None:
        super().__init__(
            f"BudgetExceeded({fn_name}): estimated {estimated_mkoto} mKOTO > cap {cap_mkoto} mKOTO"
        )
        self.cap_mkoto = cap_mkoto
        self.estimated_mkoto = estimated_mkoto
        self.fn_name = fn_name


class InsufficientCredit(EconomyError):
    """Pre-dispatch: caller DID's balance is below the cost estimate.

    Carries balance + required so the donation prompt UI can show the gap
    in concrete terms ("you have X mKOTO; this call needs Y; donate Z USDC
    to top up").
    """

    def __init__(self, *, did: str, balance_mkoto: Mkoto, required_mkoto: Mkoto) -> None:
        super().__init__(
            f"InsufficientCredit({did}): balance {balance_mkoto} mKOTO < required {required_mkoto} mKOTO"
        )
        self.did = did
        self.balance_mkoto = balance_mkoto
        self.required_mkoto = required_mkoto


# ---------- tariff ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TariffRow:
    """One backend's pricing.

    ``gas_per_1k_mkoto`` applies only to ``webgpu-wasm`` (kotoba-vm Invoke);
    HTTP-routed backends use ``gpu_second_mkoto`` + ``egress_mb_mkoto``.
    """

    backend: str                       # e.g. "litellm-gateway" | "evo-x2-litellm"
    gpu_second_mkoto: Mkoto = 0
    egress_mb_mkoto: Mkoto = 0
    gas_per_1k_mkoto: Mkoto = 0


@dataclass(frozen=True, slots=True)
class Tariff:
    """Posted price schedule.

    R1.3b: loaded from a local JSON file. R1.3d-wiring: loaded via CACAO-
    verified XRPC ``com.etzhayyim.kotoba.economy.tariff`` and verified
    against the Council signing-DID allow-list.
    """

    version: str                       # e.g. "2026-05-28"
    rows: tuple[TariffRow, ...]
    signed_by: tuple[str, ...] = ()    # DIDs of Council signers (R1.3d-wiring)
    signed_at: str = ""                # ISO-8601 UTC

    def for_backend(self, backend: str) -> TariffRow:
        for r in self.rows:
            if r.backend == backend:
                return r
        raise KeyError(
            f"no tariff row for backend {backend!r}; "
            f"available={[r.backend for r in self.rows]}"
        )

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "Tariff":
        rows = tuple(
            TariffRow(
                backend=r["backend"],
                gpu_second_mkoto=int(r.get("gpu_second_mkoto", 0)),
                egress_mb_mkoto=int(r.get("egress_mb_mkoto", 0)),
                gas_per_1k_mkoto=int(r.get("gas_per_1k_mkoto", 0)),
            )
            for r in payload.get("rows", [])
        )
        return cls(
            version=payload["version"],
            rows=rows,
            signed_by=tuple(payload.get("signed_by", [])),
            signed_at=payload.get("signed_at", ""),
        )

    @classmethod
    def load(cls, path: Path | str) -> "Tariff":
        with Path(path).open("r", encoding="utf-8") as f:
            return cls.from_json(json.load(f))


# Default development tariff. R1.3a §"Initial tariff" defines the rates;
# Council Lv6+ ≥3 attestation is required before R2 to bind these on-chain.
_DEFAULT_TARIFF_ROWS = (
    TariffRow("litellm-gateway", gpu_second_mkoto=100, egress_mb_mkoto=10),
    TariffRow("evo-x2",          gpu_second_mkoto=250, egress_mb_mkoto=10),
    TariffRow("mac-mini/judah",  gpu_second_mkoto=30,  egress_mb_mkoto=5),
)


def default_tariff() -> Tariff:
    """In-process default tariff (R1.3b development).

    Backend names match :class:`kotoba_murakumo._internal.routing.ResolvedRoute.backend`.
    For per-node Mac mini backends not enumerated here, the same per-node rate
    as ``mac-mini/judah`` applies (resolved by :func:`row_for_route`).
    """
    return Tariff(
        version="2026-05-28-dev",
        rows=_DEFAULT_TARIFF_ROWS,
        signed_by=(),
        signed_at="",
    )


def row_for_route(tariff: Tariff, backend: str) -> TariffRow:
    """Resolve a TariffRow for a ResolvedRoute.backend value.

    Per-node Mac mini backends ("mac-mini/<tribe>") fall back to the
    "mac-mini/judah" row if the specific tribe is not enumerated.
    """
    try:
        return tariff.for_backend(backend)
    except KeyError:
        if backend.startswith("mac-mini/"):
            return tariff.for_backend("mac-mini/judah")
        raise


# ---------- usage records -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class UsageEstimate:
    """Pre-flight cost estimate."""

    gpu_seconds_est: float
    egress_bytes_est: int
    cost_mkoto_est: Mkoto
    tariff_version: str
    backend: str


@dataclass(frozen=True, slots=True)
class UsageActual:
    """Post-call billing record."""

    gpu_seconds: float
    egress_bytes: int
    prompt_chars: int
    completion_chars: int
    cost_mkoto: Mkoto
    tariff_version: str
    backend: str
    latency_ms: int
    invocation_id: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "gpu_seconds": self.gpu_seconds,
            "egress_bytes": self.egress_bytes,
            "prompt_chars": self.prompt_chars,
            "completion_chars": self.completion_chars,
            "cost_mkoto": self.cost_mkoto,
            "tariff_version": self.tariff_version,
            "backend": self.backend,
            "latency_ms": self.latency_ms,
            "invocation_id": self.invocation_id,
        }


# ---------- estimator + actual-meter ------------------------------------------


# Calibration: rough character-to-token ratio (R1.3b heuristic).
# GPT-style tokenizers ~4 chars/token; Gemma ~3.5; Llama ~3.7. 3.8 is a safe
# midpoint for cost-estimation overestimate (caller never under-budgets).
_CHARS_PER_TOKEN: float = 3.8

# Output size heuristic — for the pre-flight estimate we cannot know the
# completion length; assume max_tokens worth of output at the same ratio.
# R2 may calibrate this from per-model historical actuals.
_EST_COMPLETION_TOKENS_DEFAULT: int = 256

# Per-backend gpu-seconds-per-1k-tokens heuristic. Calibrated against the
# observed throughputs in CLAUDE.md "Performance" + fleet.toml verified_perf:
# llama3.2:3b @ evo-x2 = 83 tok/s → 12.05 ms/tok → 12.05 s/1k tok.
# gemma3:4b @ mac-mini = ~50 tok/s estimate → 20 s/1k tok.
# llama3.3:70b @ evo-x2 = 1.18 tok/s → 847 ms/tok → 847 s/1k tok.
_S_PER_1K_TOKENS_BY_BACKEND: dict[str, float] = {
    "litellm-gateway":  12.0,   # gateway routes to evo-x2 by default
    "evo-x2":           12.0,
    "mac-mini/judah":   20.0,
    # unrecognized backends fall back to litellm-gateway estimate
}


def estimate(
    *,
    tariff: Tariff,
    backend: str,
    prompt_chars: int,
    expected_completion_tokens: int = _EST_COMPLETION_TOKENS_DEFAULT,
) -> UsageEstimate:
    """Pre-flight cost estimate.

    Heuristic: gpu_seconds = (prompt_tokens + completion_tokens) × s/1k.
    Egress = completion_chars (UTF-8 ≈ 1 byte/char ASCII; safe-overestimates
    on multi-byte codepoints since we count chars). Cost = backend-tariff
    × usage.

    Always rounds up to the nearest mKOTO (caller never under-budgets).
    """
    row = row_for_route(tariff, backend)
    s_per_1k = _S_PER_1K_TOKENS_BY_BACKEND.get(backend) \
        or _S_PER_1K_TOKENS_BY_BACKEND.get("litellm-gateway", 12.0)

    prompt_tokens_est = max(1, int(prompt_chars / _CHARS_PER_TOKEN))
    total_tokens_est = prompt_tokens_est + max(0, expected_completion_tokens)
    gpu_seconds_est = (total_tokens_est / 1000.0) * s_per_1k
    egress_bytes_est = max(0, expected_completion_tokens) * int(_CHARS_PER_TOKEN)

    gpu_cost = _ceil_mul(gpu_seconds_est, row.gpu_second_mkoto)
    egress_cost = _ceil_mul(egress_bytes_est / (1024 * 1024), row.egress_mb_mkoto)
    cost = gpu_cost + egress_cost

    return UsageEstimate(
        gpu_seconds_est=gpu_seconds_est,
        egress_bytes_est=egress_bytes_est,
        cost_mkoto_est=cost,
        tariff_version=tariff.version,
        backend=backend,
    )


def actual(
    *,
    tariff: Tariff,
    backend: str,
    prompt_chars: int,
    completion_chars: int,
    latency_ms: int,
    invocation_id: str = "",
) -> UsageActual:
    """Post-call billing record computed from real latency + response size."""
    row = row_for_route(tariff, backend)
    gpu_seconds = latency_ms / 1000.0
    egress_bytes = completion_chars  # ASCII safe-overestimate
    gpu_cost = _ceil_mul(gpu_seconds, row.gpu_second_mkoto)
    egress_cost = _ceil_mul(egress_bytes / (1024 * 1024), row.egress_mb_mkoto)
    return UsageActual(
        gpu_seconds=gpu_seconds,
        egress_bytes=egress_bytes,
        prompt_chars=prompt_chars,
        completion_chars=completion_chars,
        cost_mkoto=gpu_cost + egress_cost,
        tariff_version=tariff.version,
        backend=backend,
        latency_ms=latency_ms,
        invocation_id=invocation_id,
    )


def _ceil_mul(x: float, rate: Mkoto) -> Mkoto:
    """Multiply + ceil to nearest mKOTO (caller never under-budgets)."""
    import math
    return Mkoto(math.ceil(x * rate))
