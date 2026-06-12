"""JpDataGoJpSensor — Wave-1 anchor: ``gov/open-data/jpn/data-go-jp``.

Per ADR-2605263900. data.go.jp is Japan's central open-data catalog
(CKAN-based; ~30K entries) + e-Stat is 政府統計の総合窓口 (Government
Statistics Window; ~600 surveys from all ministries). Both fall under
**CC-BY 4.0** (政府標準利用規約 2.0 — JP government standard data-
utilization terms, aligned with CC-BY 4.0).

This sensor reads the per-dataset NDJSON view emitted by the (TODO W1)
``jp_data_go_jp.py`` fetcher. One row per dataset → one
``GovOpenDataObservation`` with ``jurisdiction="JPN"``. The fetcher
may combine data.go.jp CKAN packages + e-Stat statsList entries into
a single NDJSON view; the sensor treats them uniformly through the
common observation shape (e-Stat statsCodes can be used as
``datasetId`` values).

Third sibling of :class:`UsDataGovSensor` (USA W1) +
:class:`UkDataGovUkSensor` (GBR W1).

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: data.go.jp publisher
+ organization fields pass-through (省庁 + 自治体 names are upstream-
published by design). 個人情報保護法 + 行政手続オンライン化法 right-
to-be-forgotten DSARs route through ``chigiri.data_privacy`` to
upstream publisher (各省庁 / e-Stat operator NSTAC); religious-corp
NEVER performs unilateral removal.

Passive-only invariant: NEVER hits data.go.jp CKAN / e-Stat live API
at organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
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
from .base import GovOpenDataObservation


@dataclass
class JpDataGoJpSensor:
    """Sensor over a ``gov/open-data/jpn/data-go-jp/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - datasetId          (CKAN package name OR e-Stat statsCode; required)
      - title              (human-readable dataset/survey title; required)
      - license            (per-dataset license ID, default "cc-by-4.0"
                            for 政府標準利用規約; required)
      - payloadCid         (IPFS CID of normalized full metadata; required)
      - descriptionExcerpt (optional)
      - publisher          (optional 省庁 / 自治体 publisher name; e.g.
                            "総務省", "厚生労働省", "東京都")
      - publishedAtUtc     (optional ISO-8601 UTC)
      - organization       (optional CKAN organization owning the package)
      - source             (optional "data.go.jp" | "e-stat" for the
                            combined-NDJSON case; sensor does NOT filter
                            on this at the constructor level but
                            downstream consumers may inspect via the
                            payload)

    G7 schema discipline: rows missing required fields skipped.
    """

    name: str = "gov/open-data/jpn/data-go-jp"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC-BY-4.0"
    tier: Tier = "A"
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction: str = "JPN"
    # Optional filter: only yield datasets whose CKAN `organization`
    # (or 省庁 name) matches the supplied string.
    organization_filter: str = ""
    license_filter: tuple[str, ...] = ()
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

    def stream(self, pin: DatasetPin) -> Iterator[GovOpenDataObservation]:
        sensor_name = self.name
        org_filter = self.organization_filter
        license_filter_set = set(self.license_filter) if self.license_filter else None
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
                    dataset_id = str(row.get("datasetId", "")).strip()
                    title = str(row.get("title", "")).strip()
                    license_id = str(row.get("license", "")).strip()
                    payload_cid = str(row.get("payloadCid", "")).strip()
                    if not (dataset_id and title and license_id and payload_cid):
                        # G7 — required field missing.
                        continue
                    if org_filter:
                        organization = str(row.get("organization", "")).strip()
                        if organization != org_filter:
                            continue
                    if license_filter_set is not None and license_id not in license_filter_set:
                        continue
                    yield GovOpenDataObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction=self.jurisdiction,
                        dataset_id=dataset_id,
                        title=title[:1024],
                        description_excerpt=str(row.get("descriptionExcerpt", ""))[:4096],
                        license_tag=license_id,
                        publisher=(
                            str(row["publisher"])
                            if "publisher" in row and row["publisher"]
                            else None
                        ),
                        published_at_utc=(
                            str(row["publishedAtUtc"])
                            if "publishedAtUtc" in row and row["publishedAtUtc"]
                            else None
                        ),
                        payload_cid=payload_cid,
                        state_aligned_flag=False,  # JPN NOT §2(g)-flagged
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovOpenDataObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[GovOpenDataObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["JpDataGoJpSensor"]
