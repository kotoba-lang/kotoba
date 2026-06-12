"""UkCompaniesHouseSensor — Wave-1 anchor: ``corp/registries/gbr/companies-house``.

Per ADR-2605263800. UK Companies House publishes the Free Company Data
Product (FCD) — a monthly bulk archive of ~5M UK companies — under
**OGL v3.0** (Open Government Licence; Crown copyright open license).

This sensor reads the per-company NDJSON view emitted by the (TODO W1)
``uk_companies_house.py`` fetcher. One row per UK CRN (Company
Reference Number) → one ``CorpRegistryObservation``.

UK CRNs have well-defined structural shapes:
  - 8-digit numeric (e.g., ``"03977902"`` — Apple Europe Ltd)
  - 8-char alphanumeric with regional prefix:
    - ``"SC"`` + 6 digits → Scotland (e.g., ``"SC005336"``)
    - ``"NI"`` + 6 digits → Northern Ireland (e.g., ``"NI000123"``)
    - ``"OC"`` + 6 digits → English/Welsh LLP
    - ``"SO"`` + 6 digits → Scottish LLP

This sensor accepts any 8-character CRN (digits OR letter-prefix +
digits) and treats other shapes as malformed (G7 skip).

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Passive-only invariant: NEVER hits Companies House live REST / streaming
APIs at organism-tick time. Only reads pre-fetched IPFS-pinned
subdataset (monthly FCD bulk archive). Vendor commercial-terminal
imports (Bloomberg Terminal / Refinitiv / FactSet / Moody's Orbis /
D&B Hoovers / Pitchbook / Crunchbase Pro) are CONSTITUTIONALLY
PROHIBITED per Charter Rider §2(e)+§2(c).

Per-jurisdiction publication-redaction policy (ADR-2605263800 §5):
UK Companies House passes through named officers + PSCs (Persons with
Significant Control). GDPR right-to-be-forgotten DSARs route through
``chigiri.data_privacy`` to upstream publisher; religious-corp NEVER
performs unilateral removal.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import CorpRegistryObservation


# UK CRN structural pattern:
#   - 8 digits (e.g., "03977902")
#   - 2-letter prefix + 6 digits (e.g., "SC005336", "NI000123", "OC334765", "SO301234")
_CRN_PATTERN = re.compile(r"^(?:\d{8}|[A-Z]{2}\d{6})$")

# Companies House CompanyStatus → "active" rollup (informational; the
# row's `registrationStatus` field is passed through as-is via the
# registered_at optional resolution).
_KNOWN_STATUSES: set[str] = {
    "Active",
    "Active - Proposal to Strike off",
    "Liquidation",
    "Receivership",
    "In Administration",
    "Voluntary Arrangement",
    "Dissolved",
    "Converted/Closed",
    "Open",
    "Closed",
    "Removed",
}


@dataclass
class UkCompaniesHouseSensor:
    """Sensor over a ``corp/registries/gbr/companies-house/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - entityLocalId    (UK CRN, 8-char; required)
      - registeredName   (company legal name; required)
      - registeredAt     (incorporation date, ISO-8601; optional)
      - entityLei        (optional GLEIF LEI 20-char; resolved via
                          LeiSensor cross-ref by the fetcher when known)
      - companyStatus    (optional Companies House status enum; passed
                          through for downstream consumers)

    G7 schema discipline:
      - rows missing ``entityLocalId`` or ``registeredName`` → skip
      - rows with malformed CRN (not matching ``_CRN_PATTERN``) → skip
        without halting the stream
    """

    name: str = "corp/registries/gbr/companies-house"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "OGL-v3.0"
    tier: Tier = "A"
    # Companies House FCD is a monthly bulk product; weekly refresh
    # gives 4x oversampling without burdening upstream.
    refresh_cadence_sec: int = 7 * 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "GBR"
    # Optional filter: only yield CRNs with this regional prefix.
    # "" / None / "GB" = all; "SC" = Scotland only; "NI" = Northern
    # Ireland only; "OC"+"SO" = LLPs. Useful for jurisdiction-split
    # downstream consumers.
    regional_prefix_filter: str = ""
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
    def _crn_matches_prefix_filter(crn: str, prefix: str) -> bool:
        """Test whether `crn` should pass a regional `prefix` filter.

        Empty prefix or "GB" => no restriction. 2-letter prefixes match
        CRNs that start with those 2 letters. Numeric-only ("E&W" rough
        proxy) is matched by passing `prefix="00"` ... `prefix="09"` —
        but the common case is just "SC" / "NI" / "OC" / "SO".
        """
        if not prefix or prefix == "GB":
            return True
        return crn.startswith(prefix)

    def stream(self, pin: DatasetPin) -> Iterator[CorpRegistryObservation]:
        sensor_name = self.name
        prefix_filter = self.regional_prefix_filter
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
                    entity_local_id = str(row.get("entityLocalId", "")).strip().upper()
                    registered_name = str(row.get("registeredName", "")).strip()
                    if not (entity_local_id and registered_name):
                        # G7 — required field missing.
                        continue
                    if not _CRN_PATTERN.match(entity_local_id):
                        # G7 — malformed CRN; skip without halting stream.
                        continue
                    if not self._crn_matches_prefix_filter(entity_local_id, prefix_filter):
                        continue
                    entity_lei_raw = row.get("entityLei")
                    entity_lei = (
                        str(entity_lei_raw).strip()
                        if isinstance(entity_lei_raw, str) and len(entity_lei_raw.strip()) == 20
                        else None
                    )
                    registered_at_raw = row.get("registeredAt")
                    registered_at = (
                        str(registered_at_raw).strip()
                        if isinstance(registered_at_raw, str) and registered_at_raw.strip()
                        else None
                    )
                    yield CorpRegistryObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction_iso3=self.jurisdiction_iso3,
                        entity_local_id=entity_local_id,
                        entity_lei=entity_lei,
                        registered_name=registered_name[:512],
                        registered_at=registered_at,
                        license_tag=self.license,
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpRegistryObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[CorpRegistryObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["UkCompaniesHouseSensor"]
