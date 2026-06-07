# 20-actors/kotoba-kotodama/py/src/kotodama/organism/embodiment.py
from __future__ import annotations
import time
from pydantic import BaseModel, Field
from typing import List, Literal
from .base import BaseObservation
from .joucho_types import JouchoDelta

class Pose(BaseModel):
    lat: int
    lon: int
    heading_deg: int
    speed_mps: int

class TelemetryObservation(BaseObservation):
    """
    Represents a telemetry data point from an embodied organism, specifically a 'wadachi' vehicle.
    """
    kind: Literal["telemetry"] = "telemetry"

    vehicle_serial: str
    lands_parcel_cid: str
    pose: Pose
    battery_soc_pct: int = Field(..., ge=0, le=10000)
    mileage_km: int
    runtime_hours: int
    fault_codes: List[str]

    provenance_hash: str

def telemetry_joucho_delta(obs: TelemetryObservation, baseline: dict[str, int]) -> JouchoDelta:
    """
    Calculates the Joucho (emotional) delta based on a telemetry observation.
    - Battery drop > 10% -> negative yokkyu (motivation) and seimei (life force)
    - Fault codes -> positive kakushin (uncertainty) and negative kanjou (emotion)
    - Runtime increase -> slightly positive kankaku (sensation) and seimei (life force)
    """
    delta = JouchoDelta()

    prev_battery_soc = baseline.get("battery_soc_pct", obs.battery_soc_pct)
    battery_drop_bp = prev_battery_soc - obs.battery_soc_pct
    if battery_drop_bp > 1000: # 10% in basis points
        delta.yokkyu -= int(battery_drop_bp / 100)
        delta.seimei -= int(battery_drop_bp / 100)

    if obs.fault_codes:
        delta.kakushin += 10 * len(obs.fault_codes)
        delta.kanjou -= 5 * len(obs.fault_codes)

    prev_runtime = baseline.get("runtime_hours", obs.runtime_hours)
    runtime_inc = obs.runtime_hours - prev_runtime
    if runtime_inc > 0:
        delta.kankaku += 1
        delta.seimei += 2

    return delta

import random

class E7mSimTelemetrySource:
    """
    A stubbed data source for fetching telemetry from the e7m-sim environment.
    """
    @staticmethod
    def fetch(vehicle_serial: str, actor_did: str) -> TelemetryObservation:
        """
        Fetches a dummy TelemetryObservation for the given vehicle.
        """
        return TelemetryObservation(
            actorDid=actor_did,
            createdAt=int(time.time()),
            tier="B",
            internal_only=False,
            vehicle_serial=vehicle_serial,
            lands_parcel_cid="bafyreig7k47p2k4rxejiq3x6nux326p62qj3j7k2fj6y3w6q2d2d3e4f5a",
            pose=Pose(
                lat=int((35.681236 + random.uniform(-0.01, 0.01)) * 1_000_000),
                lon=int((139.767125 + random.uniform(-0.01, 0.01)) * 1_000_000),
                heading_deg=random.randint(0, 35999),
                speed_mps=random.randint(0, 1500),
            ),
            battery_soc_pct=random.randint(2000, 9500),
            mileage_km=random.randint(1000_000, 50000_000),
            runtime_hours=random.randint(100 * 3600, 2000 * 3600),
            fault_codes=["FC001" for _ in range(random.randint(0, 2))],
            provenance_hash="dummy_provenance_hash_r1",
        )
