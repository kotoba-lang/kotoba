"""JpEdinetSensor — Wave-1 anchor: ``corp/disclosures/jpn/*/`` (JP EDINET).

Per ADR-2605263800. EDINET (Electronic Disclosure for Investors'
NETwork) is JP 金融庁 (Financial Services Agency) public filings system
for ~4K filers under 金融庁 open-data utilization terms (~CC-BY 4.0
equivalent practically). Tier-A.

This sensor reads the per-filing NDJSON view emitted by the (TODO W1)
``jp_edinet.py`` fetcher. One row per filing → one
``CorpDisclosureObservation``. The fetcher MUST emit a `formClass`
field aligned with the ADR-2605263800 §3 ``FormClass`` enum; this
sensor additionally maps common EDINET native form codes (numeric
"120" / "140" / "160" / "350" etc.) to canonical form classes when
``formClass`` is omitted (resilience).

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Passive-only invariant: NEVER hits EDINET v2 documents live API at
organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
Vendor commercial-terminal imports (Bloomberg Terminal / Refinitiv /
FactSet / Moody's Orbis / D&B Hoovers / Pitchbook / Crunchbase Pro)
are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)+§2(c).

Per ADR-2605263800 §5 publication-redaction policy: JP EDINET
pass-through (upstream publishes 役員 (officers) + 大量保有提出者
(large-holding filers) + 株主 lists). 個人情報保護法 + 金融商品取引法
non-public material-fact pre-disclosure redaction is applied by the
fetcher at PII filter step if applicable; this sensor does NOT
re-redact. GDPR-class right-to-be-forgotten DSARs route through
``chigiri.data_privacy`` to upstream publisher.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import CorpDisclosureObservation, FormClass


# EDINET native form codes (per 金融庁 EDINET API v2 documentation) →
# canonical FormClass. EDINET uses a 3-digit ordinal form-code system;
# the documented filing-type taxonomy is:
#   030: 有価証券届出書 (registration statement)
#   120: 有価証券報告書 (yuho; annual report)
#   140: 四半期報告書 (quarterly report; ~2024 までは 半期報告書)
#   150: 半期報告書 (semi-annual report; legacy)
#   160: 臨時報告書 (extraordinary report)
#   350: 大量保有報告書 (large-holding report)
#   360: 大量保有報告書(変更報告書) (large-holding amendment)
_FORM_CLASS_MAP: dict[str, FormClass] = {
    "030": "registration",
    "120": "annual-report",
    "140": "interim-report",
    "150": "interim-report",
    "160": "material-event",
    "350": "institutional-holding",
    "360": "filer-amendment",
}


def _canonical_form_class(form_type_native: str) -> FormClass | None:
    """Map an EDINET 3-digit native form code to canonical FormClass.

    Returns ``None`` if unknown — sensor then skips per G7 schema
    discipline (rather than yielding an observation that fails
    downstream FormClass enum).
    """
    return _FORM_CLASS_MAP.get(form_type_native)


@dataclass
class JpEdinetSensor:
    """Sensor over a ``corp/disclosures/jpn/<form>/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - entityLocalId    (EDINET 提出者 ID, e.g. "E00001"; required)
      - formTypeNative   (EDINET 3-digit form code, e.g. "120"; required)
      - filedAtUtc       (ISO-8601 UTC; required)
      - payloadCid       (IPFS CID of normalized JSON filing; required)
      - entityLei        (optional GLEIF LEI 20-char; resolved by
                          fetcher via LeiSensor cross-ref when known)
      - formClass        (optional canonical FormClass; if absent,
                          sensor maps formTypeNative via _FORM_CLASS_MAP;
                          unknown codes are skipped per G7)
      - piiRedacted      (optional bool; default False)
    """

    name: str = "corp/disclosures/jpn"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "fsa-open-data-utilization-terms"
    tier: Tier = "A"
    # EDINET publishes daily; sensor refresh ~daily aligns.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "JPN"
    # Restrict to a specific FormClass at construction time
    # (e.g., only annual-report). Empty tuple = no restriction.
    form_class_filter: tuple[FormClass, ...] = ()
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
                        # G7 — unknown native EDINET code with no
                        # explicit formClass field: skip without halt.
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


__all__ = ["JpEdinetSensor"]
