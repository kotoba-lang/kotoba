"""SecEdgarSensor — Wave-1 anchor: ``corp/disclosures/usa/*/`` (SEC EDGAR).

Per ADR-2605263800. The U.S. Securities and Exchange Commission's EDGAR
system publishes ~10K public-traded company filings (10-K, 10-Q, 8-K,
Form 4, 13F, S-1 etc.) under US-government-work public-domain status
(17 CFR 200; 17 USC 105). Tier-A.

This sensor reads the per-filing NDJSON view emitted by the (TODO W1)
``sec_edgar.py`` fetcher. One row per filing → one
``CorpDisclosureObservation``. The fetcher MUST emit a `formClass`
field aligned with the ADR-2605263800 §3 ``FormClass`` enum; this
sensor additionally maps common native form-type codes to canonical
form classes when ``formClass`` is omitted (resilience for
hand-curated fixtures).

Hot-sample is deterministic on ``(pin.revision, n)`` per G7 of
ADR-2605263800 (reservoir sampling seeded by pin revision).

Passive-only invariant: NEVER hits the SEC EDGAR live API at
organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
Vendor commercial-terminal imports (Bloomberg Terminal / Refinitiv /
FactSet / Moody's Orbis / D&B Hoovers / Pitchbook / Crunchbase Pro)
are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)+§2(c).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import CorpDisclosureObservation, FormClass


# SEC EDGAR native form codes → canonical FormClass.
# Reference: SEC Forms List; keep external URLs out of sensors per
# ADR-2605262400 passive-only lint.
_FORM_CLASS_MAP: dict[str, FormClass] = {
    # Annual / interim / material-event
    "10-K": "annual-report",
    "10-K/A": "filer-amendment",
    "10-Q": "interim-report",
    "10-Q/A": "filer-amendment",
    "8-K": "material-event",
    "8-K/A": "filer-amendment",
    # Insider transactions
    "3": "insider-transaction",
    "4": "insider-transaction",
    "5": "insider-transaction",
    # Institutional holdings
    "13F-HR": "institutional-holding",
    "13F-HR/A": "filer-amendment",
    "SC 13D": "institutional-holding",
    "SC 13D/A": "filer-amendment",
    "SC 13G": "institutional-holding",
    "SC 13G/A": "filer-amendment",
    # Registration statements
    "S-1": "registration",
    "S-1/A": "filer-amendment",
    "S-3": "registration",
    "S-3/A": "filer-amendment",
    "F-1": "registration",
}


def _canonical_form_class(form_type_native: str) -> FormClass | None:
    """Map a native SEC form code to a canonical FormClass enum value.

    Returns ``None`` if the code is unknown — the sensor then skips the
    row per G7 schema discipline (rather than yielding an observation
    that fails downstream type checks against the FormClass enum).
    """
    return _FORM_CLASS_MAP.get(form_type_native)


@dataclass
class SecEdgarSensor:
    """Sensor over a ``corp/disclosures/usa/<form>/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - entityLocalId      (10-digit SEC CIK, zero-padded; required)
      - formTypeNative     (raw SEC form code, e.g. "10-K" / "8-K"; required)
      - filedAtUtc         (ISO-8601 UTC; required)
      - payloadCid         (IPFS CID of normalized JSON filing; required)
      - entityLei          (optional GLEIF LEI 20-char; resolved via
                            LeiSensor cross-ref by the fetcher when known)
      - formClass          (optional canonical FormClass enum; if absent,
                            this sensor maps formTypeNative via the
                            internal _FORM_CLASS_MAP table; rows whose
                            mapping is unknown are skipped per G7)
      - piiRedacted        (optional bool; default False)

    Per ADR-2605263800 §5 publication-redaction policy: SEC EDGAR is
    pass-through (upstream publishes named officers + insiders; named
    >=10% holders; director identities). ``piiRedacted=False`` is the
    expected default; the field flips True only if defense-in-depth
    PII filter at the fetcher modified the view (e.g., GDPR
    right-to-be-forgotten DSAR ingestion path), which routes through
    chigiri.data_privacy to upstream publisher; religious-corp NEVER
    performs unilateral redaction.
    """

    name: str = "corp/disclosures/usa"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "public-domain"
    tier: Tier = "A"
    # SEC EDGAR publishes daily; per-CIK quarterly indexes update on
    # filing dates; ~daily sensor refresh is appropriate.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "USA"
    # Restrict to a specific FormClass at construction time (e.g., only
    # 10-K). Empty tuple = no restriction; all known form types pass.
    form_class_filter: tuple[FormClass, ...] = ()
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        """Resolve NDJSON shard paths under <annex_root>/<name>/<rev>/.

        The SEC EDGAR fetcher emits per-form sub-snapshot directories
        (e.g., ``<annex_root>/corp/disclosures/usa/10-K/<rev>/*.ndjson``);
        this sensor accepts either:
          - the parent ``corp/disclosures/usa/<rev>/`` layout
          - the per-form sub-layout where ``name`` carries the form path

        Whichever the operator wired up at fetch time, the resolver
        descends ONE directory level to find the snapshot, then globs.
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

    def stream(self, pin: DatasetPin) -> Iterator[CorpDisclosureObservation]:
        sensor_name = self.name
        filter_set = set(self.form_class_filter) if self.form_class_filter else None
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
                    entity_local_id = str(row.get("entityLocalId", "")).strip()
                    form_type_native = str(row.get("formTypeNative", "")).strip()
                    filed_at_utc = str(row.get("filedAtUtc", "")).strip()
                    payload_cid = str(row.get("payloadCid", "")).strip()
                    if not (entity_local_id and form_type_native and filed_at_utc and payload_cid):
                        # G7 schema discipline — required field missing.
                        continue
                    # Resolve canonical FormClass.
                    form_class_raw = row.get("formClass")
                    form_class: FormClass | None
                    if isinstance(form_class_raw, str) and form_class_raw:
                        form_class = form_class_raw  # type: ignore[assignment]
                    else:
                        form_class = _canonical_form_class(form_type_native)
                    if form_class is None:
                        # Unknown native form code AND no canonical
                        # `formClass` field — G7 schema discipline:
                        # skip rather than emit a typed observation
                        # that would fail downstream FormClass enum.
                        continue
                    if filter_set is not None and form_class not in filter_set:
                        continue
                    entity_lei_raw = row.get("entityLei")
                    entity_lei = (
                        str(entity_lei_raw).strip()
                        if isinstance(entity_lei_raw, str) and len(entity_lei_raw.strip()) == 20
                        else None
                    )
                    yield CorpDisclosureObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction_iso3=self.jurisdiction_iso3,
                        entity_local_id=entity_local_id,
                        entity_lei=entity_lei,
                        form_class=form_class,
                        form_type_native=form_type_native,
                        filed_at_utc=filed_at_utc,
                        payload_cid=payload_cid,
                        license_tag=self.license,
                        internal_only=False,
                        pii_redacted=bool(row.get("piiRedacted", False)),
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpDisclosureObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[CorpDisclosureObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["SecEdgarSensor"]
