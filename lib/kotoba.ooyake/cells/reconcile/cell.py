"""ReconcileCell — ooyake R1 reconcile cell (ADR-2606021600 §5).

Reconciles each :gov.unit against external authorities and promotes
    :representative / :unverified-seed → :authoritative / :maintainer-verified
ONLY when :gov.unit/wikidata AND :gov.unit/official-url AGREE with the authority
record (G5: agreement = verification; disagreement → kept unverified + reported).

Two modes:
  mode="bundled" (default) — reconcile against the bundled, curated
      registry/authority-reference.edn. OFFLINE, deterministic, NOT gated. This is
      what runs at R1 to prove the mechanism and produce promotion reports.
  mode="live" — fetch from real external authorities (Wikidata /
      行政機関コード / 全国地方公共団体コード / GeoNames). RAISES: G4 + Council Lv6+
      + operator enablement required (public-data-only, ToS/rate-limit discipline).

This cell is READ-SIDE (G9): it produces a promotion *report*. It never files,
submits, or mutates a government record, and it never writes to the canonical seed
— applying promotions to committed state is a separate operator-gated step.
"""

from __future__ import annotations

import json
import os
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_REG = os.path.normpath(os.path.join(_HERE, "..", "..", "registry"))
DEFAULT_SEED_FILES = [
    os.path.join(_REG, "gov-units.seed.edn"),
    os.path.join(_REG, "gov-units.jp-central.seed.edn"),
]
DEFAULT_AUTH_FILE = os.path.join(_REG, "authority-reference.edn")


# ── minimal EDN reader (maps / vectors / strings / keywords / numbers / comments)
def parse_edn(src: str) -> Any:
    i, n = 0, len(src)

    def skip() -> None:
        nonlocal i
        while i < n:
            c = src[i]
            if c in " \t\r\n,":
                i += 1
                continue
            if c == ";":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            break

    def read() -> Any:
        nonlocal i
        skip()
        c = src[i]
        if c == '"':
            return read_str()
        if c == "{":
            return read_map()
        if c == "[":
            return read_vec()
        return read_atom()

    def read_str() -> str:
        nonlocal i
        i += 1
        out: list[str] = []
        while i < n:
            c = src[i]
            i += 1
            if c == "\\":
                e = src[i]
                i += 1
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(e, e))
            elif c == '"':
                return "".join(out)
            else:
                out.append(c)
        raise ValueError("unterminated string")

    def read_vec() -> list:
        nonlocal i
        i += 1
        arr = []
        while True:
            skip()
            if src[i] == "]":
                i += 1
                return arr
            arr.append(read())

    def read_map() -> dict:
        nonlocal i
        i += 1
        d: dict = {}
        while True:
            skip()
            if src[i] == "}":
                i += 1
                return d
            k = read()
            v = read()
            d[k] = v

    def read_atom() -> Any:
        nonlocal i
        start = i
        while i < n and src[i] not in " \t\r\n,;{}[]\"":
            i += 1
        tok = src[start:i]
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "nil":
            return None
        if tok.startswith(":"):
            return tok
        try:
            return int(tok)
        except ValueError:
            try:
                return float(tok)
            except ValueError:
                return tok

    skip()
    return read()


def load_units(seed_files: list[str]) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for f in seed_files:
        doc = parse_edn(open(f, encoding="utf-8").read())
        for u in doc.get(":units", []):
            uid = u.get(":gov.unit/id")
            if uid:
                units[uid] = u
    return units


def load_authority(auth_file: str) -> dict[str, dict]:
    doc = parse_edn(open(auth_file, encoding="utf-8").read())
    return {r[":unit"]: r for r in doc.get(":authority-records", [])}


def reconcile(
    seed_files: list[str] | None = None,
    auth_file: str | None = None,
) -> dict[str, Any]:
    """Core bundled reconcile. Pure function — no network, no writes."""
    units = load_units(seed_files or DEFAULT_SEED_FILES)
    auth = load_authority(auth_file or DEFAULT_AUTH_FILE)
    promoted: list[str] = []
    conflicts: list[dict] = []
    no_authority: list[str] = []
    for uid, u in sorted(units.items()):
        rec = auth.get(uid)
        if rec is None:
            no_authority.append(uid)
            continue
        wd_ok = u.get(":gov.unit/wikidata") == rec.get(":wikidata")
        url_ok = u.get(":gov.unit/official-url") == rec.get(":official-url")
        if wd_ok and url_ok:
            promoted.append(uid)
        else:
            conflicts.append(
                {
                    "unit": uid,
                    "wikidata_match": wd_ok,
                    "official_url_match": url_ok,
                }
            )
    total = len(units)
    return {
        "mode": "bundled",
        "total_units": total,
        "authority_records": len(auth),
        "promoted_to_authoritative": sorted(promoted),
        "conflicts_kept_unverified": conflicts,
        "no_authority_record_kept_representative": sorted(no_authority),
        "coverage": {
            "authoritative_after": len(promoted),
            "representative_after": total - len(promoted),
            "authoritative_pct": round(100.0 * len(promoted) / total, 1) if total else 0.0,
        },
    }


class ReconcileCell:
    """ooyake reconcile cell. solve(state) → promotion report (G9 read-side)."""

    def __init__(self) -> None:
        pass

    def solve(self, state: dict[str, Any]) -> dict[str, Any]:
        mode = (state or {}).get("mode", "bundled")
        if mode == "live":
            raise RuntimeError(
                "ooyake reconcile LIVE mode not activated (G4). Live fetch of "
                "Wikidata / 行政機関コード / 全国地方公共団体コード / GeoNames is "
                "public-data-only + ToS/rate-limit-disciplined and requires Council "
                "Lv6+ ratify (ADR-2606021600) + operator enablement. Use mode='bundled' "
                "for the offline, deterministic reconcile."
            )
        if mode != "bundled":
            raise ValueError(f"unknown reconcile mode: {mode!r} (expected 'bundled' or 'live')")
        report = reconcile(
            state.get("seed_files") if state else None,
            state.get("auth_file") if state else None,
        )
        return {"status": "ok", "report": report}
