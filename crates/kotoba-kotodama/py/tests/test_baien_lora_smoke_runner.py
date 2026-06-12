"""Unit checks for the Baien BitNet LoRA smoke runner
(`70-tools/scripts/training/baien-bitnet-lora-smoke.py`).

These tests do NOT load the real BitNet model — they cover the
non-GPU paths: plan construction, default trunk wiring, synthetic
corpus shape, and `--dry-run` behaviour. They exist so a CI run on a
laptop catches drift in the runner without needing the H100 pod.

Real GPU smoke is run via:

  python 70-tools/scripts/training/baien-bitnet-lora-smoke.py \\
      --steps 5 --output /tmp/baien-smoke

on the H100 NVL training pod (ADR 2605092345 / 2605092350)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNNER = REPO_ROOT / "70-tools" / "scripts" / "training" / "baien-bitnet-lora-smoke.py"


def _load_runner_module():
    """Import the script as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("baien_lora_smoke", RUNNER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_imports_cleanly():
    mod = _load_runner_module()
    assert mod.DEFAULT_TRUNK == "microsoft/bitnet-b1.58-2B-4T-bf16"


def test_synthetic_corpus_is_nonempty_text():
    mod = _load_runner_module()
    corpus = mod._synthetic_corpus()
    assert len(corpus) >= 5
    assert all(isinstance(x, str) and len(x) > 10 for x in corpus)
    # Sanity: the corpus should reference Baien's identity for traceability.
    joined = " ".join(corpus).lower()
    assert "baien" in joined or "bitnet" in joined


def test_plan_carries_lora_hyperparams():
    mod = _load_runner_module()
    args = mod._parse_args.__wrapped__() if hasattr(mod._parse_args, "__wrapped__") else None
    # _parse_args() reads sys.argv; build args manually for unit isolation.
    import argparse

    args = argparse.Namespace(
        base_model=mod.DEFAULT_TRUNK,
        revision="main",
        steps=3,
        lora_rank=8,
        lora_alpha=16,
        lora_dropout=0.05,
        learning_rate=2e-4,
        max_seq_len=128,
        batch_size=1,
        seed=42,
        output="/tmp/baien-smoke-test",
        skip_requantize=True,
        dry_run=True,
    )
    plan = mod._plan(args)
    assert plan["kind"] == "baien-lora"
    assert plan["baseModel"] == "microsoft/bitnet-b1.58-2B-4T-bf16"
    assert plan["hyperparams"]["loraRank"] == 8
    assert plan["hyperparams"]["loraAlpha"] == 16
    assert plan["skipRequantize"] is True


def test_dry_run_subprocess_emits_plan_and_exits_zero(tmp_path):
    """End-to-end smoke of the --dry-run path. Must complete in <2s
    without loading torch/transformers/peft."""
    out_dir = tmp_path / "smoke"
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--dry-run",
            "--steps", "1",
            "--output", str(out_dir),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    # Plan should be in stdout as a JSON block.
    assert "[baien-smoke] plan:" in proc.stdout
    # Extract the JSON between the first '{' and the matching last '}'.
    start = proc.stdout.index("{")
    end = proc.stdout.rindex("}") + 1
    plan = json.loads(proc.stdout[start:end])
    assert plan["kind"] == "baien-lora"
    assert plan["baseModel"] == "microsoft/bitnet-b1.58-2B-4T-bf16"
    assert plan["hyperparams"]["steps"] == 1
    assert "--dry-run" in proc.stdout or "dry-run" in proc.stdout
