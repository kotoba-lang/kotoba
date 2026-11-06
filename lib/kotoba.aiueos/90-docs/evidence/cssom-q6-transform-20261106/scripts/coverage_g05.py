#!/usr/bin/env python3
"""Map the strong float hits of census group G05 (float-sites.tsv) to the Q-scale functions that replace them (JUN-929 / C2b-4).

Reads ../cssom-port-census-20261106/float-sites.tsv, counts strong G05 hits per enclosing definition of layout.cljk and prints a
table; the mapping column is the author's assignment (a reading, not a measurement). Run: python3 scripts/coverage_g05.py > coverage-g05.tsv
"""
import collections, csv, sys
from pathlib import Path
CENSUS = Path(__file__).resolve().parents[2] / 'cssom-port-census-20261106'
MAP = {
    'identity-matrix': 'transform-q6: ident-ab, ident-cd, zero-ef (1.0 and 0.0 literals become Q17 131072 and 0)',
    'round-4': 'transform-q6: every output is rounded once to Q6 half up (rdiv inside map-x2, map-y2, mul-*, about-ef); no float round-trip',
    'transform-length': 'EXISTING: parse-px-q6 (px, %) + length-q6 percent-of (slice 1); the unitless zero is the host\'s',
    'transform-angle': 'trig-q6: unit codes, domain limits, exact quadrant reduction (deg, grad, turn) and the pi/2 reduction (rad); Math/PI constants become integers',
    'transform-function-matrix': 'transform-q6: scale-ab/cd, rotate-ab/cd, skew-ab/cd, mk-tr (translate), coef-of-number (matrix(), scale()); sin/cos/tan = trig-q6',
    'transform-origin-point': 'transform-q6: origin-coord (kinds 0..4)',
    'transform-ops': 'transform-q6: map-x/map-y, xs-min..ys-max, bbox-x/y/w/h, uniform-scale (sqrt|det|, Math/sqrt + Math/abs), font-scale',
    'apply-element-transform': 'transform-q6: about-ef (the T(c) x M x T(-c) conjugation in one rounding) and mul-ab/cd/ef',
    'flow-rotation': 'transform-q6: flow-rotation, signed permutations by determinant +-1 (four (/ .. det) sites), exact integers',
    'orthogonal-fallback-inline-size': 'transform-q6: orthogonal-fallback (1e7 px = 640000000 Q6)',
}
rows = [r for r in csv.DictReader((CENSUS / 'float-sites.tsv').open(), delimiter='\t') if r['group'] == 'G05-transform-matrix' and r['strong'] == '1']
count = collections.Counter(r['enclosing_def'] for r in rows)
print('enclosing_def\tstrong_hits\tport')
for k, v in sorted(count.items(), key=lambda kv: -kv[1]):
    print('%s\t%d\t%s' % (k, v, MAP.get(k, 'UNMAPPED')))
print('TOTAL\t%d\t' % sum(count.values()), file=sys.stderr)
print('unmapped\t%d\t' % sum(v for k, v in count.items() if k not in MAP), file=sys.stderr)
