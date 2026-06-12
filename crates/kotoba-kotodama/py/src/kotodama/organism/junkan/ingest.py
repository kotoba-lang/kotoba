"""junkan.ingest — turn passive public-archive samples into stock series.

ADR-2605290927 + ADR-2605262400 (PASSIVE-ONLY). This adapter maps already-fetched
aggregate observations (the kind a passive DatasetSensor produces from a
pre-published public archive) into ``StockSeries``. It performs **no network I/O,
no live probing, no inference** — it only reshapes rows that were collected
elsewhere under the passive-only discipline.

G3: every row MUST carry a ``source_cid`` (public-archive provenance).
G6: aggregate-only — rows carrying an individual/person field are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import StockSeries

_INDIVIDUAL_KEYS = {"person", "person_id", "individual", "name", "email", "handle", "did_subject"}


def series_from_observations(rows: list[dict]) -> list[StockSeries]:
    """Group aggregate observation rows by ``stock_id`` into ordered series.

    Each row: ``{stock_id, level:int, unit, desirability:+1/-1, source_cid,
    valid_time}``. Rows are ordered by ``valid_time`` within a stock.
    """
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        leak = _INDIVIDUAL_KEYS & set(r)
        if leak:  # G6 STRUCTURAL
            raise ValueError(f"G6 aggregate-only: individual field(s) {sorted(leak)} rejected")
        if not r.get("source_cid"):  # G3 STRUCTURAL
            raise ValueError("G3 passive-only: every observation MUST carry a source_cid")
        grouped.setdefault(r["stock_id"], []).append(r)

    out: list[StockSeries] = []
    for sid, rs in grouped.items():
        rs.sort(key=lambda r: r.get("valid_time", ""))
        first = rs[0]
        out.append(
            StockSeries(
                stock_id=sid,
                levels=[int(r["level"]) for r in rs],
                unit=first.get("unit", ""),
                desirability=int(first.get("desirability", 1)),
                source_cid=first["source_cid"],
            )
        )
    return out


def load_fixture(path: str | Path) -> list[StockSeries]:
    """Load a JSON fixture of aggregate observation rows into stock series.

    Used for offline dry-runs (no fleet, no network). The production path
    resolves a passive DatasetSensor pin instead (R1, Council-gated).
    """
    rows = json.loads(Path(path).read_text())
    return series_from_observations(rows)
