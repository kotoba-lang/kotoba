"""isaacsim.core.api.controllers — ArticulationController + PD gains mirror.

R1.x additions (kami-native, not in upstream Isaac Sim):
  - LqrController: classical optimal control for Cartpole upright balance.
"""

from .articulation_controller import ArticulationAction, ArticulationController
from .lqr import CartpoleConfig, LqrController, LqrWeights

__all__ = [
    "ArticulationAction", "ArticulationController",
    "CartpoleConfig", "LqrController", "LqrWeights",
]
