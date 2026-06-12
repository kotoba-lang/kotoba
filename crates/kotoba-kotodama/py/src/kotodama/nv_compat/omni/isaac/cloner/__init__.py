"""omni.isaac.cloner — parallel scene-instantiation utilities for RL.

Mirrors `omni.isaac.cloner.GridCloner` (Isaac Sim 4.x) at the public API level.
The cloner computes deterministic grid positions for N copies of a base
environment so that vectorized RL envs (kami_shugyo::VectorizedCartpoleEnv,
isaaclab.envs.ManagerBasedRLEnv with num_envs > 1) can be laid out visually.
"""

from .grid_cloner import Cloner, GridCloner

__all__ = ["Cloner", "GridCloner"]
