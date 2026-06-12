"""PlanarChain asset wrapper — configurable n-link revolute serial chain.

Unlike Cartpole/DoublePendulum which have fixed URDFs, the PlanarChain wrapper
can target any n-link configuration (matches kami_genesis::PlanarChainConfig).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlanarChain:
    """N-link planar revolute serial chain (in the xz-plane, axes along world +y).

    No bundled URDF — directly instantiated from kami_genesis::PlanarChainConfig
    via the kami substrate (Rust-side only at R1.x; Python path will appear when
    kotodama.nv_compat exposes planar_chain).
    """
    prim_path: str = "/World/PlanarChain"
    name: str = "planar_chain"
    n: int = 3  # number of links
    masses: tuple = (1.0, 1.0, 1.0)  # length must equal n
    lengths: tuple = (1.0, 1.0, 1.0)  # length must equal n
    default_joint_positions: tuple = (0.0, 0.0, 0.0)
    default_joint_velocities: tuple = (0.0, 0.0, 0.0)
    joint_lower_limits: tuple = (-3.14159, -3.14159, -3.14159)
    joint_upper_limits: tuple = (3.14159, 3.14159, 3.14159)
    effort_limits: tuple = (50.0, 50.0, 50.0)

    def __post_init__(self):
        if len(self.masses) != self.n:
            raise ValueError(f"masses length ({len(self.masses)}) != n ({self.n})")
        if len(self.lengths) != self.n:
            raise ValueError(f"lengths length ({len(self.lengths)}) != n ({self.n})")
        if len(self.default_joint_positions) != self.n:
            raise ValueError(f"default_joint_positions length ({len(self.default_joint_positions)}) != n ({self.n})")

    @property
    def joint_names(self) -> tuple:
        return tuple(f"joint_{i}" for i in range(self.n))

    @property
    def dof_count(self) -> int:
        return self.n

    @classmethod
    def uniform(cls, n: int, prim_path: str = "/World/PlanarChain") -> "PlanarChain":
        """Uniform N-link chain: each link mass=1.0 kg, length=1.0 m."""
        return cls(
            prim_path=prim_path, n=n,
            masses=tuple([1.0] * n),
            lengths=tuple([1.0] * n),
            default_joint_positions=tuple([0.0] * n),
            default_joint_velocities=tuple([0.0] * n),
            joint_lower_limits=tuple([-3.14159] * n),
            joint_upper_limits=tuple([3.14159] * n),
            effort_limits=tuple([50.0] * n),
        )
