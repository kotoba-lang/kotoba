"""Shell sewing state machine — ADR-2605261115 L4b (makura).

Three-side serge stitch shell assembly. Watari (R1+) robot witness.
Stitch density witness; one open seam left for filling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ShellSewingPhase(Enum):
    INIT = "init"
    PATTERN_LOADED = "pattern_loaded"
    FABRIC_CUT = "fabric_cut"
    SERGE_STITCHED = "serge_stitched"
    INSPECTION = "inspection"
    SHELL_READY = "shell_ready"


@dataclass
class ShellSewingState:
    phase: ShellSewingPhase
    lotId: str
    completionPct: int
    pattern: dict[str, Any] | None = None
    cutTelemetry: dict[str, Any] | None = None
    stitchTelemetry: dict[str, Any] | None = None
    inspection: dict[str, Any] | None = None
    shellReady: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_pattern_loaded(state: dict[str, Any]) -> dict[str, Any]:
    ss = ShellSewingState(**state.get("shell_sewing_state", {}))
    mock_pattern = {
        "patternCadCid": "bafkreipattern-standard-50x35...",
        "shellSize": "standard-50x35",
        "shellLengthMm": 500,
        "shellWidthMm": 350,
        "seamAllowanceMm": 10,
        "openSeamSideMm": 350,
    }
    ss.phase = ShellSewingPhase.PATTERN_LOADED
    ss.pattern = mock_pattern
    ss.completionPct = 15
    return {"shell_sewing_state": ss.__dict__, "next_node": "cut"}


def transition_to_fabric_cut(state: dict[str, Any]) -> dict[str, Any]:
    ss = ShellSewingState(**state.get("shell_sewing_state", {}))
    mock_cut = {
        "cutterType": "rotary-blade-CNC",
        "panelCount": 2,
        "trimRecycleKg": 0.05,
    }
    ss.phase = ShellSewingPhase.FABRIC_CUT
    ss.cutTelemetry = mock_cut
    ss.completionPct = 35
    return {"shell_sewing_state": ss.__dict__, "next_node": "stitch"}


def transition_to_serge_stitched(state: dict[str, Any]) -> dict[str, Any]:
    ss = ShellSewingState(**state.get("shell_sewing_state", {}))
    mock_stitch = {
        "machineType": "5-thread-overlock-serger",
        "threadType": "100% recycled-polyester-spun",
        "stitchesPerCm": 4.5,
        "stitchedSeamCount": 3,
        "openSeamCount": 1,
        "needleBreakages": 0,
    }
    ss.phase = ShellSewingPhase.SERGE_STITCHED
    ss.stitchTelemetry = mock_stitch
    ss.completionPct = 70
    return {"shell_sewing_state": ss.__dict__, "next_node": "inspection"}


def transition_to_inspection(state: dict[str, Any]) -> dict[str, Any]:
    ss = ShellSewingState(**state.get("shell_sewing_state", {}))
    mock_inspect = {
        "stitchDensityCheck": "pass",
        "seamPullTestN": 65,
        "seamPullSpecMinN": 50,
        "visualDefects": 0,
        "accept": True,
    }
    ss.phase = ShellSewingPhase.INSPECTION
    ss.inspection = mock_inspect
    ss.completionPct = 90
    return {"shell_sewing_state": ss.__dict__, "next_node": "ready"}


def transition_to_shell_ready(state: dict[str, Any]) -> dict[str, Any]:
    ss = ShellSewingState(**state.get("shell_sewing_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:watari-dan-unit-1",
            "role": "stitch_witness",
            "timestamp": "2026-05-26T12:00:00Z",
            "signature": "uV1wX2yZ3aB4...",
        },
    ]
    ss.phase = ShellSewingPhase.SHELL_READY
    ss.robotSignatures = mock_sigs
    ss.completionPct = 100
    shell_ready = {
        "lotId": ss.lotId,
        "pattern": ss.pattern,
        "stitch": ss.stitchTelemetry,
        "inspection": ss.inspection,
        "openSeamReady": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T12:00:10Z",
    }
    ss.shellReady = shell_ready
    return {"shell_sewing_state": ss.__dict__, "shell_ready": shell_ready, "next_node": "end"}
