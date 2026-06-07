"""UkDataGovUkSensor — Wave-1 anchor: ``gov/open-data/gbr/data-gov-uk``.

Per ADR-2605263900. data.gov.uk is the UK government's open-data
catalog (CKAN-based; ~70K dataset entries across UK central + local
government publishers) under **OGL v3.0** (Open Government Licence —
Crown copyright open license). Individual datasets MAY carry
additional attribution requirements via their CKAN ``license_id``
field; the sensor passes that through on the observation.

This sensor reads the per-dataset NDJSON view emitted by the (TODO W1)
``uk_data_gov_uk.py`` fetcher. One row per CKAN package → one
``GovOpenDataObservation`` with ``jurisdiction="GBR"``.

Second sibling of :class:`UsDataGovSensor` (USA W1) +
:class:`JpDataGoJpSensor` (JP W1). All three yield
``GovOpenDataObservation`` and disambiguate via the ``jurisdiction``
field.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: data.gov.uk publisher
+ organisation fields pass-through. GDPR right-to-be-forgotten DSARs
route through ``chigiri.data_privacy`` to upstream publisher (Cabinet
Office / individual UK central / local government body); religious-
corp NEVER performs unilateral removal.

Passive-only invariant: NEVER hits the data.gov.uk CKAN live API at
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
from .base import GovOpenDataObservation


@dataclass
class UkDataGovUkSensor:
    """Sensor over a ``gov/open-data/gbr/data-gov-uk/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - datasetId          (CKAN package name; required)
      - title              (human-readable dataset title; required)
      - license            (per-dataset license ID, e.g. "uk-ogl" /
                            "cc-by" / "cc0"; required)
      - payloadCid         (IPFS CID of normalized full CKAN package
                            metadata; required)
      - descriptionExcerpt (optional)
      - publisher          (optional publishing UK gov body)
      - publishedAtUtc     (optional ISO-8601 UTC)
      - organisation       (optional CKAN organisation owning the package;
                            note British English spelling)

    G7 schema discipline: rows missing any of the four required fields
    are skipped without halting the stream.
    """

    name: str = "gov/open-data/gbr/data-gov-uk"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "OGL-v3.0"
    tier: Tier = "A"
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction: str = "GBR"
    # Optional filter: only yield datasets whose CKAN `organisation`
    # matches the supplied string. "" = all organisations pass.
    organisation_filter: str = ""
    # Optional filter: only yield datasets whose CKAN `license` field
    # matches. Empty tuple = all licenses pass.
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
        org_filter = self.organisation_filter
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
                        organisation = str(row.get("organisation", "")).strip()
                        if organisation != org_filter:
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
                        state_aligned_flag=False,  # GBR NOT §2(g)-flagged
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


__all__ = ["UkDataGovUkSensor"]
