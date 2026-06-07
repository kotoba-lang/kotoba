"""isaaclab.utils.dr — per-env domain randomisation for Cartpole.

Python facade of kami_shugyo::DomainRandomizationCfg (Rust). Same formulas,
same LCG constants → bit-reproducible per-env CartpoleConfig across the
Rust ↔ Python boundary.

Usage:

    from kotodama.nv_compat.isaaclab.utils import dr
    from kotodama.nv_compat.isaacsim.core.controllers.lqr import CartpoleConfig

    base = CartpoleConfig()
    cfg = dr.DomainRandomizationCfg.around(base)         # ±20% mass, ±5% length, ±5% g
    per_env_cfgs = cfg.sample_n(base, n=1024, base_seed=42)
    env.set_per_env_cfgs(per_env_cfgs)

This mirrors `isaaclab.envs.mdp.events.randomize_*` upstream which performs
per-env physics randomisation each episode reset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# LCG matching kami_shugyo::dr::Lcg constants → cross-language reproducibility.
class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_u01(self) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)

    def next_uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.next_u01()


@dataclass
class Range:
    """Inclusive uniform-sampling range."""
    low: float
    high: float

    @staticmethod
    def fixed(v: float) -> "Range":
        return Range(low=v, high=v)


@dataclass
class DomainRandomizationCfg:
    """Per-field DR ranges. Any field with low==high keeps that parameter
    constant across envs (`Range.fixed(v)`).

    Matches kami_shugyo::DomainRandomizationCfg field-for-field.
    """
    cart_mass: Range = field(default_factory=lambda: Range(0.8, 1.2))
    pole_mass: Range = field(default_factory=lambda: Range(0.08, 0.12))
    pole_half_length: Range = field(default_factory=lambda: Range(0.2375, 0.2625))
    gravity: Range = field(default_factory=lambda: Range(9.3195, 10.3005))
    force_mag: Range = field(default_factory=lambda: Range(100.0, 100.0))
    dt: Range = field(default_factory=lambda: Range(1.0 / 60.0, 1.0 / 60.0))

    @staticmethod
    def around(base: Any) -> "DomainRandomizationCfg":
        """±20% mass, ±5% length, ±5% gravity, fixed force/dt (matches Rust)."""
        return DomainRandomizationCfg(
            cart_mass=Range(base.cart_mass * 0.8, base.cart_mass * 1.2),
            pole_mass=Range(base.pole_mass * 0.8, base.pole_mass * 1.2),
            pole_half_length=Range(base.pole_half_length * 0.95, base.pole_half_length * 1.05),
            gravity=Range(base.gravity * 0.95, base.gravity * 1.05),
            force_mag=Range.fixed(base.force_mag),
            dt=Range.fixed(base.dt),
        )

    @staticmethod
    def identity(base: Any) -> "DomainRandomizationCfg":
        return DomainRandomizationCfg(
            cart_mass=Range.fixed(base.cart_mass),
            pole_mass=Range.fixed(base.pole_mass),
            pole_half_length=Range.fixed(base.pole_half_length),
            gravity=Range.fixed(base.gravity),
            force_mag=Range.fixed(base.force_mag),
            dt=Range.fixed(base.dt),
        )

    def sample(self, base: Any, seed: int) -> Any:
        """Sample one CartpoleConfig from this DR distribution. Returns the
        same `CartpoleConfig` type as `base` (duck-typed).

        Bit-reproducible with kami_shugyo::DomainRandomizationCfg::sample.
        """
        rng = _Lcg(seed)
        type_of = type(base)
        return type_of(
            cart_mass=rng.next_uniform(self.cart_mass.low, self.cart_mass.high),
            pole_mass=rng.next_uniform(self.pole_mass.low, self.pole_mass.high),
            pole_half_length=rng.next_uniform(self.pole_half_length.low, self.pole_half_length.high),
            gravity=rng.next_uniform(self.gravity.low, self.gravity.high),
            force_mag=rng.next_uniform(self.force_mag.low, self.force_mag.high),
            dt=rng.next_uniform(self.dt.low, self.dt.high),
        )

    def sample_n(self, base: Any, n: int, base_seed: int) -> list:
        """Produce N per-env configs seeded as base_seed + i (matches Rust)."""
        return [self.sample(base, (base_seed + i) & 0xFFFFFFFFFFFFFFFF) for i in range(n)]
