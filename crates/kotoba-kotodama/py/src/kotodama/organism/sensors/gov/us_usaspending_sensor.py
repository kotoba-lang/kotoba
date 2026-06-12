"""UsUsaspendingSensor — Wave-1+ anchor: ``gov/budget/usa/usaspending-gov``.

Per ADR-2605263900. USAspending.gov is the US federal government's
canonical award + recipient + sub-award transparency portal (covering
appropriation / obligation / outlay / subaward records under the DATA
Act 2014). Bulk archives published under **public domain** (US
federal government works are not copyrighted per 17 USC 105).

This sensor reads the per-record NDJSON view emitted by the (TODO W1)
``us_usaspending.py`` fetcher. One row per budget record →
``GovBudgetObservation`` with ``jurisdiction="USA"``.

Cross-links to ``com.etzhayyim.corp.leiReference`` (ADR-2605263800
``LeiSensor``) when the recipient is a legal entity with a GLEIF LEI;
used by **toritate** (ADR-2605262900) for recipient-vendor anti-related-
party checks against Public Fund Safe + Council Safe disbursements
in the same fiscal cycle.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: USAspending recipient
names pass-through (DATA Act transparency-regime reason for
publication). GDPR-class right-to-be-forgotten DSARs route through
``chigiri.data_privacy`` to upstream publisher (Treasury / individual
federal agency); religious-corp NEVER performs unilateral removal.

Passive-only invariant: NEVER hits the USAspending.gov live API at
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
from .base import BudgetRecordKind, GovBudgetObservation


# Canonical BudgetRecordKind values per ADR-2605263900 base.py.
_KNOWN_RECORD_KINDS: set[str] = {
    "appropriation", "obligation", "outlay", "subaward",
}


@dataclass
class UsUsaspendingSensor:
    """Sensor over a ``gov/budget/usa/usaspending-gov/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - recordKind         (BudgetRecordKind enum:
                            appropriation/obligation/outlay/subaward; required)
      - recordId           (USAspending canonical ID; required)
      - programName        (program / TAS / CFDA program name; required)
      - amountLocal        (numeric; required)
      - currencyIso4217    ("USD" canonical; required)
      - fiscalYear         (integer FY; required)
      - payloadCid         (IPFS CID of normalized payload; required)
      - programCode        (optional TAS / CFDA code)
      - recipientName      (optional pass-through per §5)
      - recipientLocalId   (optional SAM.gov UEI)
      - recipientLei       (optional GLEIF LEI 20-char; cross-link to
                            com.etzhayyim.corp.leiReference)
      - awardDateUtc       (optional ISO-8601 UTC)

    G7 schema discipline: rows missing required fields OR with
    unknown recordKind value → skip without halting stream.
    """

    name: str = "gov/budget/usa/usaspending-gov"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "public-domain"
    tier: Tier = "A"
    # USAspending publishes daily; sensor ~daily refresh aligns.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction: str = "USA"
    # Optional filter: only yield records matching a canonical kind set.
    record_kind_filter: tuple[BudgetRecordKind, ...] = ()
    # Optional filter: only yield records from a specific fiscal year.
    fiscal_year_filter: int | None = None
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

    def stream(self, pin: DatasetPin) -> Iterator[GovBudgetObservation]:
        sensor_name = self.name
        kind_filter_set = (
            set(self.record_kind_filter) if self.record_kind_filter else None
        )
        fy_filter = self.fiscal_year_filter
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
                    record_kind_raw = str(row.get("recordKind", "")).strip()
                    record_id = str(row.get("recordId", "")).strip()
                    program_name = str(row.get("programName", "")).strip()
                    amount_raw = row.get("amountLocal")
                    currency = str(row.get("currencyIso4217", "")).strip().upper()
                    fy_raw = row.get("fiscalYear")
                    payload_cid = str(row.get("payloadCid", "")).strip()
                    if not (record_id and program_name and currency and payload_cid):
                        continue
                    if record_kind_raw not in _KNOWN_RECORD_KINDS:
                        # G7 — unknown BudgetRecordKind.
                        continue
                    if not isinstance(amount_raw, (int, float)):
                        continue
                    if not isinstance(fy_raw, int):
                        continue
                    if kind_filter_set is not None and record_kind_raw not in kind_filter_set:
                        continue
                    if fy_filter is not None and fy_raw != fy_filter:
                        continue
                    recipient_lei_raw = row.get("recipientLei")
                    recipient_lei = (
                        str(recipient_lei_raw).strip()
                        if isinstance(recipient_lei_raw, str)
                        and len(recipient_lei_raw.strip()) == 20
                        else None
                    )
                    yield GovBudgetObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction=self.jurisdiction,
                        record_kind=record_kind_raw,  # type: ignore[arg-type]
                        record_id=record_id,
                        program_name=program_name[:512],
                        program_code=(
                            str(row["programCode"])
                            if "programCode" in row and row["programCode"]
                            else None
                        ),
                        amount_local=float(amount_raw),
                        currency_iso4217=currency[:3],
                        fiscal_year=fy_raw,
                        recipient_name=(
                            str(row["recipientName"])
                            if "recipientName" in row and row["recipientName"]
                            else None
                        ),
                        recipient_local_id=(
                            str(row["recipientLocalId"])
                            if "recipientLocalId" in row and row["recipientLocalId"]
                            else None
                        ),
                        recipient_lei=recipient_lei,
                        award_date_utc=(
                            str(row["awardDateUtc"])
                            if "awardDateUtc" in row and row["awardDateUtc"]
                            else None
                        ),
                        license_tag=self.license,
                        payload_cid=payload_cid,
                        state_aligned_flag=False,  # USA NOT §2(g)-flagged
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovBudgetObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[GovBudgetObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["UsUsaspendingSensor"]
