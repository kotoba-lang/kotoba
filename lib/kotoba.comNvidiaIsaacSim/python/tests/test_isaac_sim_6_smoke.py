"""Tests that do not require an Isaac Sim installation."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "isaac_sim_6_smoke.py"
SPEC = importlib.util.spec_from_file_location("isaac_sim_6_smoke", MODULE_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class IsaacSim6SmokeContractTest(unittest.TestCase):
    def test_defaults_target_a_realistic_smoke_run(self) -> None:
        args = SMOKE.build_parser().parse_args([])

        self.assertEqual(args.frames, 120)
        self.assertEqual(args.output_usd, pathlib.Path("artifacts/isaac-sim-6-franka-smoke.usd"))
        SMOKE.validate_args(args)

    def test_rejects_non_positive_frame_count(self) -> None:
        args = SMOKE.build_parser().parse_args(["--frames", "0"])

        with self.assertRaisesRegex(ValueError, "must be positive"):
            SMOKE.validate_args(args)

    def test_joint_result_requires_nine_finite_franka_dofs(self) -> None:
        result = SMOKE.finite_joint_positions(SMOKE.FRANKA_TARGET, expected_dofs=9)

        self.assertEqual(result, list(SMOKE.FRANKA_TARGET))
        with self.assertRaisesRegex(RuntimeError, "expected 9"):
            SMOKE.finite_joint_positions([0.0], expected_dofs=9)
        with self.assertRaisesRegex(RuntimeError, "non-finite"):
            SMOKE.finite_joint_positions([0.0] * 8 + [float("nan")], expected_dofs=9)


if __name__ == "__main__":
    unittest.main()
