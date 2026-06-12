"""WorldBankOpenDataSensor — Wave-1 anchor: ``gov/statistics/worldbank-open-data``.

Per ADR-2605263900. The World Bank Open Data API publishes ~16K
indicators across 270+ economies (national + regional + IGO
aggregates) under **CC-BY 4.0** (World Bank Open Data Terms of Use).

This sensor reads the per-indicator NDJSON view emitted by the
(TODO W1) ``worldbank_open_data.py`` fetcher. One row per
(indicator, economy, observation-period, value) tuple → one
``GovStatisticsObservation``. The fetcher MUST preserve SDMX-style
dimension semantics by emitting an ordered list of
``[[code, value], ...]`` pairs in the row's ``dimensions`` field.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7 of
ADR-2605263900 (reservoir sampling seeded by pin revision).

Passive-only invariant: NEVER hits a per-indicator live API endpoint
at organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
Vendor commercial gov-intel terminal imports (GovWin IQ / Bloomberg
Government / Politico Pro / E&E News Pro / FiscalNote / CQ Roll Call
Pro) are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)+§2(c).

CN data semantics: World Bank publishes CN figures that PRC officials
contribute upstream; this sensor passes through ``state_aligned_flag``
from the row's payload (set true only if the fetcher already flagged
that path), since the World Bank itself is a multilateral aggregator
(not a state). Downstream consumers (ossekai + manabi) MUST honor
whatever flag is set.
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
class WorldBankOpenDataSensor:
    """Sensor over a ``gov/statistics/worldbank-open-data/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - indicatorCode      (e.g., "NY.GDP.MKTP.CD")
      - indicatorTitle     (e.g., "GDP (current US$)")
      - dimensions         (ordered list of [code, value] pairs;
                            typically [["country","CHN"], ["year","2025"]])
      - value              (number; may be None for missing-value flags)
      - valueUnit          (e.g., "USD", "%")
      - observationPeriod  (ISO-8601 period: "2025" / "2025-Q3" / "2025-12")
      - stateAlignedFlag   (optional bool; default False)

    Rows missing any of the FOUR required fields (``indicatorCode``,
    ``indicatorTitle``, ``dimensions``, ``observationPeriod``) are
    skipped without halting the stream (G7 schema discipline).
    """

    name: str = "gov/statistics/worldbank-open-data"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC-BY-4.0"
    tier: Tier = "A"
    # World Bank Open Data publishes monthly per-indicator updates;
    # absolute upstream cadence varies, but ~daily refresh is safe.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    source: str = "worldbank"
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
        """Normalize the dimensions field into a tuple of (code, value) pairs.

        Accepts either a list-of-2-lists (``[["country","USA"],...]``) or
        a dict (``{"country":"USA","year":"2025"}``). Other shapes return
        an empty tuple (the row is then skipped by the required-field
        check in ``stream``).
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
                        # G7 schema discipline — required fields missing,
                        # skip without halt.
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
                        value_unit=(str(row["valueUnit"]) if "valueUnit" in row and row["valueUnit"] is not None else None),
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


__all__ = ["WorldBankOpenDataSensor"]
