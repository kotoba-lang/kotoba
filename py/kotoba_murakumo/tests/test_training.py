"""Murakumo Modal-compat training persists weights and checkpoints to Kotoba."""

from __future__ import annotations

import json
from pathlib import Path

import kotoba_murakumo as km
from kotoba_murakumo.training import (
    KotobaArtifactStore,
    TrainConfig,
    TrainingExample,
    train_step_loop,
    train_with_modal_py,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _examples() -> list[TrainingExample]:
    return [
        TrainingExample(prompt="explain kotoba", target="content-addressed datom log", quality=1.0),
        TrainingExample(prompt="route train", target="murakumo mac mini fleet", quality=0.5),
    ]


def test_training_api_is_exported() -> None:
    assert km.TrainConfig is TrainConfig
    assert km.TrainingExample is TrainingExample
    assert hasattr(km, "MurakumoModalTrainer")


def test_train_step_loop_persists_weight_checkpoint_and_manifest(tmp_path: Path) -> None:
    cfg = TrainConfig(
        model_id="maxwell-1",
        run_id="run-test-001",
        steps=3,
        checkpoint_every=2,
        node="judah",
    )

    result = train_step_loop(config=cfg, examples=_examples(), store_root=tmp_path)

    assert result.model_id == "maxwell-1"
    assert result.steps == 3
    assert result.final_weight_cid.startswith("kotoba-sha256-")
    # step 2 plus final step 3
    assert len(result.checkpoint_cids) == 2
    assert result.manifest_cid.startswith("kotoba-sha256-")

    for cid in (result.final_weight_cid, result.manifest_cid, *result.checkpoint_cids):
        assert (tmp_path / "blobs" / f"{cid}.bin").is_file()

    manifest = json.loads((tmp_path / "manifests" / "run-test-001.json").read_text())
    assert manifest["final_weight_cid"] == result.final_weight_cid
    assert manifest["checkpoint_cids"] == list(result.checkpoint_cids)

    datoms = [
        json.loads(line)
        for line in (tmp_path / "datoms.ndjson").read_text().splitlines()
        if line
    ]
    assert {d["graph"] for d in datoms} == {
        "llm/weights",
        "llm/checkpoints",
        "llm/training-runs",
    }
    assert any(d["predicate"] == "weight/lora/adapter" for d in datoms)
    assert any(d["predicate"] == "checkpoint/step/2" for d in datoms)
    assert any(d["predicate"] == "checkpoint/step/3" for d in datoms)


def test_modal_py_facade_runs_train_and_saves_to_kotoba(tmp_path: Path) -> None:
    cfg = TrainConfig(
        model_id="maxwell-1",
        run_id="run-modal-001",
        steps=2,
        checkpoint_every=1,
        node="judah",
    )

    result = train_with_modal_py(
        config=cfg,
        examples=_examples(),
        store_root=tmp_path,
        fleet=_repo_root() / "50-infra/murakumo/fleet.toml",
    )

    assert result.trainer == "modal-compat-local"
    assert result.node == "judah"
    assert len(result.checkpoint_cids) == 2
    assert KotobaArtifactStore(tmp_path).datom_count() == result.datom_count


def test_modal_py_spawn_path_uses_same_artifact_contract(tmp_path: Path) -> None:
    cfg = TrainConfig(
        model_id="maxwell-1",
        run_id="run-spawn-001",
        steps=1,
        node="judah",
        trainer="modal-compat-spawn",
    )

    result = train_with_modal_py(
        config=cfg,
        examples=_examples(),
        store_root=tmp_path,
        fleet=_repo_root() / "50-infra/murakumo/fleet.toml",
    )

    assert result.trainer == "modal-compat-spawn"
    assert len(result.checkpoint_cids) == 1
    assert (tmp_path / "manifests" / "run-spawn-001.json").is_file()
