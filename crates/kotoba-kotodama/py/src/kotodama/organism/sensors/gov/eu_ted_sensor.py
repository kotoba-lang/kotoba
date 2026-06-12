"""EuTedSensor — Wave-1+ anchor: ``gov/procurement/eu/ted``.

Per ADR-2605263900. TED (Tenders Electronic Daily) is the EU public-
procurement transparency portal under **EU re-use Decision 2011/833/
EU** (Commission's open data policy). ~700K procurement notices /
year covering all EU + EEA contracting authorities; eForms-standard
data model.

This sensor reads the per-notice NDJSON view emitted by the (TODO W1)
``eu_ted.py`` fetcher. One row per procurement notice →
``GovProcurementObservation`` with ``jurisdiction="EU"`` (or per-
member-state ISO-3 if the fetcher splits per-country shards).

Cross-links to ``com.etzhayyim.corp.leiReference`` (ADR-2605263800
``LeiSensor``) when the awardee is a legal entity with a GLEIF LEI;
used by **toritate** (ADR-2605262900) for recipient-vendor anti-
related-party checks.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: TED awardee names
pass-through (procurement-transparency-regime reason). GDPR right-
to-be-forgotten DSARs route through ``chigiri.data_privacy`` to
upstream Publications Office of the EU; religious-corp NEVER
performs unilateral removal.

Passive-only invariant: NEVER hits ted.europa.eu live API at
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
from .base import GovProcurementObservation, ProcurementRecordKind


# Canonical ProcurementRecordKind per ADR-2605263900 base.py.
_KNOWN_RECORD_KINDS: set[str] = {
    "tender-notice", "award", "modification", "cancellation",
}

# TED eForms notice-type strings → canonical ProcurementRecordKind.
# Reference: TED eForms documentation + notice-type taxonomy.
_NOTICE_TYPE_MAP: dict[str, ProcurementRecordKind] = {
    # Tender / contract notices
    "Contract notice": "tender-notice",
    "Prior information notice": "tender-notice",
    "Periodic indicative notice": "tender-notice",
    "Qualification system notice": "tender-notice",
    "Concession notice": "tender-notice",
    "Voluntary ex ante transparency notice": "tender-notice",
    "Design contest notice": "tender-notice",
    # Award notices
    "Contract award notice": "award",
    "Award notice": "award",
    "Concession award notice": "award",
    # Modifications
    "Modification notice": "modification",
    "Modification of a contract": "modification",
    # Cancellations / corrections
    "Cancellation notice": "cancellation",
    "Corrigendum": "cancellation",
}


def _canonical_record_kind(native: str) -> ProcurementRecordKind | None:
    return _NOTICE_TYPE_MAP.get(native)


@dataclass
class EuTedSensor:
    """Sensor over a ``gov/procurement/eu/ted/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - noticeId             (TED canonical notice ID, e.g.
                              "12345-2026"; required)
      - title                (notice title; required)
      - contractingAuthority (issuing buyer org; required)
      - payloadCid           (IPFS CID of normalized eForms payload; required)
      - recordKind OR nativeKind  (canonical kind OR TED notice-type
                                   string for canonical mapping; required)
      - awardeeName          (optional pass-through per §5)
      - awardeeLocalId       (optional national company-register ID OR EU PIC)
      - awardeeLei           (optional GLEIF LEI 20-char; cross-link to
                              corp.leiReference)
      - awardAmountLocal     (optional numeric)
      - currencyIso4217      (optional currency code)
      - awardDateUtc         (optional ISO-8601 UTC)

    G7 schema discipline: rows missing required fields OR with
    unmappable nativeKind (+ no explicit recordKind) → skip without halt.
    """

    name: str = "gov/procurement/eu/ted"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "eu-reuse-decision-2011-833"
    tier: Tier = "A"
    # TED publishes ~daily; sensor ~daily refresh aligns.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction: str = "EU"
    # Optional filter: only yield records of selected canonical kinds
    # (e.g., ('award',) for awardee-graph consumers).
    record_kind_filter: tuple[ProcurementRecordKind, ...] = ()
    # Optional filter: only yield records with award_amount_local >=
    # threshold (in source currency; None = no filter).
    min_amount_local: float | None = None
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

    def stream(self, pin: DatasetPin) -> Iterator[GovProcurementObservation]:
        sensor_name = self.name
        kind_filter_set = (
            set(self.record_kind_filter) if self.record_kind_filter else None
        )
        min_amount = self.min_amount_local
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
                    notice_id = str(row.get("noticeId", "")).strip()
                    title = str(row.get("title", "")).strip()
                    contracting_authority = str(row.get("contractingAuthority", "")).strip()
                    payload_cid = str(row.get("payloadCid", "")).strip()
                    if not (notice_id and title and contracting_authority and payload_cid):
                        # G7 — required field missing.
                        continue
                    # Resolve canonical record kind.
                    record_kind_raw = row.get("recordKind")
                    record_kind: ProcurementRecordKind | None
                    if isinstance(record_kind_raw, str) and record_kind_raw in _KNOWN_RECORD_KINDS:
                        record_kind = record_kind_raw  # type: ignore[assignment]
                    else:
                        native_kind = str(row.get("nativeKind", "")).strip()
                        record_kind = _canonical_record_kind(native_kind)
                    if record_kind is None:
                        # G7 — kind unresolvable.
                        continue
                    if kind_filter_set is not None and record_kind not in kind_filter_set:
                        continue
                    award_amount_raw = row.get("awardAmountLocal")
                    award_amount = (
                        float(award_amount_raw)
                        if isinstance(award_amount_raw, (int, float))
                        else None
                    )
                    if min_amount is not None:
                        if award_amount is None or award_amount < min_amount:
                            continue
                    currency_raw = row.get("currencyIso4217")
                    currency = (
                        str(currency_raw).strip().upper()[:3]
                        if isinstance(currency_raw, str) and currency_raw.strip()
                        else None
                    )
                    awardee_lei_raw = row.get("awardeeLei")
                    awardee_lei = (
                        str(awardee_lei_raw).strip()
                        if isinstance(awardee_lei_raw, str)
                        and len(awardee_lei_raw.strip()) == 20
                        else None
                    )
                    yield GovProcurementObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction=self.jurisdiction,
                        record_kind=record_kind,
                        notice_id=notice_id,
                        title=title[:1024],
                        contracting_authority=contracting_authority[:512],
                        awardee_name=(
                            str(row["awardeeName"])
                            if "awardeeName" in row and row["awardeeName"]
                            else None
                        ),
                        awardee_local_id=(
                            str(row["awardeeLocalId"])
                            if "awardeeLocalId" in row and row["awardeeLocalId"]
                            else None
                        ),
                        awardee_lei=awardee_lei,
                        award_amount_local=award_amount,
                        currency_iso4217=currency,
                        award_date_utc=(
                            str(row["awardDateUtc"])
                            if "awardDateUtc" in row and row["awardDateUtc"]
                            else None
                        ),
                        license_tag=self.license,
                        payload_cid=payload_cid,
                        state_aligned_flag=False,  # EU NOT §2(g)-flagged
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovProcurementObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[GovProcurementObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["EuTedSensor"]
