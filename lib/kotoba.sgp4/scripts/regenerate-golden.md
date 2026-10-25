# Regenerating the golden fixtures

Both fixtures under `test/sgp4/` are generated from oracles that share no
code with this implementation. Regenerate them only when adding cases --
never to make a failing test pass.

```bash
python3 -m venv /tmp/sgp4-oracle
/tmp/sgp4-oracle/bin/pip install sgp4 pyproj
/tmp/sgp4-oracle/bin/python scripts/gen_golden.py       > /tmp/g.json
/tmp/sgp4-oracle/bin/python scripts/gen_frames_golden.py > /tmp/f.json
kbb --backend sci scripts/json_to_edn.cljk /tmp/g.json test/sgp4/golden.edn
kbb --backend sci scripts/json_to_edn.cljk /tmp/f.json test/sgp4/frames_golden.edn
```

| fixture | oracle | what it bounds |
|---|---|---|
| `golden.edn` | python `sgp4` 2.27 (Vallado C++ port) | position/velocity, and which element sets are deep space |
| `frames_golden.edn` | `sgp4.propagation/gstime`; pyproj 3.7.2 / PROJ 9.5.1 | GMST; ECEF -> geodetic |

## Two things to know before touching a tolerance

**GMST agrees to ~8e-12 rad, not better.** The polynomial's dominant term
reaches 7.6e8 for a modern date; one ulp there becomes ~8.7e-12 rad after
scaling. A tolerance below that fails on summation order alone.

**PROJ is the looser side of the geodetic comparison.** Measured
2026-08-26, on 3 of the 12 fixture points PROJ's answer round-trips back to
ECEF 0.1-2.1 mm from the input while this implementation's lands under a
nanometre. The PROJ comparison is there to catch a wrong ellipsoid or a
degrees/radians slip; `geodetic-residual-is-sub-nanometre` is the tight
check. Tightening the PROJ tolerance does not make the suite stronger.

## The TLE lines are not transcribed from memory

The Vallado verification cases in the fixture are only the ones whose
modulo-10 check digits verify against `sgp4.tle/checksum` (itself checked
against 42 real CelesTrak lines). Two hand-typed cases failed that check
while this was being written, and were dropped rather than corrected: a bad
check digit means the *elements* are suspect too, not just column 69.
