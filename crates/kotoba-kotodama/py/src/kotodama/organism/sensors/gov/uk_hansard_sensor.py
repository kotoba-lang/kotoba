"""UkHansardSensor — Wave-1 anchor: ``gov/parliament/gbr/hansard``.

Per ADR-2605263900. Hansard is the official report of debates in the
UK Parliament (Commons + Lords). The Parliamentary Data Service
publishes Hansard under **OGL v3.0** (Open Parliament Licence
mirrors the Open Government Licence).

This sensor reads the per-record NDJSON view emitted by the (TODO W1)
``uk_hansard.py`` fetcher. One row per parliamentary record (debate
contribution / committee minute / division / bill / member statement
/ petition / question) → one ``GovParliamentObservation``.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: UK Hansard
pass-through (speakers / members / Lords / committee chairs are
named by upstream as the public record of parliamentary speech).
GDPR right-to-be-forgotten DSARs route through ``chigiri.data_privacy``
to upstream publisher (Parliament); religious-corp NEVER performs
unilateral removal.

Passive-only invariant: NEVER hits the Hansard live API at
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
from .base import GovParliamentObservation, ParliamentRecordKind


# Hansard native record-type strings → canonical ParliamentRecordKind.
# Source: parliament.uk Hansard publication categories.
_RECORD_KIND_MAP: dict[str, ParliamentRecordKind] = {
    "Debate": "debate",
    "Oral Question": "question",
    "Written Question": "question",
    "Written Statement": "member-statement",
    "Personal Statement": "member-statement",
    "Petition": "petition",
    "Committee": "committee",
    "Committee Stage": "committee",
    "Division": "vote",
    "Vote": "vote",
    "Bill": "bill",
    "Bill Reading": "bill",
}

# House code → legislature (Commons / Lords both feed into uk-parliament).
_HOUSE_VALUES: set[str] = {"Commons", "Lords"}


def _canonical_record_kind(native: str) -> ParliamentRecordKind | None:
    """Map a Hansard native record-type string to canonical enum.

    Returns ``None`` if unknown — sensor then skips per G7 schema
    discipline.
    """
    return _RECORD_KIND_MAP.get(native)


@dataclass
class UkHansardSensor:
    """Sensor over a ``gov/parliament/gbr/hansard/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - recordId             (per-Hansard canonical ID; required)
      - sessionDateUtc       (ISO-8601 UTC; required)
      - payloadCid           (IPFS CID of normalized payload; required)
      - house                ("Commons" | "Lords"; required)
      - recordKind OR nativeKind  (canonical kind OR Hansard native
                                   type for canonical mapping; required)
      - bodyExcerpt          (optional short excerpt; full body in
                              payloadCid)
      - speakerName          (optional; pass-through per §5)
      - speakerRole          (optional; e.g. "MP", "Lord", "Speaker",
                              "Minister", etc.)

    G7 schema discipline: rows missing required fields OR with
    unmappable `nativeKind` (and no explicit `recordKind`) are skipped
    without halting the stream.
    """

    name: str = "gov/parliament/gbr/hansard"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "OGL-v3.0"
    tier: Tier = "A"
    # Hansard publishes within ~24h of sittings; daily refresh.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "GBR"
    legislature: str = "uk-parliament"
    # Optional filter: only yield records from a specific House
    # ("Commons" or "Lords"). "" = both Houses pass.
    house_filter: str = ""
    # Optional record-kind filter (canonical enum values).
    record_kind_filter: tuple[ParliamentRecordKind, ...] = ()
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

    def stream(self, pin: DatasetPin) -> Iterator[GovParliamentObservation]:
        sensor_name = self.name
        house_filter = self.house_filter
        kind_filter_set = (
            set(self.record_kind_filter) if self.record_kind_filter else None
        )
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
                    record_id = str(row.get("recordId", "")).strip()
                    session_date_utc = str(row.get("sessionDateUtc", "")).strip()
                    payload_cid = str(row.get("payloadCid", "")).strip()
                    house = str(row.get("house", "")).strip()
                    if not (record_id and session_date_utc and payload_cid and house):
                        # G7 — required field missing.
                        continue
                    if house not in _HOUSE_VALUES:
                        # G7 — unknown house value (typo / data error).
                        continue
                    if house_filter and house != house_filter:
                        continue
                    # Resolve canonical record kind.
                    record_kind_raw = row.get("recordKind")
                    record_kind: ParliamentRecordKind | None
                    if isinstance(record_kind_raw, str) and record_kind_raw:
                        record_kind = record_kind_raw  # type: ignore[assignment]
                    else:
                        native_kind = str(row.get("nativeKind", "")).strip()
                        record_kind = _canonical_record_kind(native_kind)
                    if record_kind is None:
                        # G7 — kind unresolvable; skip.
                        continue
                    if kind_filter_set is not None and record_kind not in kind_filter_set:
                        continue
                    yield GovParliamentObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        jurisdiction_iso3=self.jurisdiction_iso3,
                        legislature=self.legislature,
                        record_kind=record_kind,
                        record_id=record_id,
                        body_excerpt=str(row.get("bodyExcerpt", ""))[:8192],
                        speaker_name=(
                            str(row["speakerName"])
                            if "speakerName" in row and row["speakerName"]
                            else None
                        ),
                        speaker_role=(
                            str(row["speakerRole"])
                            if "speakerRole" in row and row["speakerRole"]
                            else None
                        ),
                        session_date_utc=session_date_utc,
                        license_tag=self.license,
                        payload_cid=payload_cid,
                        state_aligned_flag=False,  # UK is not §2(g)-flagged
                        internal_only=False,
                        pii_redacted=bool(row.get("piiRedacted", False)),
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovParliamentObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[GovParliamentObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["UkHansardSensor"]
