"""Self-test for the CI grep gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_gate_passes_on_real_source_tree() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    script = repo_root / "70-tools/scripts/lint/verify_no_modal_labs_calls.py"
    assert script.exists(), f"missing gate script: {script}"

    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        f"CI grep gate failed:\nstdout: {r.stdout}\nstderr: {r.stderr}"
    )
    assert "clean" in r.stdout


def test_gate_flags_injected_violation(tmp_path) -> None:
    """If we drop a violating .py into the package dir, the gate must flag it."""
    repo_root = Path(__file__).resolve().parents[5]
    script = repo_root / "70-tools/scripts/lint/verify_no_modal_labs_calls.py"

    # Build a temporary fake repo with the same path structure.
    fake_pkg = (
        tmp_path / "40-engine/kotoba/py/kotoba_murakumo/kotoba_murakumo"
    )
    fake_pkg.mkdir(parents=True)
    bad = fake_pkg / "evil.py"
    bad.write_text(
        '"""bad module"""\nimport modal\n'
        'BASE = "https://api.modal.com/v1/functions"\n',
        encoding="utf-8",
    )

    r = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1, (
        f"gate should have flagged the injected violation but exited "
        f"{r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"
    )
    assert "modal.com" in r.stderr or "modal" in r.stderr
