"""EuEurostatSensor — Wave-1 anchor: ``gov/statistics/eurostat``.

Per ADR-2605263900. Eurostat is the statistical office of the European
Union. The Statistics API publishes ~10K SDMX dataflows across EU-27 +
EEA + candidate countries under **Eurostat free re-use per Decision
2011/833/EU** (Commission's open data policy).

This sensor reads the per-observation NDJSON view emitted by the
(TODO W1) ``eu_eurostat.py`` fetcher. One row per (dataflow,
dimensions, observation-period, value) tuple →
``GovStatisticsObservation`` with ``source="eurostat"``.

Eurostat dataflow IDs are stable identifiers like ``nama_10_gdp``
(GDP at current prices), ``demo_pjan`` (population), ``prc_hicp_manr``
(HICP monthly inflation). The sensor preserves SDMX-style dimension
semantics by representing the ``dimensions`` field as an ordered
tuple of ``(code, value)`` pairs (e.g. ``(("geo","DE"),("time","2025"))``).

Sibling sensor of :class:`WorldBankOpenDataSensor` — both yield
``GovStatisticsObservation`` and share the dimension-coercion
contract for list-of-2-lists OR dict input shapes.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Passive-only invariant: NEVER hits Eurostat SDMX live API at
organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
Vendor commercial gov-intel terminal imports (GovWin IQ / Bloomberg
Government / Politico Pro / E&E News Pro / FiscalNote / CQ Roll Call
Pro) are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)+§2(c).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import GovStatisticsObservation


@dataclass
class EuEurostatSensor:
    """Sensor over a ``gov/statistics/eurostat/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - indicatorCode      (Eurostat dataflow ID, e.g. "nama_10_gdp"; required)
      - indicatorTitle     (human-readable dataflow title; required)
      - dimensions         (SDMX dimensions; list-of-2-lists OR dict;
                            typically [["geo","DE"],["time","2025"]]; required)
      - observationPeriod  (ISO-8601 period: "2025" / "2025-Q3" / "2025-12"; required)
      - value              (number; may be None for missing-value flags)
      - valueUnit          (e.g., "EUR_HAB", "PC", "RT")
      - payloadCid         (optional IPFS CID of normalized payload)
      - stateAlignedFlag   (optional bool; default False; Eurostat
                            itself is NOT §2(g)-flagged but per-row
                            reporter override permitted)

    G7 schema discipline: rows missing required fields are skipped
    without halting the stream.
    """

    name: str = "gov/statistics/eurostat"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "eurostat-free-reuse"
    tier: Tier = "A"
    # Eurostat publishes daily for monthly/quarterly indicators; ~daily
    # sensor refresh is appropriate.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    source: str = "eurostat"
    # Optional dataflow ID prefix filter (e.g. "nama_" for national-
    # accounts indicators only). Empty = all.
    dataflow_prefix_filter: str = ""
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        subdataset_dir = self.annex_root / self.name
        if not subdataset_dir.exists():
            raise FileNotFoundError(
                f"subdataset '{self.name}' not present at {subdataset_dir}"
            )
        candidates = sorted(
            (p for p in subdataset_dir.iterdir() if p.is_dir()),
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"no snapshot directory under {subdataset_dir}")
        snapshot_dir = candidates[0]
        ndjson_files = sorted(snapshot_dir.glob(f"*{self.ndjson_suffix}"))
        if not ndjson_files:
            raise FileNotFoundError(
                f"no '*{self.ndjson_suffix}' under {snapshot_dir}"
            )
        return ndjson_files

    @staticmethod
    def _coerce_dimensions(raw) -> tuple[tuple[str, str], ...]:
        """Normalize dimensions to a tuple of (code, value) pairs.

        Accepts list-of-2-lists OR dict (sibling contract with
        WorldBankOpenDataSensor._coerce_dimensions). Other shapes →
        empty tuple, which the required-field check in ``stream``
        treats as "dimensions missing" and skips per G7.
        """
        if isinstance(raw, list):
            pairs: list[tuple[str, str]] = []
            for entry in raw:
                if (
                    isinstance(entry, (list, tuple))
                    and len(entry) == 2
                    and all(isinstance(x, str) for x in entry)
                ):
                    pairs.append((entry[0], entry[1]))
            return tuple(pairs)
        if isinstance(raw, dict):
            return tuple((str(k), str(v)) for k, v in raw.items())
        return ()

    def stream(self, pin: DatasetPin) -> Iterator[GovStatisticsObservation]:
        sensor_name = self.name
        prefix_filter = self.dataflow_prefix_filter
        for path in self._resolve_ndjson_paths(pin):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        row = json.loads(s)
                    except json.JSONDecodeError:
                        continue
                    indicator_code = str(row.get("indicatorCode", "")).strip()
                    indicator_title = str(row.get("indicatorTitle", "")).strip()
                    dimensions = self._coerce_dimensions(row.get("dimensions"))
                    obs_period = str(row.get("observationPeriod", "")).strip()
                    if not (indicator_code and indicator_title and dimensions and obs_period):
                        # G7 — required field missing.
                        continue
                    if prefix_filter and not indicator_code.startswith(prefix_filter):
                        continue
                    raw_value = row.get("value")
                    value = (
                        float(raw_value)
                        if isinstance(raw_value, (int, float))
                        else None
                    )
                    yield GovStatisticsObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        source=self.source,  # type: ignore[arg-type]
                        indicator_code=indicator_code,
                        indicator_title=indicator_title[:1024],
                        dimensions=dimensions,
                        value=value,
                        value_unit=(
                            str(row["valueUnit"])
                            if "valueUnit" in row and row["valueUnit"] is not None
                            else None
                        ),
                        observation_period=obs_period,
                        payload_cid=str(row.get("payloadCid", "")),
                        license_tag=self.license,
                        state_aligned_flag=bool(row.get("stateAlignedFlag", False)),
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovStatisticsObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[GovStatisticsObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["EuEurostatSensor"]
