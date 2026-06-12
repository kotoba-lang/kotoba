"""UsUscSensor — Wave-1 anchor: ``law/statutes/us-usc`` (US Code statutes).

Per ADR-2605262800. US Code (Office of Law Revision Counsel) is public
domain. Subdataset shards are NDJSON, one row per (title, section,
subsection) tuple emitted by the (TODO W1) ``us_usc.py`` fetcher.

Hot-sample is deterministic on ``pin.revision`` per G9.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LegalStatuteObservation


@dataclass
class UsUscSensor:
    """Sensor over a ``law/statutes/us-usc/<rev>/`` subdataset NDJSON view."""

    name: str = "law/statutes/us-usc"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "public-domain"
    tier: Tier = "A"
    refresh_cadence_sec: int = 7 * 24 * 3600  # weekly upstream cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "USA"
    statute_class: str = "code"
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        """Resolve which files in the annex view to read for this pin.

        Layout: ``<annex_root>/<name-with-slashes>/<latest-snapshot>/*.ndjson``.
        """
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

    def stream(self, pin: DatasetPin) -> Iterator[LegalStatuteObservation]:
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
                    yield LegalStatuteObservation(
                        sensor=self.name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        citation=row.get("citation", ""),
                        title=row.get("title", ""),
                        body_excerpt=row.get("body", "")[:2000],
                        jurisdiction_iso3=self.jurisdiction_iso3,
                        statute_class=self.statute_class,  # type: ignore[arg-type]
                        in_force_at=row.get("in_force_at"),
                        license_tag=self.license,
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalStatuteObservation]:
        # Reservoir sample; deterministic on (pin.revision, n) per G9.
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LegalStatuteObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["UsUscSensor"]
