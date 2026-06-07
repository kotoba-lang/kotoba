"""V13 OutcomeActor — Bayesian outcome posterior (conjugate Beta-Binomial).

Charter §V13: PyMC Bayesian model for localization / SIN / PedsQL. The
charter target is a full posterior over a 3-axis outcome vector; the P0
implementation uses scipy.stats conjugate Beta-Binomial posteriors which
are exact for binary success rates and sufficient as the first deliverable.
PyMC migration (with a joint copula over the three axes and predictive
sampling) is a P1 enhancement.

The three axes:

  - **localization**: binaural sound-localization accuracy (RMS error
    below clinical threshold; binarized success rate)
  - **SIN**: speech-in-noise comprehension (CNC / AzBio HINT score above
    age-stratified cutoff; binarized success rate)
  - **PedsQL**: PedsQL or AQoL-derived quality-of-life improvement
    (above MCID; binarized success rate)

For each axis we maintain a Beta(α, β) posterior. Priors are seeded from
charter Table §60-79 literature + the V12 plasticity ceiling — a CLOSED
phase gate (`outcome_ceiling=LATE_ADULT`) shifts the prior toward β.

Stop condition: the Pregel halts when the entropy of all three posteriors
falls below ε (charter §Supersteps). This actor emits the entropy so the
runner can apply that gate.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

try:
    from scipy.stats import beta as _beta  # type: ignore[import-not-found]

    _SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover — guarded fallback
    _SCIPY_AVAILABLE = False


# ── Prior tables (clinician-reviewable in PR) ────────────────────────────────

# Default uninformative seed if V12 outcome_ceiling is missing.
_DEFAULT_PRIOR_ALPHA = 2.0
_DEFAULT_PRIOR_BETA = 2.0

# Outcome-ceiling → (alpha, beta) prior mean adjustment per axis.
_CEILING_PRIOR: dict[str, tuple[float, float]] = {
    "high":       (5.0, 2.0),   # E[p] ≈ 0.71
    "moderate":   (3.0, 3.0),   # E[p] ≈ 0.50
    "limited":    (2.0, 4.0),   # E[p] ≈ 0.33
    "late_adult": (2.0, 6.0),   # E[p] ≈ 0.25
}

# 95% credible interval mass.
_CRED_MASS = 0.95


# ── Inputs ───────────────────────────────────────────────────────────────────


class OutcomeObservation(BaseModel):
    """Binomial trial counts for one axis. `successes ≤ trials`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trials: int = Field(..., ge=0, le=10_000)
    successes: int = Field(..., ge=0, le=10_000)


class OutcomeInput(BaseModel):
    """V13 input. All axes optional — missing axes use the V12-seeded prior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    localization: Optional[OutcomeObservation] = None
    sin: Optional[OutcomeObservation] = None
    pedsql: Optional[OutcomeObservation] = None


# ── Output ───────────────────────────────────────────────────────────────────


class AxisPosterior(BaseModel):
    """Posterior summary for one axis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: float
    beta: float
    posterior_mean: float = Field(..., ge=0.0, le=1.0)
    posterior_sd: float = Field(..., ge=0.0)
    credible_interval_low: float = Field(..., ge=0.0, le=1.0)
    credible_interval_high: float = Field(..., ge=0.0, le=1.0)
    # Differential entropy of Beta(α, β) in nats. Note: differential entropy
    # is signed; for α, β > 1 it is negative (more peaked than uniform).
    entropy_nats: float


class OutcomePosterior(BaseModel):
    """V13 output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    localization: AxisPosterior
    sin: AxisPosterior
    pedsql: AxisPosterior
    # Sum of axis SDs — concrete uncertainty signal used for the Pregel
    # stop condition. Charter §Supersteps loosely says "entropy < ε";
    # we operationalise that as "total posterior SD < ε" which is
    # equivalent up to a monotone transform on Beta and avoids the sign
    # ambiguity of differential entropy.
    total_posterior_sd: float = Field(..., ge=0.0)
    total_entropy_nats: float  # signed; for reporting only
    halt_recommended: bool = Field(
        ...,
        description="True when total_posterior_sd < halt_epsilon — Pregel "
        "stop condition per charter §Supersteps.",
    )
    halt_epsilon: float = Field(..., gt=0.0)
    backend: Literal["scipy", "fallback"]


# ── Actor ────────────────────────────────────────────────────────────────────


class OutcomeActor:
    """V13 — conjugate Beta-Binomial posterior over 3 outcome axes."""

    name = "V13_outcome"

    # Charter §Supersteps stop condition. We operationalise "entropy < ε"
    # as "total posterior SD < ε" (sum of per-axis SDs). 0.15 = roughly
    # 0.05 per axis = posterior tight enough that the 95% CI half-width is
    # under ~0.1, i.e. each axis is decided to ±10%.
    HALT_EPSILON_SD = 0.15

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("outcome_input") or {}
        parsed = OutcomeInput.model_validate(raw)

        plasticity = state.get("plasticity_plan") or {}
        ceiling = str(plasticity.get("outcome_ceiling") or "").lower()
        prior_alpha, prior_beta = _CEILING_PRIOR.get(
            ceiling, (_DEFAULT_PRIOR_ALPHA, _DEFAULT_PRIOR_BETA)
        )

        loc = OutcomeActor._axis(parsed.localization, prior_alpha, prior_beta)
        sin = OutcomeActor._axis(parsed.sin, prior_alpha, prior_beta)
        ped = OutcomeActor._axis(parsed.pedsql, prior_alpha, prior_beta)

        total_sd = loc.posterior_sd + sin.posterior_sd + ped.posterior_sd
        total_entropy = loc.entropy_nats + sin.entropy_nats + ped.entropy_nats
        posterior = OutcomePosterior(
            localization=loc,
            sin=sin,
            pedsql=ped,
            total_posterior_sd=total_sd,
            total_entropy_nats=total_entropy,
            halt_recommended=total_sd < OutcomeActor.HALT_EPSILON_SD,
            halt_epsilon=OutcomeActor.HALT_EPSILON_SD,
            backend="scipy" if _SCIPY_AVAILABLE else "fallback",
        )
        return {
            "outcome_posterior": posterior.model_dump(),
            "requires_human_review": True,
        }

    @staticmethod
    def _axis(
        obs: Optional[OutcomeObservation],
        prior_alpha: float,
        prior_beta: float,
    ) -> AxisPosterior:
        trials = obs.trials if obs is not None else 0
        successes = obs.successes if obs is not None else 0
        if obs is not None and successes > trials:
            # pydantic doesn't enforce cross-field here; clamp deterministically.
            successes = trials

        alpha = prior_alpha + successes
        beta = prior_beta + (trials - successes)

        mean = alpha / (alpha + beta)
        # Closed-form Beta variance: αβ / ((α+β)² (α+β+1)).
        var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        sd = math.sqrt(var)

        # Credible interval (95% equal-tailed). Scipy if available; else
        # Wald-style approximation around the posterior mean.
        if _SCIPY_AVAILABLE:
            low = float(_beta.ppf((1 - _CRED_MASS) / 2, alpha, beta))
            high = float(_beta.ppf(1 - (1 - _CRED_MASS) / 2, alpha, beta))
        else:
            low = max(0.0, mean - 1.96 * sd)
            high = min(1.0, mean + 1.96 * sd)

        return AxisPosterior(
            alpha=alpha,
            beta=beta,
            posterior_mean=round(mean, 6),
            posterior_sd=round(sd, 6),
            credible_interval_low=round(low, 6),
            credible_interval_high=round(high, 6),
            entropy_nats=round(OutcomeActor._beta_entropy(alpha, beta), 6),
        )

    @staticmethod
    def _beta_entropy(alpha: float, beta: float) -> float:
        """Differential entropy of Beta(α, β), in nats.

        h = ln B(α, β) − (α−1)·ψ(α) − (β−1)·ψ(β) + (α+β−2)·ψ(α+β)

        Implemented via math.lgamma + a polynomial digamma so we don't pull
        scipy into the entropy path (numerically stable enough at the
        α,β ≥ 1 we'll see here)."""
        # log-Beta(α, β) = lgamma(α) + lgamma(β) − lgamma(α + β)
        log_beta = math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
        return (
            log_beta
            - (alpha - 1.0) * _digamma(alpha)
            - (beta - 1.0) * _digamma(beta)
            + (alpha + beta - 2.0) * _digamma(alpha + beta)
        )


def _digamma(x: float) -> float:
    """Digamma ψ(x) via the asymptotic series + recurrence shift.

    Accurate to ~1e-6 for x ≥ 1, which is the regime we operate in (priors
    seeded at α,β ≥ 2, observations only push them higher). Avoids a scipy
    dependency in the entropy path."""
    result = 0.0
    while x < 6.0:
        result -= 1.0 / x
        x += 1.0
    # Asymptotic series.
    result += math.log(x) - 1.0 / (2.0 * x)
    x2 = 1.0 / (x * x)
    result -= x2 * (
        1.0 / 12.0
        - x2 * (1.0 / 120.0 - x2 * (1.0 / 252.0 - x2 / 240.0))
    )
    return result
