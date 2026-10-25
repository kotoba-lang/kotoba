#!/usr/bin/env python3
"""Headless Isaac Sim 6.0 smoke simulation for this repository.

Run this file with Isaac Sim's ``python.sh``.  Importing Omniverse modules
before ``SimulationApp`` starts Kit is unsupported, so all runtime imports
intentionally live inside :func:`run`.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence


FRANKA_USD = "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
FRANKA_TARGET = (-1.5, 0.0, 0.0, -1.5, 0.0, 1.5, 0.5, 0.04, 0.04)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a headless Franka articulation smoke test in Isaac Sim 6.0."
    )
    parser.add_argument("--frames", type=int, default=120, help="Physics steps to execute.")
    parser.add_argument(
        "--output-usd",
        type=Path,
        default=Path("artifacts/isaac-sim-6-franka-smoke.usd"),
        help="USD stage written after the simulation.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.frames <= 0:
        raise ValueError("--frames must be positive")


def finite_joint_positions(positions: Sequence[float], expected_dofs: int) -> list[float]:
    values = [float(position) for position in positions]
    if len(values) != expected_dofs:
        raise RuntimeError(f"expected {expected_dofs} Franka DOFs, received {len(values)}")
    if not all(math.isfinite(position) for position in values):
        raise RuntimeError("Isaac Sim returned non-finite joint positions")
    return values


def run(args: argparse.Namespace) -> dict[str, object]:
    validate_args(args)

    # Isaac Sim 6.0 requires Kit to be initialized before any Omniverse import.
    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": True})
    try:
        import numpy as np
        import omni.usd
        import isaacsim.core.experimental.utils.stage as stage_utils
        from isaacsim.core.experimental.objects import GroundPlane
        from isaacsim.core.experimental.prims import Articulation, XformPrim
        from isaacsim.core.rendering_manager import RenderingManager
        from isaacsim.core.simulation_manager import SimulationManager
        from isaacsim.storage.native import get_assets_root_path

        stage_utils.create_new_stage()
        GroundPlane("/World/GroundPlane", positions=[0.0, 0.0, 0.0])

        assets_root = get_assets_root_path()
        if not assets_root:
            raise RuntimeError("Isaac Sim assets root is unavailable")
        stage_utils.add_reference_to_stage(
            usd_path=assets_root + FRANKA_USD,
            path="/World/Franka",
        )
        arm_transform = XformPrim("/World/Franka")
        arm_transform.set_world_poses(positions=[0.0, 0.0, 0.0])
        arm = Articulation("/World/Franka")

        # Let references and physics schemas initialize before reading the DOFs.
        for _ in range(4):
            SimulationManager.step()
            RenderingManager.render()
            simulation_app.update()

        initial = finite_joint_positions(arm.get_dof_positions(), expected_dofs=9)
        arm.set_dof_positions(np.asarray(FRANKA_TARGET, dtype=np.float32))

        for _ in range(args.frames):
            SimulationManager.step()
            RenderingManager.render()
            simulation_app.update()

        final = finite_joint_positions(arm.get_dof_positions(), expected_dofs=9)
        target_error = max(abs(actual - target) for actual, target in zip(final, FRANKA_TARGET))
        if target_error > 0.1:
            raise RuntimeError(f"Franka target was not applied (max joint error {target_error:.4f})")

        output_usd = args.output_usd.resolve()
        output_usd.parent.mkdir(parents=True, exist_ok=True)
        if not omni.usd.get_context().save_as_stage(str(output_usd)):
            raise RuntimeError(f"failed to save USD stage to {output_usd}")

        return {
            "status": "ok",
            "isaac_sim_target": "6.0",
            "frames": args.frames,
            "dof_count": len(final),
            "initial_joint_positions": initial,
            "final_joint_positions": final,
            "max_target_error": target_error,
            "output_usd": str(output_usd),
        }
    finally:
        simulation_app.close()


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), sort_keys=True))
    except (RuntimeError, ValueError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
