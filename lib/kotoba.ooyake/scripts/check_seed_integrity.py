#!/usr/bin/env python3
"""check_seed_integrity.py — ooyake registry integrity guard (ADR-2606021600 §4/§5).

Institutionalizes the 2026-06-03 QID-fabrication finding: a contiguous fake Wikidata
block (Q1023xxx) had been hand-entered for the JP ministries — MOF's "Q1023766"
actually resolves to *CIUTI*, a Brussels translators' association, and MOF + MEXT
shared the same fake QID. This checker fails on the structural tells of that class so
it cannot silently recur as the real G20 dataset grows.

Loads EVERY `registry/gov-units*.edn` (glob — new files like gov-units.g20.edn are
covered automatically) + authority-reference.edn.

Checks (each a hard ERROR):
  1. duplicate :gov.unit/wikidata across distinct units      (the MOF/MEXT tell)
  2. malformed Wikidata QID (must match ^Q[1-9][0-9]*$)
  3. G5: every unit carries :gov.unit/{sourcing,provenance,last-verified}
  4. sourcing ∈ {:authoritative,:representative}; verification-status ∈
     {:unverified-seed,:maintainer-verified,:stale}
  5. addresses: :gov.address/unit resolves to a known unit; sourcing enum valid;
     address id unique
  6. authority-reference :wikidata/:official-url AGREE with the seed unit; no
     dangling authority record

READ-ONLY (G9): inspects committed registry files, never writes.

Usage:
    python3 check_seed_integrity.py            # human report, exit 1 on any ERROR
    python3 check_seed_integrity.py --quiet     # only print on failure
"""
from __future__ import annotations

import glob
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import load_authority, parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))
_QID_RE = re.compile(r"^Q[1-9][0-9]*$")
_G5_REQUIRED = (":gov.unit/sourcing", ":gov.unit/provenance", ":gov.unit/last-verified")
_SOURCING_OK = {":authoritative", ":representative"}
_VSTATUS_OK = {":unverified-seed", ":maintainer-verified", ":stale", None}
# must mirror gov-atlas-ontology.kotoba.edn :gov.unit/level and :gov.unit/branch enums
_LEVEL_OK = {":supranational", ":country", ":region", ":subdivision", ":prefecture",
             ":municipality", ":ward", ":ministry", ":agency", ":bureau", ":division",
             ":section", ":madoguchi", ":legislature", ":court", ":cabinet"}
_BRANCH_OK = {":executive", ":legislative", ":judicial", ":independent", ":local",
              ":intergovernmental", None}


def seed_files() -> list[str]:
    return sorted(glob.glob(os.path.join(_REG, "gov-units*.edn")))


def load_all_units(files: list[str]) -> dict[str, dict]:
    units: dict[str, dict] = {}
    dupes: list[str] = []
    for f in files:
        doc = parse_edn(open(f, encoding="utf-8").read())
        for u in doc.get(":units", []):
            uid = u.get(":gov.unit/id")
            if not uid:
                continue
            if uid in units:
                dupes.append(uid)
            units[uid] = u
    load_all_units._dupes = dupes  # type: ignore[attr-defined]
    return units


def check(files=None, auth_file=None) -> list[str]:
    files = files or seed_files()
    units = load_all_units(files)
    errors: list[str] = []

    for uid in getattr(load_all_units, "_dupes", []):
        errors.append(f"[duplicate-unit-id] {uid} defined in more than one seed file")

    seen: dict[str, str] = {}
    for uid, u in sorted(units.items()):
        qid = u.get(":gov.unit/wikidata")
        if qid is not None:
            if not _QID_RE.match(qid):
                errors.append(f"[malformed-qid] {uid}: {qid!r} is not a valid Wikidata QID")
            if qid in seen:
                errors.append(
                    f"[duplicate-qid] {qid} used by BOTH {seen[qid]} and {uid} "
                    f"(two government bodies cannot share one Wikidata entity)"
                )
            else:
                seen[qid] = uid
        for key in _G5_REQUIRED:
            if not u.get(key):
                errors.append(f"[g5-missing] {uid}: missing {key} (provenance discipline)")
        if u.get(":gov.unit/sourcing") not in _SOURCING_OK:
            errors.append(f"[bad-sourcing] {uid}: {u.get(':gov.unit/sourcing')!r}")
        if u.get(":gov.unit/level") not in _LEVEL_OK:
            errors.append(f"[bad-level] {uid}: {u.get(':gov.unit/level')!r} not in ontology :gov.unit/level enum")
        if u.get(":gov.unit/branch") not in _BRANCH_OK:
            errors.append(f"[bad-branch] {uid}: {u.get(':gov.unit/branch')!r} not in ontology :gov.unit/branch enum")
        if u.get(":gov.unit/verification-status") not in _VSTATUS_OK:
            errors.append(f"[bad-verification-status] {uid}: {u.get(':gov.unit/verification-status')!r}")
        parent = u.get(":gov.unit/parent")
        if parent and parent not in units:
            errors.append(f"[dangling-parent] {uid}: :parent {parent!r} is not a known gov.unit")

    # addresses
    addr_seen: dict[str, str] = {}
    for f in files:
        doc = parse_edn(open(f, encoding="utf-8").read())
        for a in doc.get(":addresses", []):
            aid = a.get(":gov.address/id")
            if aid and aid in addr_seen:
                errors.append(f"[duplicate-address-id] {aid} in {os.path.basename(f)} and {addr_seen[aid]}")
            elif aid:
                addr_seen[aid] = os.path.basename(f)
            au = a.get(":gov.address/unit")
            if au and au not in units:
                errors.append(f"[dangling-address] {aid}: :unit {au!r} is not a known gov.unit")
            if a.get(":gov.address/sourcing") not in _SOURCING_OK:
                errors.append(f"[bad-address-sourcing] {aid}: {a.get(':gov.address/sourcing')!r}")

    auth = load_authority(auth_file or os.path.join(_REG, "authority-reference.edn"))
    for unit_id, rec in sorted(auth.items()):
        u = units.get(unit_id)
        if u is None:
            errors.append(f"[dangling-authority] authority record for unknown unit {unit_id!r}")
            continue
        if u.get(":gov.unit/wikidata") != rec.get(":wikidata"):
            errors.append(
                f"[authority-qid-mismatch] {unit_id}: seed={u.get(':gov.unit/wikidata')!r} "
                f"authority={rec.get(':wikidata')!r}"
            )
        if u.get(":gov.unit/official-url") != rec.get(":official-url"):
            errors.append(f"[authority-url-mismatch] {unit_id}")
    return errors


def main() -> int:
    quiet = "--quiet" in sys.argv
    files = seed_files()
    errors = check(files)
    units = load_all_units(files)
    n_qid = sum(1 for u in units.values() if u.get(":gov.unit/wikidata"))
    n_auth = sum(1 for u in units.values() if u.get(":gov.unit/sourcing") == ":authoritative")
    if errors:
        print("ooyake registry integrity: FAIL")
        for e in errors:
            print(f"  ✗ {e}")
        print(f"  ({len(errors)} error(s); {len(units)} units across {len(files)} files)")
        return 1
    if not quiet:
        print("ooyake registry integrity: OK")
        print(f"  {len(units)} units across {len(files)} files; {n_qid} with QIDs "
              f"(all unique + well-formed); {n_auth} :authoritative; G5 present; "
              f"authority-reference agrees with seed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
