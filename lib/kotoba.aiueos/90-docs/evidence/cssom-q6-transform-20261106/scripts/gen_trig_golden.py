#!/usr/bin/env python3
"""ONE-TIME golden-table generator for the Q17 sin / cos / tan of cssom.trig-q6 (JUN-929 / C2b-4, census group G05).

This script is an ORACLE RUN, not part of any gate: the native gate only reads its OUTPUT (trig-golden.tsv, trig_golden.kotoba) and
pins their sha256. Python's `math` is the oracle the task asked for; an INDEPENDENT second computation (exact decimal angle, pi from
Machin's formula with integers, Taylor series in 10^70-scaled integers, no `math`) is run on every row and any disagreement
between the two after rounding is recorded in trig-golden-meta.json (it must be empty, or the row is listed).

Row = (unit, v) with v the D6 integer (millionths of the unit); unit 1 deg, 2 grad, 3 rad, 4 turn.
Rounding rule of the golden: floor(x * 2^k + 1/2) on the exact double / exact rational (round half up, like the Q6 modules).
tan is INV when the rounded |tan| * 2^17 exceeds 8388607 (|tan| >= 64) or cos is exactly 0 (the quadrant edge for deg/grad/turn).

usage: gen_trig_golden.py OUTDIR
"""
import hashlib, json, math, platform, random, sys, datetime
from fractions import Fraction as F
from pathlib import Path

LIMIT = {1: 11520000000, 2: 12800000000, 3: 201061929, 4: 32000000}
INV = None


def machin_pi(prec=110):
    def atan_inv(x):
        one = 10 ** prec
        s = t = one // x
        x2 = x * x
        n, sign = 1, -1
        while t:
            t //= x2
            n += 2
            s += sign * (t // n)
            sign = -sign
        return s
    return F(4 * (4 * atan_inv(5) - atan_inv(239)), 10 ** prec)


PI = machin_pi()
S = 10 ** 70


def hp_sincos(unit, v):
    """exact sin, cos of the decimal angle, as integers scaled by S (independent of `math`)"""
    x = F(v, 10 ** 6) * {1: PI / 180, 2: PI / 200, 3: F(1), 4: 2 * PI}[unit]
    twopi = 2 * PI
    x -= twopi * math.floor(x / twopi)           # now in [0, 2 pi)
    X = (x.numerator * S) // x.denominator
    # Taylor in scaled integers
    # sin
    t = X
    n = 1
    sin = 0
    while t:
        sin += t if (n // 2) % 2 == 0 else -t
        t = t * X // S * X // S // ((n + 1) * (n + 2))
        n += 2
    t = S
    n = 0
    cos = 0
    while t:
        cos += t if (n // 2) % 2 == 0 else -t
        t = t * X // S * X // S // ((n + 1) * (n + 2))
        n += 2
    return sin, cos


def rnd_frac(num, den, k):
    """floor(num/den * 2^k + 1/2)"""
    return (2 * num * (2 ** k) + den) // (2 * den)


def rnd_float(x, k):
    f = F(x) * (2 ** k)
    return (2 * f.numerator + f.denominator) // (2 * f.denominator)


def radians_of(unit, v):
    x = v / 1e6
    return {1: math.radians(x), 2: x * math.pi / 200.0, 3: x, 4: x * 2.0 * math.pi}[unit]


def rows_grid():
    rng = random.Random(20261106)
    r = []
    # degrees
    r += [(1, i * 10 ** 6) for i in range(-720, 721)]                       # every degree, +-2 turns
    r += [(1, i * 10 ** 5) for i in range(0, 3600)]                         # every 0.1 degree over one turn
    pole = [85000000 + i * 10000 for i in range(0, 421)]                    # 85.00 .. 89.20 deg step 0.01 (tan 11.4 .. 71.6)
    r += [(1, p) for p in pole] + [(1, -p) for p in pole] + [(1, p + 180000000) for p in pole]
    r += [(1, s * x) for x in (1, 2, 3, 5, 10, 100, 1000, 10000) for s in (1, -1)]
    r += [(1, rng.randint(-LIMIT[1], LIMIT[1])) for _ in range(1000)]
    for k in range(-8, 9):                                                     # multiples of 45 deg and neighbours
        for d in (-2, -1, 0, 1, 2):
            r.append((1, k * 45000000 + d))
    for e in (LIMIT[1], LIMIT[1] - 1, LIMIT[1] + 1, LIMIT[1] + 90000000, -LIMIT[1], -LIMIT[1] + 1, -LIMIT[1] - 1):
        r.append((1, e))
    # gradians
    r += [(2, i * 10 ** 6) for i in range(-800, 801)]
    r += [(2, rng.randint(-LIMIT[2], LIMIT[2])) for _ in range(400)]
    r += [(2, e) for e in (LIMIT[2], LIMIT[2] - 1, LIMIT[2] + 1, -LIMIT[2], -LIMIT[2] - 1, 100000000, 99999999, 100000001, 50000000, 150000000)]
    # radians
    r += [(3, i * 250000) for i in range(-804, 805)]                          # step 0.25 rad over +-201
    r += [(3, rng.randint(-LIMIT[3], LIMIT[3]) // 1 ) for _ in range(600)]
    r += [(3, e) for e in (0, 1, 1570796, 1570797, 3141592, 3141593, 4712388, 4712389, 6283185, 6283186, 785398, 785399,
                           LIMIT[3], LIMIT[3] - 1, LIMIT[3] + 1, -LIMIT[3], -LIMIT[3] - 1, 1000000, -1000000, 1569796, 1571796)]
    # turns
    r += [(4, i * 62500) for i in range(-512, 513)]                           # step 1/16 turn over +-32
    r += [(4, rng.randint(-LIMIT[4], LIMIT[4])) for _ in range(400)]
    r += [(4, e) for e in (LIMIT[4], LIMIT[4] - 1, LIMIT[4] + 1, -LIMIT[4], -LIMIT[4] - 1, 250000, 249999, 250001, 125000, 124999, 125001, 1, -1)]
    # de-duplicate, keep order
    seen, out = set(), []
    for x in r:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def main(outdir):
    out = Path(outdir)
    rows = rows_grid()
    tsv = ['id\tunit\tv\tsin17\tcos17\ttan17\tsin30\tcos30']
    meta_dis = []
    recs = []
    for i, (u, v) in enumerate(rows):
        if abs(v) > LIMIT[u]:
            rec = (i, u, v, INV, INV, INV, INV, INV)
        else:
            x = radians_of(u, v)
            ms, mc, mt = math.sin(x), math.cos(x), math.tan(x)
            hs, hc = hp_sincos(u, v)
            s17, c17 = rnd_float(ms, 17), rnd_float(mc, 17)
            s30, c30 = rnd_float(ms, 30), rnd_float(mc, 30)
            hs17, hc17 = rnd_frac(hs, S, 17), rnd_frac(hc, S, 17)
            hs30, hc30 = rnd_frac(hs, S, 30), rnd_frac(hc, S, 30)
            # tan from the exact rational sin / cos
            if hc == 0:
                t17 = INV
            else:
                # exact: the independent rational is hs/hc; sign and magnitude
                num, den = hs, hc
                if den < 0:
                    num, den = -num, -den
                t = rnd_frac(num, den, 17)
                t17 = INV if abs(t) > 8388607 else t
            # an exact quadrant edge has cos = 0 up to 1e-70 in the series: treat |cos| < 1e-60 as exactly zero (deg/grad/turn only)
            if u != 3 and abs(hc) < 10 ** 10:
                t17 = INV
            if (s17, c17, s30, c30) != (hs17, hc17, hs30, hc30):
                meta_dis.append({'id': i, 'unit': u, 'v': v, 'math': [s17, c17, s30, c30], 'hp': [hs17, hc17, hs30, hc30]})
            rec = (i, u, v, s17, c17, t17, s30, c30)
        recs.append(rec)
        tsv.append('\t'.join('INV' if x is None else str(x) for x in rec))
    (out / 'trig-golden.tsv').write_text('\n'.join(tsv) + '\n')

    # ---- native data module: balanced if-trees on the row index (the host compiler takes this in 3 s) ----
    def tree(vals, lo, hi, depth=0):
        if hi - lo == 1:
            return str(vals[lo])
        m = (lo + hi) // 2
        return '(if (< i %d) %s %s)' % (m, tree(vals, lo, m), tree(vals, m, hi))
    n = len(recs)
    inp, q17, s30c = [], [], []
    for (i, u, v, s17, c17, t17, s30, c30) in recs:
        inp.append(u + 8 * (v + 2 ** 35))                                   # unit (3 bits) | v + 2^35 (36 bits)
        if s17 is None:
            q17.append(0)
        else:
            tf = 0 if t17 is None else t17 + 2 ** 23
            q17.append((s17 + 2 ** 18) + ((c17 + 2 ** 18) << 19) + (tf << 38))
    s30l, c30l = [], []
    for k in range(0, n, 4):
        s30, c30 = recs[k][6], recs[k][7]
        s30l.append(0 if s30 is None else s30 + 2 ** 30 + 1)                 # +1: 0 stays "invalid"
        c30l.append(0 if c30 is None else c30 + 2 ** 30 + 1)
    mod = ['(ns cssom.trig-golden (:export [rows g-in g-q17 g-s30 g-c30]))',
           ';; GENERATED by scripts/gen_trig_golden.py (one-time Python oracle run). DATA, not code. Do not edit.',
           ';; rows: number of golden rows. g-in i = unit + 8 * (v + 2^35).',
           ';; g-q17 i = (sin17 + 2^18) + (cos17 + 2^18) * 2^19 + (tan17 + 2^23) * 2^38, 0 = invalid (outside the domain); the tan field alone is 0',
           ';;   when tan is refused (|tan| >= 64 or cos = 0).',
           ';; g-s30 j / g-c30 j for row 4 j: Q30 + 2^30 + 1, 0 = invalid.',
           '(defn rows [] :i64 %d)' % n,
           '(defn g-in [i :i64] :i64 %s)' % tree(inp, 0, n),
           '(defn g-q17 [i :i64] :i64 %s)' % tree(q17, 0, n),
           '(defn g-s30 [i :i64] :i64 %s)' % tree(s30l, 0, len(s30l)),
           '(defn g-c30 [i :i64] :i64 %s)' % tree(c30l, 0, len(c30l))]
    (out / 'trig_golden.kotoba').write_text('\n'.join(mod) + '\n')
    meta = {'date': str(datetime.date.today()), 'python': platform.python_version(), 'platform': platform.platform(),
            'rows': n, 'command': 'python3 scripts/gen_trig_golden.py <evidence dir>',
            'seed': 20261106, 'rows_by_unit': {str(u): sum(1 for r in rows if r[0] == u) for u in (1, 2, 3, 4)},
            'domainInvalidRows': sum(1 for r in recs if r[3] is None),
            'tanInvalidRows': sum(1 for r in recs if r[3] is not None and r[5] is None),
            'math_vs_independent_disagreements': meta_dis,
            'sha256': {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in ('trig-golden.tsv', 'trig_golden.kotoba')}}
    (out / 'trig-golden-meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps({k: meta[k] for k in ('rows', 'rows_by_unit', 'domainInvalidRows', 'tanInvalidRows')}), 'disagreements', len(meta_dis))


if __name__ == '__main__':
    main(sys.argv[1])
