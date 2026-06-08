"""Murakumo Modal-compat training with Kotoba-backed artifacts.

This module is the training-side sibling of :mod:`kotoba_murakumo.modal_compat`.
It intentionally uses the Modal-shaped API surface while routing to the
Murakumo fleet abstraction, never to Modal Labs servers.

R0 scope:

* define a stable Modal-compatible train job shape;
* run the train body in-process for tests / operator dry-runs;
* persist every produced weight and checkpoint into a Kotoba-style
  content-addressed artifact store.

The store layout is deliberately simple and lossless so a later kotoba-server
XRPC implementation can import it without changing the public API.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from . import modal_compat as modal

_TRAIN_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="murakumo-train")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cid(data: bytes) -> str:
    """Return a stable content id for local Kotoba artifact blobs."""
    return "kotoba-sha256-" + hashlib.sha256(data).hexdigest()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True, slots=True)
class TrainingExample:
    """One supervised training row."""

    prompt: str
    target: str
    quality: float = 1.0


@dataclass(frozen=True, slots=True)
class TrainConfig:
    """Configuration for one Murakumo training run."""

    model_id: str
    run_id: str
    steps: int = 1
    learning_rate: float = 1e-4
    checkpoint_every: int = 1
    node: str = "judah"
    seed: int = 0
    trainer: Literal["modal-compat-local", "modal-compat-spawn"] = "modal-compat-local"

    def validate(self) -> None:
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.run_id:
            raise ValueError("run_id is required")
        if self.steps < 1:
            raise ValueError("steps must be >= 1")
        if self.checkpoint_every < 1:
            raise ValueError("checkpoint_every must be >= 1")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be > 0")


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """A content-addressed artifact persisted through :class:`KotobaArtifactStore`."""

    cid: str
    kind: str
    path: str
    size: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrainRunResult:
    """Result returned by a Murakumo train run."""

    model_id: str
    run_id: str
    trainer: str
    node: str
    steps: int
    final_weight_cid: str
    checkpoint_cids: tuple[str, ...]
    manifest_cid: str
    datom_count: int


class KotobaArtifactStore:
    """Local Kotoba-compatible artifact sink for weights and checkpoints.

    Layout under ``root``::

        blobs/<cid>.bin          raw artifact bytes
        datoms.ndjson           append-only datom projection
        manifests/<run_id>.json final run manifest

    Each datom line uses explicit graph / subject / predicate / object fields so
    kotoba-kqe ingestion can replay the store later without guessing.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.blobs_dir = self.root / "blobs"
        self.manifests_dir = self.root / "manifests"
        self.datoms_path = self.root / "datoms.ndjson"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.datoms_path.touch(exist_ok=True)

    def put_blob(self, data: bytes, *, kind: str, metadata: dict[str, Any]) -> StoredArtifact:
        cid = _cid(data)
        path = self.blobs_dir / f"{cid}.bin"
        if not path.exists():
            path.write_bytes(data)
        return StoredArtifact(
            cid=cid,
            kind=kind,
            path=str(path),
            size=len(data),
            metadata=dict(metadata),
        )

    def append_datom(
        self,
        *,
        graph: str,
        subject: str,
        predicate: str,
        obj: dict[str, Any],
        tx: str,
    ) -> None:
        payload = {
            "graph": graph,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "tx": tx,
            "asserted": True,
            "ts": _now_ms(),
        }
        with self.datoms_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def persist_weight(
        self,
        *,
        model_id: str,
        run_id: str,
        step: int,
        weight_name: str,
        data: bytes,
    ) -> StoredArtifact:
        art = self.put_blob(
            data,
            kind="weight",
            metadata={
                "model_id": model_id,
                "run_id": run_id,
                "step": step,
                "weight_name": weight_name,
            },
        )
        self.append_datom(
            graph="llm/weights",
            subject=model_id,
            predicate=f"weight/{weight_name}",
            obj={"cid": art.cid, "size": art.size, "step": step, "run_id": run_id},
            tx=run_id,
        )
        return art

    def persist_checkpoint(
        self,
        *,
        model_id: str,
        run_id: str,
        step: int,
        weights: dict[str, StoredArtifact],
        metrics: dict[str, Any],
    ) -> StoredArtifact:
        payload = {
            "model_id": model_id,
            "run_id": run_id,
            "step": step,
            "weights": {name: asdict(art) for name, art in sorted(weights.items())},
            "metrics": metrics,
        }
        art = self.put_blob(
            _json_bytes(payload),
            kind="checkpoint",
            metadata={"model_id": model_id, "run_id": run_id, "step": step},
        )
        self.append_datom(
            graph="llm/checkpoints",
            subject=run_id,
            predicate=f"checkpoint/step/{step}",
            obj={"cid": art.cid, "size": art.size, "model_id": model_id, "metrics": metrics},
            tx=run_id,
        )
        return art

    def persist_manifest(self, result: TrainRunResult, *, checkpoints: list[StoredArtifact]) -> StoredArtifact:
        payload = {
            "model_id": result.model_id,
            "run_id": result.run_id,
            "trainer": result.trainer,
            "node": result.node,
            "steps": result.steps,
            "final_weight_cid": result.final_weight_cid,
            "checkpoint_cids": list(result.checkpoint_cids),
            "checkpoints": [asdict(c) for c in checkpoints],
        }
        data = _json_bytes(payload)
        art = self.put_blob(
            data,
            kind="manifest",
            metadata={"model_id": result.model_id, "run_id": result.run_id},
        )
        (self.manifests_dir / f"{result.run_id}.json").write_bytes(data)
        self.append_datom(
            graph="llm/training-runs",
            subject=result.run_id,
            predicate="manifest",
            obj={"cid": art.cid, "model_id": result.model_id},
            tx=result.run_id,
        )
        return art

    def datom_count(self) -> int:
        return sum(1 for line in self.datoms_path.read_text(encoding="utf-8").splitlines() if line)


def _initial_weight_bytes(config: TrainConfig, name: str) -> bytes:
    seed = f"{config.model_id}:{config.run_id}:{name}:{config.seed}".encode("utf-8")
    return hashlib.sha256(seed).digest()


def _training_delta(examples: Iterable[TrainingExample], *, step: int, learning_rate: float) -> bytes:
    h = hashlib.sha256()
    h.update(str(step).encode("ascii"))
    h.update(str(learning_rate).encode("ascii"))
    for ex in examples:
        h.update(ex.prompt.encode("utf-8"))
        h.update(b"\0")
        h.update(ex.target.encode("utf-8"))
        h.update(b"\0")
        h.update(str(max(0.0, min(1.0, ex.quality))).encode("ascii"))
    return h.digest()


def _apply_delta(weight: bytes, delta: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(weight, delta, strict=True))


def train_step_loop(
    *,
    config: TrainConfig,
    examples: list[TrainingExample],
    store_root: Path | str,
) -> TrainRunResult:
    """Run a deterministic train loop and persist weights/checkpoints to Kotoba."""
    config.validate()
    if not examples:
        raise ValueError("at least one TrainingExample is required")

    store = KotobaArtifactStore(store_root)
    weights = {
        "lora/adapter": _initial_weight_bytes(config, "lora/adapter"),
    }
    latest_weight_artifacts: dict[str, StoredArtifact] = {}
    checkpoint_artifacts: list[StoredArtifact] = []

    for step in range(1, config.steps + 1):
        delta = _training_delta(examples, step=step, learning_rate=config.learning_rate)
        weights["lora/adapter"] = _apply_delta(weights["lora/adapter"], delta)
        latest_weight_artifacts["lora/adapter"] = store.persist_weight(
            model_id=config.model_id,
            run_id=config.run_id,
            step=step,
            weight_name="lora/adapter",
            data=weights["lora/adapter"],
        )
        if step % config.checkpoint_every == 0 or step == config.steps:
            checkpoint_artifacts.append(
                store.persist_checkpoint(
                    model_id=config.model_id,
                    run_id=config.run_id,
                    step=step,
                    weights=latest_weight_artifacts,
                    metrics={
                        "examples": len(examples),
                        "quality_mean": sum(e.quality for e in examples) / len(examples),
                    },
                )
            )

    final_weight = latest_weight_artifacts["lora/adapter"]
    provisional = TrainRunResult(
        model_id=config.model_id,
        run_id=config.run_id,
        trainer=config.trainer,
        node=config.node,
        steps=config.steps,
        final_weight_cid=final_weight.cid,
        checkpoint_cids=tuple(c.cid for c in checkpoint_artifacts),
        manifest_cid="",
        datom_count=store.datom_count(),
    )
    manifest = store.persist_manifest(provisional, checkpoints=checkpoint_artifacts)
    return TrainRunResult(
        model_id=provisional.model_id,
        run_id=provisional.run_id,
        trainer=provisional.trainer,
        node=provisional.node,
        steps=provisional.steps,
        final_weight_cid=provisional.final_weight_cid,
        checkpoint_cids=provisional.checkpoint_cids,
        manifest_cid=manifest.cid,
        datom_count=store.datom_count(),
    )


class MurakumoModalTrainer:
    """Modal-shaped trainer bound to one Murakumo Mac mini node."""

    def __init__(
        self,
        *,
        store_root: Path | str,
        node: str = "judah",
        fleet: Path | str = "50-infra/murakumo/fleet.toml",
        did: str = "did:web:etzhayyim.com:actor:maxwell-trainer",
    ) -> None:
        self.store_root = Path(store_root)
        self.node = node
        self.app = modal.App("murakumo-weight-train", fleet=fleet, did=did)

        @self.app.function(
            gpu=modal.gpu.MacMini(node=node),
            timeout=24 * 60 * 60,
            volumes={"/kotoba": modal.Volume.from_name("kotoba-weight-checkpoints", create_if_missing=True)},
        )
        def _train(config_payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
            cfg = TrainConfig(**config_payload)
            examples = [TrainingExample(**row) for row in rows]
            result = train_step_loop(config=cfg, examples=examples, store_root=self.store_root)
            return asdict(result)

        self._train = _train

    def train(self, config: TrainConfig, examples: list[TrainingExample]) -> TrainRunResult:
        """Run the configured Modal-compatible train function."""
        payload = asdict(config)
        rows = [asdict(e) for e in examples]
        if config.trainer == "modal-compat-spawn":
            # Function.spawn() is reserved for inference HTTP dispatch in the
            # existing Modal facade. Training uses the same @app.function shape
            # but runs the train body, so async mode is a local job future until
            # kotoba-vm remote Python execution lands.
            raw = _TRAIN_EXECUTOR.submit(self._train.local, payload, rows).result()
        else:
            raw = self._train.local(payload, rows)
        return TrainRunResult(
            model_id=raw["model_id"],
            run_id=raw["run_id"],
            trainer=raw["trainer"],
            node=raw["node"],
            steps=raw["steps"],
            final_weight_cid=raw["final_weight_cid"],
            checkpoint_cids=tuple(raw["checkpoint_cids"]),
            manifest_cid=raw["manifest_cid"],
            datom_count=raw["datom_count"],
        )


def train_with_modal_py(
    *,
    config: TrainConfig,
    examples: list[TrainingExample],
    store_root: Path | str,
    fleet: Path | str = "50-infra/murakumo/fleet.toml",
) -> TrainRunResult:
    """Convenience entrypoint for operator scripts."""
    trainer = MurakumoModalTrainer(store_root=store_root, node=config.node, fleet=fleet)
    return trainer.train(config, examples)


__all__ = [
    "KotobaArtifactStore",
    "MurakumoModalTrainer",
    "StoredArtifact",
    "TrainConfig",
    "TrainRunResult",
    "TrainingExample",
    "train_step_loop",
    "train_with_modal_py",
]
