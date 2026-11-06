#!/usr/bin/env python3
"""ONE-TIME exact-rational reference generator for cssom.transform-q6 (JUN-929 / C2b-4, census group G05).

An ORACLE RUN, not part of any gate: the native gate reads only the OUTPUT (transform_golden.kotoba, transform-golden.tsv) and pins its
sha256. Everything here is Python `fractions.Fraction` / integers: no float, no `math.sin`. The reference semantics are the definitions in
layout.cljk (matrix*, transform-ops px / py / bbox, the `about` conjugation, round-4 replaced by round-half-up to the Q-scale), applied to
the inputs read as exact rationals (Q17 coefficients, Q6 lengths); trig values come from the independent series of gen_trig_golden.py.

Inputs are regenerated on the native side from a documented generator (so the table holds expected outputs only):
  rr(i, k) = x3 where x0 = 7919 i + 104729 k + 1 and x_{j+1} = x_j * 48271 mod 2147483647  (Park-Miller, three steps)
  val(i, k, e) = rr(i, k) mod (2^(e+1) + 1) - 2^e        uval(i, k, e) = rr(i, k) mod (2^e + 1)
Tables: P1 (N1 cases x 15 functions, expected word per function), FLOW (81 x 81 + 2 x 81), E2E (ideal real-valued point images, Q10).

usage: gen_transform_golden.py OUTDIR
"""
import hashlib, json, math, platform, sys, datetime
from fractions import Fraction as F
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_trig_golden as gt

INV = -4611686018427387904
N1 = 1500
N2 = 1000


def rr(i, k):
    x = 7919 * i + 104729 * k + 1
    for _ in range(3):
        x = x * 48271 % 2147483647
    return x


def val(i, k, e):
    return rr(i, k) % (2 ** (e + 1) + 1) - 2 ** e


def uval(i, k, e):
    return rr(i, k) % (2 ** e + 1)


def rq(x):                      # round half up of an exact rational
    return math.floor(F(x) + F(1, 2))


def lin_ok(x): return -8388608 < x < 8388608
def tr_ok(x): return -4194304 <= x <= 4194304
def clamp(x): return max(-1073741825, min(1073741825, x))
def PACK(h, l): return (clamp(h) << 32) + clamp(l) + 1073741825
def HI(p): return p >> 32
def LO(p): return (p & 4294967295) - 1073741825
def mk_lin(a, b): return PACK(a, b) if lin_ok(a) and lin_ok(b) else INV
def mk_tr(e, f): return PACK(e, f) if tr_ok(e) and tr_ok(f) else INV
EL = [14, 16, 17, 18, 19, 20, 22, 23]
ET = [4, 8, 12, 16, 20, 22, 23]
EV = [20, 24, 26, 27, 30]
EN = [8, 16, 24, 32, 40, 44, 46, 47]


def case_args(i):
    el, et = EL[rr(i, 50) % 8], ET[rr(i, 51) % 7]
    a = dict(el=el, et=et)
    a['a1'], a['b1'], a['c1'], a['d1'] = (val(i, k, el) for k in (1, 2, 3, 4))
    a['e1'], a['f1'] = val(i, 5, et), val(i, 6, et)
    a['a2'], a['b2'], a['c2'], a['d2'] = (val(i, k, el) for k in (7, 8, 9, 10))
    a['e2'], a['f2'] = val(i, 11, et), val(i, 12, et)
    a['x'], a['y'] = val(i, 13, et), val(i, 14, et)
    a['w'], a['h'] = uval(i, 15, et), uval(i, 16, et)
    a['cx'], a['cy'] = val(i, 17, et), val(i, 18, et)
    a['v6'] = val(i, 19, EV[rr(i, 52) % 5])
    en = EN[rr(i, 53) % 8]
    a['n'] = (rr(i, 20) * rr(i, 27)) % (2 ** en + 1)
    a['fs'], a['scale'] = val(i, 21, et), val(i, 22, el)
    a['kind'], a['ov'], a['basis'] = rr(i, 23) % 6, val(i, 24, 17), val(i, 25, et)
    return a


def expected(a):
    out = []
    # 0 coef-of-number
    v6 = a['v6']
    out.append((lambda r: r if lin_ok(r) else INV)(rq(F(v6 * 131072, 10 ** 6))) if -1073741824 <= v6 <= 1073741824 else INV)
    ok1 = all(lin_ok(a[k]) for k in ('a1', 'b1', 'c1', 'd1'))
    ok2 = all(lin_ok(a[k]) for k in ('a2', 'b2', 'c2', 'd2'))
    tr1, tr2 = tr_ok(a['e1']) and tr_ok(a['f1']), tr_ok(a['e2']) and tr_ok(a['f2'])
    a1, b1, c1, d1, a2, b2, c2, d2 = (a[k] for k in ('a1', 'b1', 'c1', 'd1', 'a2', 'b2', 'c2', 'd2'))
    e1, f1, e2, f2 = a['e1'], a['f1'], a['e2'], a['f2']
    # 1 mul-ab, 2 mul-cd (inputs ab1 cd1 ab2 / cd2)
    out.append(mk_lin(rq(F(a1 * a2 + c1 * b2, 131072)), rq(F(b1 * a2 + d1 * b2, 131072))) if ok1 else INV)
    out.append(mk_lin(rq(F(a1 * c2 + c1 * d2, 131072)), rq(F(b1 * c2 + d1 * d2, 131072))) if ok1 else INV)
    # 3 mul-ef
    out.append(mk_tr(rq(F(a1 * e2 + c1 * f2, 131072) + e1), rq(F(b1 * e2 + d1 * f2, 131072) + f1)) if (ok1 and tr1 and tr2) else INV)
    # 4 about-ef (m1 linear, ef1 = (e1, f1), c = (cx, cy))
    cx, cy = a['cx'], a['cy']
    trc = tr_ok(cx) and tr_ok(cy)
    out.append(mk_tr(rq(e1 + cx - F(a1 * cx + c1 * cy, 131072)), rq(f1 + cy - F(b1 * cx + d1 * cy, 131072))) if (ok1 and tr1 and trc) else INV)
    x, y, w, h = a['x'], a['y'], a['w'], a['h']

    def mapx(xx, yy):
        if not (ok1 and tr1 and tr_ok(xx) and tr_ok(yy)):
            return INV
        r = rq(F(a1 * xx + c1 * yy, 131072) + e1)
        return r if tr_ok(r) else INV

    def mapy(xx, yy):
        if not (ok1 and tr1 and tr_ok(xx) and tr_ok(yy)):
            return INV
        r = rq(F(b1 * xx + d1 * yy, 131072) + f1)
        return r if tr_ok(r) else INV
    out.append(mapx(x, y))
    out.append(mapy(x, y))
    for fn, pick in ((mapx, min), (mapx, max), (mapy, min), (mapy, max)):
        cs = [fn(x, y), fn(x + w, y), fn(x, y + h), fn(x + w, y + h)]
        out.append(INV if (INV in cs or w < 0 or h < 0) else pick(cs))
    # 11 uniform-scale of (ab1, cd1)
    if ok1:
        n = abs(a1 * d1 - b1 * c1)
        out.append(INV if n >= 2 ** 46 else (math.isqrt(4 * n) + 1) // 2)
    else:
        out.append(INV)
    # 12 font-scale
    fs, sc = a['fs'], a['scale']
    out.append((lambda r: r if tr_ok(r) else INV)(rq(F(fs * sc, 131072))) if (tr_ok(fs) and lin_ok(sc)) else INV)
    # 13 isqrt
    n = a['n']
    out.append(math.isqrt(n) if n < 2 ** 46 else INV)
    # 14 origin-coord
    k, ov, bs = a['kind'], a['ov'], a['basis']
    if not tr_ok(bs):
        out.append(INV)
    elif k == 0: out.append(rq(F(bs, 2)))
    elif k == 1: out.append(0)
    elif k == 2: out.append(bs)
    elif k == 3: out.append(ov if tr_ok(ov) else INV)
    elif k == 4: out.append(rq(F(ov * bs, 10000)) if -65535 <= ov <= 65535 else INV)
    else: out.append(INV)
    return out


def tree(vals, lo, hi, var='i'):
    if hi - lo == 1:
        return 'X' if vals[lo] == INV else str(vals[lo])
    m = (lo + hi) // 2
    return '(if (< %s %d) %s %s)' % (var, m, tree(vals, lo, m, var), tree(vals, m, hi, var))


# ---------------- flow rotation ----------------
def dec(code):
    d = code % 3; q = code // 3; c = q % 3; q //= 3; b = q % 3; a = q // 3
    return (a - 1, b - 1, c - 1, d - 1)


def enc(a, b, c, d): return (a + 1) * 27 + (b + 1) * 9 + (c + 1) * 3 + (d + 1)


def flow_expected(child, parent):
    A, P = dec(child), dec(parent)
    det = lambda m: m[0] * m[3] - m[1] * m[2]
    if abs(det(A)) != 1 or abs(det(P)) != 1:
        return INV
    pa, pb, pc, pd = (F(x) for x in P)
    dd = pa * pd - pb * pc
    inv = (pd / dd, -pb / dd, -pc / dd, pa / dd)          # exact 2x2 inverse
    a1, b1, c1, d1 = inv; a2, b2, c2, d2 = (F(x) for x in A)
    m = (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2)
    if any(abs(x) > 1 for x in m):
        return INV
    m = tuple(int(x) for x in m)
    return -1 if m == (1, 0, 0, 1) else enc(*m)


# ---------------- end to end (ideal real numbers) ----------------
def e2e_args(i):
    u = 1 + rr(i, 60) % 4
    v = rr(i, 61) % (2 * gt.LIMIT[u] + 1) - gt.LIMIT[u]
    sx6 = rr(i, 62) % 4000001 - 2000000
    sy6 = rr(i, 63) % 4000001 - 2000000
    ax6 = rr(i, 64) % 170000001 - 85000000
    ay6 = rr(i, 65) % 170000001 - 85000000
    ex = [8, 12, 16, 19, 22][rr(i, 66) % 5]
    return dict(u=u, v=v, sx6=sx6, sy6=sy6, ax6=ax6, ay6=ay6, ex=ex, x=val(i, 67, ex), y=val(i, 68, ex), cx=val(i, 69, ex), cy=val(i, 70, ex))


def mm(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1; a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2, a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def ideal(a, pl):
    s, c = gt.hp_sincos(a['u'], a['v'])
    s, c = F(s, gt.S), F(c, gt.S)
    R = (c, s, -s, c, F(0), F(0))
    if pl == 0:
        S = (F(a['sx6'], 10 ** 6), F(0), F(0), F(a['sy6'], 10 ** 6), F(0), F(0))
        M = mm(R, S)
    else:
        sx, cx_ = gt.hp_sincos(1, a['ax6'])
        sy, cy_ = gt.hp_sincos(1, a['ay6'])
        tx, ty = F(sx, gt.S) / F(cx_, gt.S), F(sy, gt.S) / F(cy_, gt.S)
        K = (F(1), ty, tx, F(1), F(0), F(0))                # skew(ax, ay) = [1 tan(ay) tan(ax) 1 0 0]
        M = mm(K, R)
    cx, cy = a['cx'], a['cy']
    Tp = (F(1), F(0), F(0), F(1), F(cx), F(cy)); Tm = (F(1), F(0), F(0), F(1), F(-cx), F(-cy))
    A = mm(mm(Tp, M), Tm)
    x, y = a['x'], a['y']
    return (A[0] * x + A[2] * y + A[4], A[1] * x + A[3] * y + A[5])


def main(outdir):
    out = Path(outdir)
    cols = ['coef', 'mulab', 'mulcd', 'mulef', 'about', 'mapx', 'mapy', 'xsmin', 'xsmax', 'ysmin', 'ysmax', 'uscale', 'fscale', 'isqrt', 'origin']
    P1 = [expected(case_args(i)) for i in range(N1)]
    tsv = ['i\t' + '\t'.join(cols)] + ['\t'.join([str(i)] + ['INV' if v == INV else str(v) for v in row]) for i, row in enumerate(P1)]
    (out / 'transform-golden.tsv').write_text('\n'.join(tsv) + '\n')
    flow = [flow_expected(c, p) for c in range(81) for p in range(81)]
    flowab = [INV if abs(dec(c)[0] * dec(c)[3] - dec(c)[1] * dec(c)[2]) != 1 else PACK(131072 * dec(c)[0], 131072 * dec(c)[1]) for c in range(81)]
    flowcd = [INV if abs(dec(c)[0] * dec(c)[3] - dec(c)[1] * dec(c)[2]) != 1 else PACK(131072 * dec(c)[2], 131072 * dec(c)[3]) for c in range(81)]
    # end to end: ideal point image in Q10 (Q6 raw * 16), two pipelines (rotate*scale, skew*rotate); None -> 0 word = skip (outside range)
    e2e = {0: [], 1: []}
    skipped = {0: 0, 1: 0}
    for pl in (0, 1):
        for i in range(N2):
            a = e2e_args(i)
            if pl == 1 and (abs(a['ax6']) > 85000000 or abs(a['ay6']) > 85000000):
                pass
            X, Y = ideal(a, pl)
            lim = 2 ** 22 - 64
            if abs(X) > lim or abs(Y) > lim:
                e2e[pl].append((0, 0)); skipped[pl] += 1
            else:
                e2e[pl].append((rq(X * 16) + 2 ** 27, rq(Y * 16) + 2 ** 27))      # biased so 0 means skipped
    ctsv = ['section\tindex\tvalue']
    ctsv += ['flow\t%d\t%s' % (k, 'INV' if v == INV else v) for k, v in enumerate(flow)]
    ctsv += ['flow-ab\t%d\t%s' % (k, 'INV' if v == INV else v) for k, v in enumerate(flowab)]
    ctsv += ['flow-cd\t%d\t%s' % (k, 'INV' if v == INV else v) for k, v in enumerate(flowcd)]
    for pl in (0, 1):
        for ax, idx in (('x', 0), ('y', 1)):
            ctsv += ['e2e-%s-%d\t%d\t%d' % (ax, pl, k, r[idx]) for k, r in enumerate(e2e[pl])]
    (out / 'transform-golden-c.tsv').write_text('\n'.join(ctsv) + '\n')
    hdr = [';; GENERATED by scripts/gen_transform_golden.py (one-time exact-rational reference run). DATA, not code. Do not edit.',
           ';; The golden data is split over three modules because the host compiler refuses a single module of about 1.3 MB (EHOST packaging).']
    def p1(lo, hi, name):
        m = ['(ns cssom.transform-golden-%s (:export [g1%s]))' % (name, name)] + hdr + ['(def X -4611686018427387904)',
             ';; g1%s i f: expected word of function f (%d..%d of: 0 coef-of-number, 1 mul-ab, 2 mul-cd, 3 mul-ef, 4 about-ef, 5 map-x, 6 map-y,' % (name, lo, hi - 1),
             ';; 7 xs-min, 8 xs-max, 9 ys-min, 10 ys-max, 11 uniform-scale, 12 font-scale, 13 isqrt, 14 origin-coord) for case i; -2^62 = refused.']
        for f in range(lo, hi):
            m.append('(defn g1-%d [i :i64] :i64 %s)' % (f, tree([row[f] for row in P1], 0, N1)))
        m.append('(defn g1%s [i :i64 f :i64] :i64\n  (cond ' % name + ' '.join('(= f %d) (g1-%d i)' % (f, f) for f in range(lo, hi - 1)) + ' :else (g1-%d i)))' % (hi - 1))
        return '\n'.join(m) + '\n'
    (out / 'transform_golden_a.kotoba').write_text(p1(0, 8, 'a'))
    (out / 'transform_golden_b.kotoba').write_text(p1(8, 15, 'b'))
    m = ['(ns cssom.transform-golden-c (:export [n1 n2 g-flow g-flow-ab g-flow-cd g-e2e-x g-e2e-y]))'] + hdr + [
         ';; g-flow k: flow-rotation of child k / 81 and parent k mod 81; g-flow-ab / cd code. g-e2e-x / y pl i: ideal real-valued image of the',
         ';; point, Q6 * 16 + 2^27, 0 = skipped.',
         '(def X -4611686018427387904)', '(defn n1 [] :i64 %d)' % N1, '(defn n2 [] :i64 %d)' % N2]
    m.append('(defn g-flow [i :i64] :i64 %s)' % tree(flow, 0, len(flow)))
    m.append('(defn g-flow-ab [i :i64] :i64 %s)' % tree(flowab, 0, 81))
    m.append('(defn g-flow-cd [i :i64] :i64 %s)' % tree(flowcd, 0, 81))
    for ax, idx in (('x', 0), ('y', 1)):
        for pl in (0, 1):
            m.append('(defn g-e2e-%s-%d [i :i64] :i64 %s)' % (ax, pl, tree([r[idx] for r in e2e[pl]], 0, N2)))
        m.append('(defn g-e2e-%s [pl :i64 i :i64] :i64 (if (= pl 0) (g-e2e-%s-0 i) (g-e2e-%s-1 i)))' % (ax, ax, ax))
    (out / 'transform_golden_c.kotoba').write_text('\n'.join(m) + '\n')
    meta = {'date': str(datetime.date.today()), 'python': platform.python_version(), 'platform': platform.platform(),
            'command': 'python3 scripts/gen_transform_golden.py <evidence dir>', 'n1': N1, 'n2': N2,
            'refusedWordsPerFunction': {c: sum(1 for r in P1 if r[j] == INV) for j, c in enumerate(cols)},
            'flowRefused': sum(1 for v in flow if v == INV), 'flowIdentity': sum(1 for v in flow if v == -1),
            'e2eSkipped': skipped,
            'sha256': {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in ('transform-golden.tsv', 'transform-golden-c.tsv', 'transform_golden_a.kotoba', 'transform_golden_b.kotoba', 'transform_golden_c.kotoba')}}
    (out / 'transform-golden-meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(meta['refusedWordsPerFunction']), meta['flowRefused'], meta['flowIdentity'], skipped)


if __name__ == '__main__':
    main(sys.argv[1])
