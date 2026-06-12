"""Subprocess test for `70-tools/scripts/training/baien-mx-smoke.py`
(ADR 2605101000 step 5/6).

The smoke runner asserts internally that every projector branch
received gradient over its 5 steps; this test runs the runner end-
to-end and verifies (a) it exits 0, (b) summary.json reports
gradSeen=True for all four modalities, (c) the loss series has the
expected length, (d) `--dry-run` skips training without loading torch
state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNNER = REPO_ROOT / "70-tools" / "scripts" / "training" / "baien-mx-smoke.py"


def test_dry_run_emits_plan_and_exits_zero(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run",
         "--output", str(tmp_path / "dry")],
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[baien-mx-smoke] plan:" in proc.stdout
    assert "kind" in proc.stdout
    # Dry run should NOT have written summary.json.
    assert not (tmp_path / "dry" / "summary.json").exists()


def test_smoke_run_grads_every_projector(tmp_path):
    out_dir = tmp_path / "smoke"
    proc = subprocess.run(
        [sys.executable, str(RUNNER),
         "--steps", "3", "--batch", "8", "--rows", "32",
         "--output", str(out_dir)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0, (
        f"runner failed: stdout=\n{proc.stdout}\nstderr=\n{proc.stderr}"
    )
    summary_path = out_dir / "summary.json"
    assert summary_path.exists(), proc.stdout
    summary = json.loads(summary_path.read_text())
    assert summary["ok"] is True
    grad_seen = summary["metrics"]["gradSeen"]
    # Hard contract: every projector must have received gradient.
    assert grad_seen == {
        "triple": True,
        "vec768": True,
        "vec4096fp8": True,
        "3dblob": True,
    }, grad_seen
    assert len(summary["metrics"]["lossSeries"]) == 3
    assert summary["metrics"]["finalLoss"] is not None


def test_smoke_run_with_3_steps_and_smaller_batch_still_grads_all(tmp_path):
    """Smaller knobs still satisfy the grad-on-every-projector
    contract. Pins that the contract is robust to step/batch tuning,
    not just the default 5/8."""
    out_dir = tmp_path / "smoke-small"
    proc = subprocess.run(
        [sys.executable, str(RUNNER),
         "--rows", "20", "--steps", "2", "--batch", "4",
         "--output", str(out_dir)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((out_dir / "summary.json").read_text())
    assert all(summary["metrics"]["gradSeen"].values())
