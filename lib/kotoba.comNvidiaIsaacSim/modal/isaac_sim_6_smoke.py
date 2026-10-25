"""Run the repository's Isaac Sim 6.0 smoke test on a Modal RTX GPU.

Prerequisites:
  modal secret create ngc-registry \
    REGISTRY_USERNAME='$oauthtoken' REGISTRY_PASSWORD='<NGC_API_KEY>'
  modal volume create isaac-sim-6-artifacts

Run from this repository:
  modal run modal/isaac_sim_6_smoke.py --frames 240
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import modal


APP = modal.App("kotoba-isaac-sim-6-smoke")
ARTIFACTS = modal.Volume.from_name("isaac-sim-6-artifacts", create_if_missing=True)
NGC_REGISTRY = modal.Secret.from_name(
    "ngc-registry", required_keys=["REGISTRY_USERNAME", "REGISTRY_PASSWORD"]
)

ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "python" / "isaac_sim_6_smoke.py"

# The NGC image carries Kit's own Python runtime. The function invokes
# /isaac-sim/python.sh explicitly, avoiding an accidental host-Python import.
IMAGE = modal.Image.from_registry(
    "nvcr.io/nvidia/isaac-sim:6.0.1", secret=NGC_REGISTRY
).add_local_file(SMOKE_SCRIPT, "/workspace/isaac_sim_6_smoke.py", copy=True)


def last_json_object(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "status" in value:
            return value
    raise RuntimeError("Isaac Sim smoke process did not emit a JSON result")


@APP.function(
    image=IMAGE,
    gpu="RTX-PRO-6000",
    timeout=60 * 60,
    volumes={"/artifacts": ARTIFACTS},
    env={"ACCEPT_EULA": "Y", "PRIVACY_CONSENT": "Y"},
)
def run_smoke(frames: int = 240) -> dict[str, object]:
    output_usd = "/artifacts/franka-smoke.usd"
    command = [
        "/isaac-sim/python.sh",
        "/workspace/isaac_sim_6_smoke.py",
        "--frames",
        str(frames),
        "--output-usd",
        output_usd,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "ACCEPT_EULA": "Y", "PRIVACY_CONSENT": "Y"},
    )
    result = last_json_object(completed.stdout + "\n" + completed.stderr)
    if completed.returncode != 0 or result.get("status") != "ok":
        raise RuntimeError(json.dumps(result, sort_keys=True))
    ARTIFACTS.commit()
    return result


@APP.local_entrypoint()
def main(frames: int = 240) -> None:
    print(json.dumps(run_smoke.remote(frames), indent=2, sort_keys=True))
