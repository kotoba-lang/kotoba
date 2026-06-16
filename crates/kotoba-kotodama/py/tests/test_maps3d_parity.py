"""py↔clj parity cross-check for the maps3d decision tasks.

The migration keeps the Python tasks (maps3d.py) and the Clojure reimplementation
(20-actors/maps/methods/maps3d_tasks.cljc) in PARALLEL. This test feeds identical
inputs to BOTH implementations and asserts they make the SAME deterministic
decision — guarding the parallel pair against silent drift.

Scope = the branches both implement identically with no LLM:
  - curateImages: empty→abort, below-min→abort, top-N-by-quality fallback
    (the Python LLM is forced to fail so its FALLBACK path — the one the clj
    port mirrors — is exercised)
  - replanReconstruction: attempt≥3→downgradeOsm, <5 images→requestMore

Skipped when `bb` (babashka) is not on PATH.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps3d as M

_REPO_ROOT = Path(__file__).resolve().parents[6]
_BB = shutil.which("bb")

pytestmark = pytest.mark.skipif(_BB is None, reason="babashka (bb) not installed")


def _bb(code: str) -> str:
    """Run a bb expression from the repo root (so maps.methods.* is on cp)."""
    out = subprocess.run([_BB, "-e", code], cwd=_REPO_ROOT,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, f"bb failed: {out.stderr}"
    return out.stdout.strip()


def _clj_curate(candidates, target, min_count) -> tuple[bool, list[str]]:
    code = (
        "(require '[maps.methods.maps3d-tasks :as t] '[clojure.string :as s])"
        f"(let [o (t/curate-images {{:candidates {_edn_cands(candidates)} "
        f":target-count {target} :min-count {min_count}}})]"
        "(println (str (:abort o) \"|\" (s/join \",\" (:selectedIds o)))))"
    )
    abort_s, _, ids_s = _bb(code).partition("|")
    return abort_s == "true", ([x for x in ids_s.split(",") if x])


def _clj_replan(attempt, image_count) -> str:
    code = (
        "(require '[maps.methods.maps3d-tasks :as t])"
        f"(println (:action (t/replan {{:attempt {attempt} :image-count {image_count}}})))"
    )
    return _bb(code)


def _edn_cands(cands) -> str:
    return "[" + " ".join(
        "{:id \"%s\" :qualityScore %s}" % (c["id"], c["qualityScore"]) for c in cands
    ) + "]"


def _py_curate(candidates, target, min_count) -> tuple[bool, list[str]]:
    # force the LLM to fail so the deterministic fallback (mirrored by clj) runs
    with patch.object(M._llm, "call_tier_json", side_effect=RuntimeError("no llm")):
        out = asyncio.run(M.task_maps3d_curate_images(
            tileH3="t", candidates=candidates, targetCount=target, minCount=min_count))
    return bool(out["abort"]), list(out["selectedIds"])


def _py_replan(attempt, image_count) -> str:
    out = asyncio.run(M.task_maps3d_replan_reconstruction(
        tileH3="t", imageCount=image_count, attempt=attempt))
    return out["action"]


# ─── curate parity ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cands,target,minc", [
    ([], 30, 8),                                                   # empty → abort
    ([{"id": "1", "qualityScore": 0.9}, {"id": "2", "qualityScore": 0.8}], 30, 8),  # below min
    ([{"id": str(i), "qualityScore": round(1.0 - i * 0.01, 3)} for i in range(20)], 5, 3),  # top-N
])
def test_curate_parity(cands, target, minc):
    py_abort, py_ids = _py_curate(cands, target, minc)
    clj_abort, clj_ids = _clj_curate(cands, target, minc)
    assert py_abort == clj_abort, f"abort differs: py={py_abort} clj={clj_abort}"
    assert py_ids == clj_ids, f"selectedIds differ: py={py_ids} clj={clj_ids}"


# ─── replan parity (deterministic rule branches) ─────────────────────────────

@pytest.mark.parametrize("attempt,images", [
    (3, 10),     # max attempts → downgradeOsm
    (4, 99),     # >max attempts → downgradeOsm
    (1, 2),      # too few images → requestMore
    (2, 0),      # too few images → requestMore
])
def test_replan_parity(attempt, images):
    assert _py_replan(attempt, images) == _clj_replan(attempt, images)
