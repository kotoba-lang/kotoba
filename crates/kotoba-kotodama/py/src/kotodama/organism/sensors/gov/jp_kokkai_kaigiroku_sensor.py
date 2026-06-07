"""JpKokkaiKaigirokuSensor — Wave-1 anchor: ``gov/parliament/jpn/kokkai-kaigiroku``.

Per ADR-2605263900. 国会会議録検索 (Kokkai Kaigiroku Kensaku — National
Diet meeting records search) is the official archive of Japanese
Diet meeting records (both Houses, all committees, since 1947).
Published by the National Diet Library (国会図書館) under 著作権法 §13
as 公の著作物 (official government work) — free use as a public
record. Tier-A.

This sensor reads the per-record NDJSON view emitted by the (TODO W1)
``jp_kokkai_kaigiroku.py`` fetcher. One row per record →
``GovParliamentObservation`` with ``legislature="jp-kokkai"``.

Sibling of :class:`UkHansardSensor` (UK Parliament) +
:class:`UsCongressGovSensor` (US Congress); the three share the
``GovParliamentObservation`` yield contract and disambiguate via the
``legislature`` field.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7.

Per ADR-2605263900 §5 publication-rule honoring: 国会会議録 pass-
through (議員 + 委員長 + 大臣 + 参考人 are named by upstream as the
public record of parliamentary speech). 個人情報保護法 + 国会会議録法
right-to-be-forgotten DSARs route through ``chigiri.data_privacy``
to upstream publisher (国会図書館); religious-corp NEVER performs
unilateral removal.

Passive-only invariant: NEVER hits the kokkai.ndl.go.jp live API at
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


# Diet native record-type strings → canonical ParliamentRecordKind.
# Source: kokkai.ndl.go.jp 会議名 + 質疑種別 taxonomy.
_RECORD_KIND_MAP: dict[str, ParliamentRecordKind] = {
    # 本会議 (plenary)
    "本会議": "debate",
    "予算委員会": "committee",
    "委員会": "committee",
    "連合審査会": "committee",
    "公聴会": "committee",
    "参考人質疑": "committee",
    # 質疑 / 質問 / 答弁
    "質疑": "question",
    "質問": "question",
    "代表質問": "question",
    "口頭質問": "question",
    "書面質問": "question",
    "答弁": "member-statement",
    "施政方針演説": "member-statement",
    "所信表明": "member-statement",
    # 法律案 / 決議案
    "法律案": "bill",
    "予算案": "bill",
    "条約承認案": "bill",
    "決議案": "bill",
    # 採決 (votes)
    "採決": "vote",
    "起立採決": "vote",
    "記名投票": "vote",
    "投票": "vote",
    # 請願 (petition)
    "請願": "petition",
    "陳情": "petition",
}

# Canonical Diet houses (Japanese forms).
_HOUSE_VALUES: set[str] = {"衆議院", "参議院"}


def _canonical_record_kind(native: str) -> ParliamentRecordKind | None:
    """Map a Diet native record-type string to canonical enum.

    Returns ``None`` if unknown — sensor skips per G7 schema discipline.
    """
    return _RECORD_KIND_MAP.get(native)


@dataclass
class JpKokkaiKaigirokuSensor:
    """Sensor over a ``gov/parliament/jpn/kokkai-kaigiroku/<rev>/`` subdataset.

    Expected NDJSON row shape (minimum):
      - recordId           (NDL canonical ID, e.g. "120814010X00420251205";
                            required)
      - sessionDateUtc     (ISO-8601 UTC of 開会日; required)
      - payloadCid         (IPFS CID of normalized payload; required)
      - house              ("衆議院" | "参議院"; required)
      - recordKind OR nativeKind  (canonical kind OR 会議名/質疑種別
                                   string for canonical mapping; required)
      - dietSession        (optional Diet session number, e.g. 217)
      - bodyExcerpt        (optional short excerpt; full body in payloadCid)
      - speakerName        (optional pass-through per §5)
      - speakerRole        (optional; e.g. "議員", "委員長", "国務大臣",
                            "内閣総理大臣", "参考人")

    G7 schema discipline: rows missing required fields OR with
    unmappable nativeKind (and no explicit recordKind) are skipped
    without halting the stream.
    """

    name: str = "gov/parliament/jpn/kokkai-kaigiroku"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "ndl-public-record-free-use"
    tier: Tier = "A"
    # NDL publishes 議事録 within ~3 days of sittings; daily refresh OK.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    jurisdiction_iso3: str = "JPN"
    legislature: str = "jp-kokkai"
    # Optional filter: only yield records from a specific house
    # ("衆議院" or "参議院"). "" = both houses pass.
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
                        state_aligned_flag=False,  # JP NOT §2(g)-flagged
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


__all__ = ["JpKokkaiKaigirokuSensor"]
