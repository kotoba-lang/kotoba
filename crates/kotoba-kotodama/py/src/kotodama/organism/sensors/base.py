"""DatasetSensor Protocol — read-only IPFS-CID-resolved view of a subdataset.

Per ADR-2605262400 §3. A DatasetSensor lets a `kotodama.organism`
heartbeat tick consume a bounded sample from a public-domain corpus
without breaking the substrate boundary:

  - bytes are resolved via `com.etzhayyim.substrate.datasetPin` AT records
    (ADR-2605241500) + IPFS CID map; no separate projection layer;
  - the sensor runs in-memory only — it does NOT write back into the
    DataLad annex; the cold-path corpus assembler is the persistence
    boundary;
  - tier="C" observations carry `internal_only=True` and MUST be dropped
    by `PostSink` on external paths (G4 + R9 backstop);
  - sensor implementations MUST NOT perform active network probes
    against third-party hosts (G8; enforced by
    `70-tools/scripts/lint/sensor-no-active-probe.mjs`).
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol, runtime_checkable

Tier = Literal["A", "B", "C", "D"]


class PiiFilterPolicy(enum.Enum):
    """How aggressively the sensor redacts PII before yielding observations.

    `STRICT` (default) over-redacts; `BALANCED` runs the full Wave-1
    rule set without speculative pattern broadening; `OFF` is reserved
    for in-tree unit tests with synthetic fixtures only — production
    sensors MUST NOT use OFF.
    """

    STRICT = "strict"
    BALANCED = "balanced"
    OFF = "off"


@dataclass(frozen=True)
class DatasetPin:
    """A receipt for one IPFS-pinned subdataset version.

    Resolved from an `com.etzhayyim.substrate.datasetPin` AT record. The
    sensor consumes `cid_map` (a sha256e-key → IPFS CID mapping) to
    fetch individual annex objects on demand via Kubo HTTP API.
    """

    name: str
    revision: str
    cid_map_cid: str
    license: str
    tier: Tier
    created_at: str
    assigned_nodes: tuple[str, ...] = ()
    at_uri: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SensorObservation:
    """One yielded data point from a sensor.

    Distinct from `kotodama.organism.kaizen.Observation` (that one is
    an observer-tick aggregate of shard healthz). This is a per-record
    observation from a public-data sensor.
    """

    sensor: str
    tier: Tier
    pin_revision: str
    payload: dict[str, Any]
    captured_at_ms: int = 0
    internal_only: bool = False

    def with_internal_only(self, flag: bool) -> "SensorObservation":
        return SensorObservation(
            sensor=self.sensor,
            tier=self.tier,
            pin_revision=self.pin_revision,
            payload=self.payload,
            captured_at_ms=self.captured_at_ms,
            internal_only=flag,
        )


@runtime_checkable
class DatasetSensor(Protocol):
    """Read-only IPFS-resolved view of a subdataset.

    Implementations MUST be deterministic on `hot_sample(pin, n)` given
    a fixed `pin.revision` (G9 in ADR-2605262400). Implementations MUST
    NOT touch any network resource other than the religious-corp DID
    infrastructure and the local Kubo HTTP API (G8).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]: ...


@dataclass
class StaticPinResolver:
    """A minimal pin resolver suitable for tests + W1 single-machine use.

    Wave-1 sensors use this; W3 will replace it with an
    `at://did:web:dataset-pinner.etzhayyim.com/...` resolver that hits
    the religious-corp PDS and verifies the DID-signed datasetPin
    record.
    """

    pins: dict[str, DatasetPin] = field(default_factory=dict)

    def latest(self, name: str) -> DatasetPin:
        if name not in self.pins:
            raise LookupError(f"no pin registered for subdataset '{name}'")
        return self.pins[name]


def now_ms() -> int:
    return int(time.time() * 1000)


def make_observation(
    *,
    sensor: str,
    tier: Tier,
    pin: DatasetPin,
    payload: dict[str, Any],
) -> SensorObservation:
    """Helper that fills `internal_only=True` when tier == 'C'.

    Sensors should ALWAYS use this helper rather than constructing
    SensorObservation directly — that way G4 is enforced at the
    construction site and a sensor cannot accidentally emit a tier-C
    observation as externally-shareable.
    """
    return SensorObservation(
        sensor=sensor,
        tier=tier,
        pin_revision=pin.revision,
        payload=payload,
        captured_at_ms=now_ms(),
        internal_only=(tier == "C"),
    )


def stream_bounded(
    sensor: DatasetSensor,
    pin: DatasetPin,
    limit: int,
) -> Iterator[SensorObservation]:
    """Yield at most ``limit`` observations from any DatasetSensor.

    Heartbeat-friendly bounded sampling helper (introduced 2026-05-27
    after the W2 RIPE-RIS perf measurement showed unbounded
    ``hot_sample`` taking minutes on multi-GB BGP archives). Operates
    on any sensor implementing the ``DatasetSensor`` Protocol —
    callers don't need a sensor-specific specialization.

    The sample is **head-biased**: it returns the first ``limit``
    records the sensor's ``stream()`` emits. Suitable for cadence-
    driven organism polls (situational awareness). NOT suitable for
    unbiased cold-path corpus assembly — use the sensor's
    ``hot_sample(pin, n)`` (reservoir over full file) there.

    Performance budget (measured 2026-05-27):
      - NDJSON sensors (rir_delegated, iana_root, OSM, CAIDA):
        ~400-500K obs/s. ``limit=1000`` ≈ 2-5ms.
      - MRT sensors (RIPE-RIS, Routeviews via mrtparse):
        ~15K obs/s. ``limit=1000`` ≈ 70ms; ``limit=10000`` ≈ 700ms.
      - Parquet sensors (OpenINTEL via pyarrow):
        pyarrow chunks at ~100K rows/batch; ``limit=1000`` ≈ 10ms.
    """
    import itertools
    return itertools.islice(sensor.stream(pin), limit)


def hot_sample_bounded(
    sensor: DatasetSensor,
    pin: DatasetPin,
    n: int,
    max_iter: int,
) -> list[SensorObservation]:
    """Reservoir-sample ``n`` from the first ``max_iter`` records.

    Generic bounded version of any sensor's ``hot_sample``. Trades
    uniform sampling over the entire backing file for bounded latency
    — heartbeat callers pick ``max_iter`` to fit their tick budget.

    G9 determinism: same (pin.revision, n, max_iter, sensor.name)
    seed key → identical reservoir result.
    """
    import random
    rng = random.Random(f"{pin.revision}:{n}:{max_iter}:{sensor.name}")
    reservoir: list[SensorObservation] = []
    for i, obs in enumerate(stream_bounded(sensor, pin, max_iter)):
        if i < n:
            reservoir.append(obs)
        else:
            j = rng.randint(0, i)
            if j < n:
                reservoir[j] = obs
    return reservoir


__all__ = [
    "DatasetPin",
    "DatasetSensor",
    "PiiFilterPolicy",
    "SensorObservation",
    "StaticPinResolver",
    "Tier",
    "hot_sample_bounded",
    "make_observation",
    "now_ms",
    "stream_bounded",
]
