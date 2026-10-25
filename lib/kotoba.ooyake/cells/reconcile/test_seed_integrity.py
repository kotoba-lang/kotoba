"""Tests for ooyake's registry integrity guard (scripts/check_seed_integrity.py).

Proves the guard (a) passes on the committed registry and (b) actually FIRES on the
class of bug it exists to catch — the 2026-06-03 QID-fabrication finding (duplicate
QIDs, malformed QIDs, missing G5 provenance, bad enum, dangling address, circular
authority).

Run: python3 -m pytest cells/reconcile/test_seed_integrity.py
 or: python3 cells/reconcile/test_seed_integrity.py
"""
from __future__ import annotations

import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "scripts")))
from check_seed_integrity import check  # noqa: E402


def test_committed_registry_is_clean():
    assert check() == []


def _w(tmp, name, body):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    return p


_GOOD = (
    '{:gov.unit/id "gov.x" :gov.unit/wikidata "Q1" '
    ':gov.unit/level :country :gov.unit/branch :executive '
    ':gov.unit/official-url "https://x/" :gov.unit/sourcing :authoritative '
    ':gov.unit/provenance "https://x/" :gov.unit/last-verified "2026-06-03" '
    ':gov.unit/verification-status :maintainer-verified}'
)


def test_bad_level_fires():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        seed = _w(tmp, "gov-units.s.edn",
                  '{:units [{:gov.unit/id "gov.z" :gov.unit/wikidata "Q9" '
                  ':gov.unit/level :galaxy :gov.unit/branch :executive '
                  ':gov.unit/sourcing :authoritative :gov.unit/provenance "https://z/" '
                  ':gov.unit/last-verified "2026-06-03"}]}')
        auth = _w(tmp, "authority-reference.edn", "{:authority-records []}")
        assert any("bad-level" in e for e in check([seed], auth))


def test_duplicate_qid_fires():
    with tempfile.TemporaryDirectory() as tmp:
        seed = _w(tmp, "gov-units.s.edn",
                  '{:units [' + _GOOD + ' '
                  '{:gov.unit/id "gov.y" :gov.unit/wikidata "Q1" '
                  ':gov.unit/official-url "https://y/" :gov.unit/sourcing :authoritative '
                  ':gov.unit/provenance "https://y/" :gov.unit/last-verified "2026-06-03" '
                  ':gov.unit/verification-status :maintainer-verified}]}')
        auth = _w(tmp, "authority-reference.edn", "{:authority-records []}")
        assert any("duplicate-qid" in e for e in check([seed], auth))


def test_malformed_qid_missing_g5_and_bad_enum_fire():
    with tempfile.TemporaryDirectory() as tmp:
        seed = _w(tmp, "gov-units.s.edn",
                  '{:units [{:gov.unit/id "gov.bad" :gov.unit/wikidata "1023766" '
                  ':gov.unit/official-url "https://b/" :gov.unit/sourcing :bogus}]}')
        auth = _w(tmp, "authority-reference.edn", "{:authority-records []}")
        errs = check([seed], auth)
        assert any("malformed-qid" in e for e in errs), errs
        assert any("g5-missing" in e for e in errs), errs
        assert any("bad-sourcing" in e for e in errs), errs


def test_dangling_address_and_authority_mismatch_fire():
    with tempfile.TemporaryDirectory() as tmp:
        seed = _w(tmp, "gov-units.s.edn",
                  '{:units [' + _GOOD + '] '
                  ':addresses [{:gov.address/id "a1" :gov.address/unit "gov.ghost" '
                  ':gov.address/sourcing :authoritative}]}')  # dangling addr
        auth = _w(tmp, "authority-reference.edn",
                  '{:authority-records [{:unit "gov.x" :wikidata "Q999" :official-url "https://x/"}]}')
        errs = check([seed], auth)
        assert any("dangling-address" in e for e in errs), errs
        assert any("authority-qid-mismatch" in e for e in errs), errs


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
