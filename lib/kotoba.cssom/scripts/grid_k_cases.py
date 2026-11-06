#!/usr/bin/env python3
"""Case table, exact and f64 models and wire encoding for the grid / table sizing slice (JUN-932 part 2, JUN-920, ADR-0287).

This file is a pure-Python generator and model; nothing in it runs in a gate path of the product (no JVM, nbb or babashka).

Three independent computations of the same semantics (layout.cljk track-sizes, distribute-fr, distribute-equally-with-caps,
grid-track-intrinsics, span-width, table-column-widths, table-fixed-column-widths, distribute-excess and the caption widening of
layout-table), each transcribed from the source and not from the region modules:

  * `model(words, "exact")`  integer arithmetic: every fraction is floor(a / b) of integers (the fr weights are D4 integers). The kernel
                             modules (grid_k, table_k) must equal it on every case.
  * `model(words, "f64")`    the same algorithm with the source's own double arithmetic (IEEE doubles, Python float = Java double):
                             weights are raw / 10000.0, `(quot (* r w) total)` is trunc(fl(fl(r * w) / total)), the table's proportional
                             steps are trunc(a * fl(b / total)). The native f64 references (grid_ref.kotoba, table_ref.kotoba) must equal it.
  * hand-derived expectations written out from the CSS text and the docstrings of layout.cljk before any run.

Wherever the two models differ, the difference is logged as a TIE: the step's exact value is an integer (the exact quotient is whole)
and the double result falls one unit below it. Any other difference is a defect of the transcription and is raised.

Wire format of a case (what the kernel entry copies into page 0 of the owned window): u16 big endian word count, then that many u32 big
endian words (stored little endian in the window). Layout of the words: see the headers of grid_k.kotoba and table_k.kotoba.
"""
import random
import struct
from fractions import Fraction

LIM = 1 << 24
NONE = 0xFFFFFFFF
D4 = 10000


def px(v):
    return v >> 6


def q(x):
    """Q6 raw of a whole-pixel length."""
    return x * 64


def hash_out(values):
    h = 5381
    for v in values:
        h = (h * 257 + (v << 6) + 1) & 0xFFFFFFFF
    return h


# ------------------------------------------------------------------------------------------------------------------ models
class Ties:
    def __init__(self):
        self.log = []

    def frac(self, mode, num, den, f64_fn, where):
        """floor(num/den) exactly, or the source's double expression; logs the disagreement and checks it is an exact tie."""
        exact = num // den
        if mode == "exact":
            return exact
        got = f64_fn()
        if got != exact:
            if Fraction(num, den).denominator != 1 or got != exact - 1:
                raise ValueError(("double step differs from the exact floor away from an exact tie", where, num, den, exact, got))
            self.log.append((where, num, den, exact, got))
        return got


def dewc(sizes, idxs, cap_of, free):
    """layout.cljk distribute-equally-with-caps, literally."""
    if free <= 0 or not idxs:
        return sizes
    sizes, live, free = list(sizes), list(idxs), int(free)
    while True:
        if not live or free <= 0:
            return sizes
        share = free // len(live)
        if share <= 0:
            for i in live:
                if free > 0:
                    cap = cap_of(i)
                    want = sizes[i] + 1
                    if cap is None or want <= cap:
                        sizes[i] = want
                        free -= 1
            return sizes
        unspent, still = 0, []
        for i in live:
            cap = cap_of(i)
            cur = sizes[i]
            want = cur + share
            if cap is not None and want >= cap:
                sizes[i] = max(cur, cap)
                unspent += want - max(cur, cap)
            else:
                sizes[i] = want
                still.append(i)
        spent = free - unspent - (free % len(live))
        free, live = free - spent, still


def grid_check(w):
    """The status the contract gives (None when the case is accepted); the order of the checks is part of the contract."""
    n = w[0] if len(w) > 0 else 0
    if len(w) < 8 or len(w) > 1024:
        return -1
    n, gap, t, stretch, m, derive, r6, r7 = w[:8]
    if not 1 <= n <= 16:
        return -2
    if m > 32:
        return -3
    if len(w) != 8 + 6 * n + 4 * m:
        return -1
    if not (stretch < 2 and derive < 2 and r6 == 0 and r7 == 0):
        return -1
    if gap >= LIM:
        return -5
    if not (t < LIM or t == NONE):
        return -5
    for i in range(n):
        ty, a, b, mn, mx, _ = w[8 + 6 * i:14 + 6 * i]
        if ty > 4:
            return -4
        if not (a < LIM and b < LIM and mn < LIM and mx < LIM):
            return -5
    for j in range(m):
        cs, ce, mn, mx = w[8 + 6 * n + 4 * j:12 + 6 * n + 4 * j]
        if not (cs < ce <= n):
            return -6
        if not (mn < LIM and mx < LIM):
            return -5
    return None


def grid_model(w, mode, ties=None):
    """Returns (outputs, sizes) -- outputs = n track sizes + m span widths in whole px -- or a negative status."""
    st = grid_check(w)
    if st is not None:
        return st
    ties = ties if ties is not None else Ties()
    n, gap_raw, t, stretch, m, derive = w[0], w[1], w[2], w[3], w[4], w[5]
    gap = px(gap_raw)
    T = None if t == NONE else px(t)
    tracks = [w[8 + 6 * i:14 + 6 * i] for i in range(n)]
    items = [w[8 + 6 * n + 4 * j:12 + 6 * n + 4 * j] for j in range(m)]
    # intrinsics: grid-track-intrinsics (single-track items) or the track words; intrinsic-max is at least the min
    if derive:
        imin, imax = [0] * n, [0] * n
        for cs, ce, mn, mx in items:
            if ce - cs == 1:
                imin[cs] = max(imin[cs], px(mn))
                imax[cs] = max(imax[cs], px(mx))
    else:
        imin = [px(tr[3]) for tr in tracks]
        imax = [px(tr[4]) for tr in tracks]
    imax = [max(a, b) for a, b in zip(imin, imax)]

    def fixed_contribution(tr):
        ty, a, b = tr[0], px(tr[1]), px(tr[2])
        return {0: a, 1: 0, 2: max(a, b), 3: a, 4: 0}[ty]

    def weight(tr):  # D4 raw or None
        return {1: tr[1], 3: tr[2]}.get(tr[0])

    gap_total = gap * max(0, n - 1)
    auto_idxs = [i for i in range(n) if tracks[i][0] == 4]
    base = [imin[i] if tracks[i][0] == 4 else fixed_contribution(tracks[i]) for i in range(n)]
    has_fr = any(weight(tr) is not None for tr in tracks)
    if T is not None and auto_idxs:
        grown = dewc(base, auto_idxs, lambda i: imax[i], T - sum(base) - gap_total)
        if has_fr or not stretch:
            auto_resolved = grown
        else:
            auto_resolved = dewc(grown, auto_idxs, lambda i: None, T - sum(grown) - gap_total)
    else:
        auto_resolved = base
    fixed_total = sum(auto_resolved[i] if tracks[i][0] == 4 else fixed_contribution(tracks[i]) for i in range(n))
    remaining = max(0, T - fixed_total - gap_total) if T is not None else None
    weights = [weight(tr) for tr in tracks if weight(tr) is not None]
    # distribute-fr
    if remaining is None:
        fr_sizes = []
    elif mode == "exact":
        total = sum(weights)
        if remaining <= 0 or not total > 0:
            fr_sizes = [0] * len(weights)
        else:
            fr_sizes = [remaining * x // total for x in weights]
            left = remaining - sum(fr_sizes)
            if left > 0 and fr_sizes:
                fr_sizes[-1] += left
    else:
        wf = [x / 10000.0 for x in weights]
        total = 0.0
        for x in wf:
            total = total + x
        if remaining <= 0 or not total > 0:
            fr_sizes = [0] * len(weights)
        else:
            fr_sizes = []
            etotal = sum(weights)
            for x, xf in zip(weights, wf):
                got = int(float(remaining) * xf / total)
                exact = remaining * x // etotal
                if got != exact:
                    if Fraction(remaining * x, etotal).denominator != 1 or got != exact - 1:
                        raise ValueError(("fr step differs away from an exact tie", remaining, x, etotal, exact, got))
                    ties.log.append(("fr", remaining * x, etotal, exact, got))
                fr_sizes.append(got)
            left = remaining - sum(fr_sizes)
            if left > 0 and fr_sizes:
                fr_sizes[-1] += left
    out, k = [], 0
    for i in range(n):
        tr = tracks[i]
        if tr[0] == 4:
            out.append(auto_resolved[i])
        elif weight(tr) is not None:
            out.append((px(tr[1]) if tr[0] == 3 else 0) + (fr_sizes[k] if k < len(fr_sizes) else 0))
            k += 1
        else:
            out.append(fixed_contribution(tr))
    spans = [sum(out[cs:ce]) + gap * max(0, ce - cs - 1) for cs, ce, _, _ in items]
    return out + spans, out


def table_check(w):
    if len(w) < 8 or len(w) > 1024:
        return -1
    mode, cw, sp, kk, c, cap, tgt, r7 = w[:8]
    if kk > 16:
        return -2
    if c > 64:
        return -3
    if len(w) != 8 + 2 * kk + 5 * c:
        return -1
    if not (mode < 2 and r7 == 0):
        return -1
    if not (cw < LIM and sp < LIM and cap < LIM and (tgt < LIM or tgt == NONE)):
        return -5
    for k in range(kk):
        a, b = w[8 + 2 * k], w[9 + 2 * k]
        if not ((a < LIM or a == NONE) and (b < LIM or b == NONE)):
            return -5
    for j in range(c):
        col, span, nat, dec, r0 = w[8 + 2 * kk + 5 * j:13 + 2 * kk + 5 * j]
        if span == 0:
            return -6
        if col + span > 16:
            return -7
        if not (nat < LIM and (dec < LIM or dec == NONE) and r0 < 2):
            return -5
    return None


def table_model(w, mode, ties=None):
    st = table_check(w)
    if st is not None:
        return st
    ties = ties if ties is not None else Ties()
    tmode, cwr, spr, kk, c, capr, tgt, _ = w[:8]
    content_w, spacing, caption_w = px(cwr), px(spr), px(capr)
    colw = [None if w[8 + 2 * k] == NONE else px(w[8 + 2 * k]) for k in range(kk)]
    decl = [None if w[9 + 2 * k] == NONE else px(w[9 + 2 * k]) for k in range(kk)]
    cells = []
    for j in range(c):
        col, span, nat, dec, r0 = w[8 + 2 * kk + 5 * j:13 + 2 * kk + 5 * j]
        cells.append(dict(col=col, span=span, nat=px(nat), dec=None if dec == NONE else px(dec), row0=r0))

    def nth(lst, i):
        return lst[i] if i < len(lst) else None

    def frac_dx(num, den, f64_fn, where):
        return ties.frac(mode, num, den, f64_fn, where)

    def distribute_excess(widths, target, locked):
        total = sum(widths)
        free = [i for i in range(len(widths)) if i not in locked]
        free_total = sum(widths[i] for i in free)
        if not widths or not total > 0 or target <= total:
            return widths
        if not free or not free_total > 0:
            grown = [frac_dx(target * x, total, lambda x=x: int(target * (x / float(total))), "excess-all") for x in widths]
            grown[-1] += target - sum(grown)
            return grown
        free_target = target - (total - free_total)
        grown = list(widths)
        for i in free:
            grown[i] = frac_dx(free_target * widths[i], free_total,
                               lambda i=i: int(free_target * (widths[i] / float(free_total))), "excess-free")
        grown[free[-1]] += target - sum(grown)
        return grown

    if tmode == 0:
        n = max([cl["col"] + cl["span"] for cl in cells], default=0)
        base = []
        for col in range(n):
            cwv, dwv = nth(colw, col), nth(decl, col)
            if cwv is not None and dwv is not None:
                base.append(max(cwv, dwv))
            elif cwv is not None or dwv is not None:
                base.append(cwv if cwv is not None else dwv)
            else:
                base.append(max([1] + [cl["nat"] for cl in cells if cl["span"] == 1 and cl["col"] == col]))
        widths = list(base)
        for cl in cells:
            if cl["span"] != 1:
                cols = range(cl["col"], cl["col"] + cl["span"])
                have = sum(widths[i] for i in cols) + spacing * (cl["span"] - 1)
                short = cl["nat"] - have
                if short > 0:
                    add = -(-short // cl["span"])
                    for i in cols:
                        widths[i] += add
        total = sum(widths)
        if total > 0 and total > content_w:
            widths = [frac_dx(x * content_w, total, lambda x=x: int(x * (content_w / total)), "scale") for x in widths]
    else:
        n = max([kk] + [cl["col"] + cl["span"] for cl in cells if cl["row0"] == 1])
        avail = max(0, content_w - spacing * (n + 1))
        declared = []
        for col in range(n):
            v = nth(colw, col)
            if v is None:
                v = next((cl["dec"] for cl in cells if cl["row0"] == 1 and cl["span"] == 1 and cl["col"] == col and cl["dec"] is not None), None)
            declared.append(v)
        fixed = sum(v for v in declared if v is not None)
        autos = sum(1 for v in declared if v is None)
        each = max(0, int((avail - fixed) / autos)) if autos else 0
        widths = [v if v is not None else each for v in declared]
        if not autos:
            widths = distribute_excess(widths, avail, set())
    # caption widening, layout-table
    short = caption_w - (sum(widths) + spacing * (len(widths) + 1))
    if short > 0 and widths:
        add = -(-short // len(widths))
        widths = [x + add for x in widths]
    if tmode == 0 and tgt != NONE:
        locked = {i for i in range(len(widths)) if nth(colw, i) is not None or nth(decl, i) is not None}
        widths = distribute_excess(widths, px(tgt), locked)
    return widths, widths


def model(w, kind, mode, ties=None):
    return (grid_model if kind == "grid" else table_model)(w, mode, ties)


# ------------------------------------------------------------------------------------------------------------------ encoders
def grid_words(tracks, gap=0, total=None, stretch=1, items=(), derive=0, n=None):
    """tracks: ("fixed", px) ("fr", d4) ("minmax", minpx, maxpx) ("minmaxfr", minpx, d4) ("auto", min_raw, max_raw)
    (a track may also be a raw 6-tuple of words); items: (cs, ce, min_raw, max_raw)."""
    ws = [len(tracks) if n is None else n, q(gap), NONE if total is None else q(total), stretch, len(items), derive, 0, 0]
    for tr in tracks:
        if len(tr) == 6 and isinstance(tr[0], int):
            ws += list(tr)
            continue
        k = tr[0]
        if k == "fixed":
            ws += [0, q(tr[1]), 0, 0, 0, 0]
        elif k == "fr":
            ws += [1, tr[1], 0, 0, 0, 0]
        elif k == "minmax":
            ws += [2, q(tr[1]), q(tr[2]), 0, 0, 0]
        elif k == "minmaxfr":
            ws += [3, q(tr[1]), tr[2], 0, 0, 0]
        else:
            ws += [4, 0, 0, tr[1], tr[2], 0]
    for it in items:
        ws += list(it)
    return ws


def table_words(cells, cols=(), content=300, spacing=2, fixed=0, caption=0, target=None, cap_cols=None):
    """cells: (col, colspan, natural_px, declared_px or None, row0); cols: (colwidth_px or None, declared_px or None) per column record."""
    N = lambda v: NONE if v is None else q(v)
    ws = [fixed, q(content), q(spacing), len(cols), len(cells), q(caption), NONE if target is None else q(target), 0]
    for a, b in cols:
        ws += [N(a), N(b)]
    for col, span, nat, dec, r0 in cells:
        ws += [col, span, q(nat) if nat >= 0 else nat, N(dec), r0]
    return ws


def encode(words):
    return struct.pack(">H", len(words)) + b"".join(struct.pack(">I", x) for x in words)


# ------------------------------------------------------------------------------------------------------------------ cases
def hand_cases():
    """Expected track / column sizes (whole px) written out by hand from the CSS text and the docstrings of layout.cljk."""
    c = []

    def g(name, why, words, sizes, spans=()):
        c.append(dict(kind="grid", name=name, why=why, words=words, status=0, expect=list(sizes) + list(spans)))

    def t(name, why, words, widths):
        c.append(dict(kind="table", name=name, why=why, words=words, status=0, expect=list(widths)))

    F1 = D4
    g("grid-hand-100-1fr-2fr", "parse-track-list docstring: `100px 1fr 2fr` in 400px: 100 + 300 split 1:2",
      grid_words([("fixed", 100), ("fr", F1), ("fr", 2 * F1)], total=400), [100, 100, 200])
    g("grid-hand-thirds-leftover", "distribute-fr docstring: the rounding leftover goes to the last fr track: 100/3 = 33 33 + 34",
      grid_words([("fr", F1)] * 3, total=100), [33, 33, 34])
    g("grid-hand-gap", "gap is taken off the fr space: (300 - 10) / 2",
      grid_words([("fr", F1)] * 2, gap=10, total=300), [145, 145])
    g("grid-hand-gap-thirds", "two gaps of 5 leave 90 for three 1fr tracks",
      grid_words([("fr", F1)] * 3, gap=5, total=100), [30, 30, 30])
    g("grid-hand-minmax-fr", "repeat(3, minmax(80px, 1fr)) in 300px: 3 x 80 reserved, 60 shared, 100 each",
      grid_words([("minmaxfr", 80, F1)] * 3, total=300), [100, 100, 100])
    g("grid-hand-minmax-overflow", "the same in 200px: reservations exceed the width, no fr space, every track keeps its min",
      grid_words([("minmaxfr", 80, F1)] * 3, total=200), [80, 80, 80])
    g("grid-hand-minmax-fixed", "minmax(50px, 200px) resolves like a fixed track at max(min, max); 1fr takes the rest",
      grid_words([("minmax", 50, 200), ("fr", F1)], total=500), [200, 300])
    g("grid-hand-fractional-fr", "1.5fr 1fr in 100px: 100 * 1.5 / 2.5 = 60",
      grid_words([("fr", 15000), ("fr", F1)], total=100), [60, 40])
    g("grid-hand-zero-free", "100px 1fr in a 100px grid: no free space, the fr track is 0",
      grid_words([("fixed", 100), ("fr", F1)], total=100), [100, 0])
    g("grid-hand-negative-free", "100px 100px 1fr in 150px: free space is negative, the fr track is 0 and the fixed tracks overflow",
      grid_words([("fixed", 100), ("fixed", 100), ("fr", F1)], total=150), [100, 100, 0])
    g("grid-hand-indefinite", "no definite size: fr tracks are 0, an auto track is its min-content",
      grid_words([("fixed", 100), ("fr", F1), ("auto", q(30), q(50))], total=None), [100, 0, 30])
    g("grid-hand-auto-auto-stretch", "track-sizes docstring `auto auto` 300px holding xx / yyyy (17.16 / 35.47 px content): 17 + 124, 35 + 124",
      grid_words([("auto", 1098, 1098), ("auto", 2270, 2270)], total=300), [141, 159])
    g("grid-hand-auto-auto-start", "justify-content: start leaves auto tracks at max-content",
      grid_words([("auto", 1098, 1098), ("auto", 2270, 2270)], total=300, stretch=0), [17, 35])
    g("grid-hand-auto-1fr", "`auto 1fr`: the auto track stays at max-content (41.625 -> 41), 1fr takes 259",
      grid_words([("auto", 2664, 2664), ("fr", F1)], total=300), [41, 259])
    g("grid-hand-auto-100px", "`auto 100px`: the auto track stretches past max-content (no fr competes): 41 + 159",
      grid_words([("auto", 2664, 2664), ("fixed", 100)], total=300), [200, 100])
    g("grid-hand-equal-share-400", "docstring: short (41.625) / long (145.312) at 400px: each its max-content plus an equal share (214 / 2)",
      grid_words([("auto", 2664, 2664), ("auto", 9300, 9300)], total=400), [148, 252])
    g("grid-hand-equal-share-200", "the same at 200px: 186 + 7 each",
      grid_words([("auto", 2664, 2664), ("auto", 9300, 9300)], total=200), [48, 152])
    g("grid-hand-cap-reoffer", "min 10 / max 30 and min 10 / max 100 in 100px: the first freezes at 30, its unspent share goes to the other",
      grid_words([("auto", q(10), q(30)), ("auto", q(10), q(100))], total=100), [30, 70])
    g("grid-hand-one-px-each", "fewer px than tracks (2 for 3): handed out one at a time in order",
      grid_words([("auto", q(10), q(10))] * 3, total=32), [11, 11, 10])
    g("grid-hand-derive-intrinsics", "intrinsics from the single-track items only (the 0..2 item is ignored), spans over the result",
      grid_words([("auto", 0, 0), ("auto", 0, 0)], total=200, derive=1,
                 items=[(0, 1, q(10), q(30)), (0, 1, q(20), q(25)), (1, 2, q(5), q(50)), (0, 2, q(100), q(100))]),
      [90, 110], [90, 90, 110, 200])
    g("grid-hand-spans", "span-width: the spanned tracks plus the gaps between them, never one before the first or after the last",
      grid_words([("fixed", 100)] * 3, gap=10, total=400, items=[(0, 2, 0, 0), (1, 3, 0, 0), (0, 3, 0, 0), (2, 3, 0, 0)]),
      [100, 100, 100], [210, 210, 320, 100])

    t("table-hand-auto-two", "natural widths 9 and 163 (docstring of table-fixed / distribute-excess), wide table, no surplus",
      table_words([(0, 1, 9, None, 1), (1, 1, 163, None, 1)], content=400), [9, 163])
    t("table-hand-surplus", "300px table, cells 7 and 14: surplus 294 - 21 shared 1:2 (98 and 196) with the rounding shortfall to the last",
      table_words([(0, 1, 7, None, 1), (1, 1, 14, None, 1)], content=400, spacing=2, target=294), [98, 196])
    t("table-hand-col-locked", "distribute-excess docstring: a 200px <col> keeps it, the other column takes the surplus: 200 + 94",
      table_words([(0, 1, 9, None, 1), (1, 1, 9, None, 1)], cols=[(200, None)], content=400, spacing=2, target=294), [200, 94])
    t("table-hand-colspan", "a colspan 2 cell of 100 over 30 + 40 + 2px spacing: short 28, +14 each",
      table_words([(0, 1, 30, None, 1), (1, 1, 40, None, 1), (0, 2, 100, None, 0)], content=400, spacing=2), [44, 54])
    t("table-hand-colspan-odd", "a colspan 2 cell of 101 over 30 + 40 + 2px spacing: short 29, shared equally and rounded UP (15 each)",
      table_words([(0, 1, 30, None, 1), (1, 1, 40, None, 1), (0, 2, 101, None, 0)], content=400, spacing=2), [45, 55])
    t("table-hand-caption-odd", "caption 101px over two 9px columns and 2px spacing: short 77, 39 each (rounded up)",
      table_words([(0, 1, 9, None, 1), (1, 1, 9, None, 1)], content=400, spacing=2, caption=101), [48, 48])
    t("table-hand-scale-down", "columns 100 100 200 in a 200px content width scale down in proportion: 50 50 100",
      table_words([(0, 1, 100, None, 1), (1, 1, 100, None, 1), (2, 1, 200, None, 1)], content=200, spacing=2), [50, 50, 100])
    t("table-hand-fixed-declared", "table-fixed-column-widths docstring: first row 52 + two auto cells in 300px / spacing 2: 52 120 120",
      table_words([(0, 1, 9, 52, 1), (1, 1, 9, None, 1), (2, 1, 9, None, 1)], content=300, spacing=2, fixed=1), [52, 120, 120])
    t("table-hand-fixed-equal", "table-layout fixed, nothing declared, 300px: both columns 147 whatever the content",
      table_words([(0, 1, 9, None, 1), (1, 1, 200, None, 1)], content=300, spacing=2, fixed=1), [147, 147])
    t("table-hand-fixed-all-declared", "every column declared: stretched in proportion to the 294px of column space: 147 147",
      table_words([(0, 1, 9, 100, 1), (1, 1, 9, 100, 1)], content=300, spacing=2, fixed=1), [147, 147])
    t("table-hand-caption", "caption 100px over two 9px columns and 2px spacing: short 76, +38 each",
      table_words([(0, 1, 9, None, 1), (1, 1, 9, None, 1)], content=400, spacing=2, caption=100), [47, 47])
    return c


def grid_mix_cases():
    out = []
    kinds = {
        "F": ("fixed", 60), "f": ("fr", D4), "g": ("fr", 25000), "m": ("minmax", 40, 90), "n": ("minmaxfr", 30, D4),
        "a": ("auto", q(20), q(60)), "b": ("auto", 1000, 7000), "z": ("fr", 0),
    }
    mixes = ["Ff", "fa", "ab", "Fan", "mfa", "fgn", "aab", "Fgb", "zfa", "nna"]
    for mi in mixes:
        for total in (None, 0, 25, 200, 1000):
            for gap, stretch in ((0, 1), (7, 0)):
                if (total in (25, 1000)) and gap == 7 and stretch == 0 and len(out) % 2:
                    continue
                tracks = [kinds[ch] for ch in mi]
                out.append(dict(kind="grid", name="grid-mix-%s-T%s-g%d-s%d" % (mi, total, gap, stretch),
                                words=grid_words(tracks, gap=gap, total=total, stretch=stretch), status=0))
    return out


def grid_random_cases(seed=20261106, count=26):
    rnd = random.Random(seed)
    out = []
    for k in range(count):
        n = rnd.randint(1, 9)
        tracks = []
        for _ in range(n):
            ty = rnd.choice(["fixed", "fr", "fr", "minmax", "minmaxfr", "auto", "auto"])
            if ty == "fixed":
                tracks.append(("fixed", rnd.randint(0, 120)))
            elif ty == "fr":
                tracks.append(("fr", rnd.choice([D4, D4, 5000, 15000, 25000, 12345, 3333, 70000])))
            elif ty == "minmax":
                tracks.append(("minmax", rnd.randint(0, 80), rnd.randint(0, 150)))
            elif ty == "minmaxfr":
                tracks.append(("minmaxfr", rnd.randint(0, 80), rnd.choice([D4, 20000, 7777])))
            else:
                mn = rnd.randint(0, 6000)
                tracks.append(("auto", mn, mn + rnd.randint(0, 9000)))
        items = []
        derive = rnd.randint(0, 1)
        for _ in range(rnd.randint(0, 6)):
            cs = rnd.randint(0, n - 1)
            ce = rnd.randint(cs + 1, n)
            mn = rnd.randint(0, 4000)
            items.append((cs, ce, mn, mn + rnd.randint(0, 6000)))
        total = rnd.choice([None, 0, rnd.randint(1, 80), rnd.randint(80, 600), rnd.randint(600, 4000)])
        out.append(dict(kind="grid", name="grid-random-%02d" % k, status=0,
                        words=grid_words(tracks, gap=rnd.choice([0, 0, 3, 12]), total=total, stretch=rnd.randint(0, 1), items=items, derive=derive)))
    return out


def tie_cases():
    """Found by a seeded search (20000 draws) for cases where the double evaluation of the source differs from the exact floor: every
    one is an exact-integer quotient (the fr share 99 * 0.1 / 0.3 = 33 exactly; the table's 117 * 10 / 78 = 15 exactly) that a double
    evaluation puts one below. The kernel is exact; the f64 reference is the source's arithmetic; the gate reports each pair."""
    out = []
    for ws, total in (([1000, 2000], 99), ([3000, 1000, 500], 48), ([2000, 3000, 3000], 272), ([1000, 10000, 3000], 658), ([7000, 15000, 7000, 7000], 480)):
        out.append(dict(kind="grid", name="grid-tie-%s-T%d" % ("-".join(str(x) for x in ws), total), status=0,
                        words=grid_words([("fr", x) for x in ws], total=total), tie=True))
    for a, b, c, tg in ((10, 42, 26, 117), (5, 37, 26, 204), (60, 7, 50, 351), (57, 8, 20, 340)):
        out.append(dict(kind="table", name="table-tie-%d-%d-%d-T%d" % (a, b, c, tg), status=0, tie=True,
                        words=table_words([(0, 1, a, None, 1), (1, 1, b, None, 1), (2, 1, c, None, 1)], content=800, spacing=2, target=tg)))
    return out


def grid_bound_cases():
    out = []

    def add(name, words, status, **kw):
        out.append(dict(kind="grid", name=name, words=words, status=status, **kw))
    add("grid-bound-16-tracks", grid_words([("fr", D4)] * 16, total=1000, items=[(0, 16, 0, 0)]), 0)
    add("grid-bound-17-tracks", grid_words([("fr", D4)] * 17, total=1000), -2)
    add("grid-bound-0-tracks", grid_words([], total=1000), -2)
    add("grid-bound-32-items", grid_words([("auto", 0, 0)] * 4, total=100, derive=1, items=[(i % 4, i % 4 + 1, 640, 1280) for i in range(32)]), 0)
    add("grid-bound-33-items", grid_words([("auto", 0, 0)] * 4, total=100, derive=1, items=[(i % 4, i % 4 + 1, 640, 1280) for i in range(33)]), -3)
    add("grid-bound-length-max", grid_words([("auto", LIM - 1, LIM - 1), ("fixed", 100)], total=None), 0)
    add("grid-bound-length-past", grid_words([("auto", LIM, LIM), ("fixed", 100)], total=None), -5)
    add("grid-bound-weight-max", grid_words([("fr", LIM - 1), ("fr", D4)], total=1000), 0)
    add("grid-bound-weight-past", grid_words([("fr", LIM), ("fr", D4)], total=1000), -5)
    add("grid-bound-total-max", grid_words([("fr", D4), ("fr", 3 * D4)], total=262143), 0)
    add("grid-bound-total-past", [2, 0, LIM, 1, 0, 0, 0, 0] + [1, D4, 0, 0, 0, 0] * 2, -5)
    add("grid-refuse-type", grid_words([(5, 0, 0, 0, 0, 0)], total=100), -4)
    add("grid-refuse-item-range", grid_words([("fr", D4)] * 2, total=100, items=[(1, 3, 0, 0)]), -6)
    add("grid-refuse-item-empty", grid_words([("fr", D4)] * 2, total=100, items=[(1, 1, 0, 0)]), -6)
    add("grid-refuse-length", grid_words([("fr", D4)] * 2, total=100)[:-1], -1)
    add("grid-refuse-reserved", grid_words([("fr", D4)] * 2, total=100)[:6] + [1, 0] + grid_words([("fr", D4)] * 2, total=100)[8:], -1)
    add("grid-refuse-gap", grid_words([("fr", D4)] * 2, gap=0, total=100)[:1] + [LIM] + grid_words([("fr", D4)] * 2, total=100)[2:], -5)
    return out


def table_gen_cases(seed=7):
    rnd = random.Random(seed)
    out = []
    for k in range(32):
        ncol = rnd.randint(1, 6)
        cells = []
        for col in range(ncol):
            cells.append((col, 1, rnd.randint(1, 120), rnd.choice([None, None, rnd.randint(1, 100)]), 1))
        for _ in range(rnd.randint(0, 3)):
            col = rnd.randint(0, ncol - 1)
            span = rnd.randint(1, ncol - col)
            cells.append((col, span, rnd.randint(1, 300), None, rnd.randint(0, 1)))
        cols = [(rnd.choice([None, None, rnd.randint(1, 150)]), rnd.choice([None, None, rnd.randint(1, 150)])) for _ in range(rnd.randint(0, ncol))]
        fixed = rnd.randint(0, 1)
        out.append(dict(kind="table", name="table-gen-%02d%s" % (k, "f" if fixed else "a"), status=0,
                        words=table_words(cells, cols=cols, content=rnd.choice([30, 90, 200, 300, 640]), spacing=rnd.choice([0, 2, 5]),
                                          fixed=fixed, caption=rnd.choice([0, 0, 50, 400]),
                                          target=None if fixed else rnd.choice([None, 100, 290, 600, 1000]))))
    return out


def table_bound_cases():
    out = []

    def add(name, words, status):
        out.append(dict(kind="table", name=name, words=words, status=status))
    add("table-bound-16-columns", table_words([(i, 1, 10 + i, None, 1) for i in range(16)], content=1000, spacing=2, target=900), 0)
    add("table-bound-span-17", table_words([(0, 17, 10, None, 1)], content=1000), -7)
    add("table-bound-col-past", table_words([(16, 1, 10, None, 1)], content=1000), -7)
    add("table-bound-16-records", table_words([(0, 1, 10, None, 1)], cols=[(20, None)] * 16, content=100, fixed=1), 0)
    add("table-bound-17-records", table_words([(0, 1, 10, None, 1)], cols=[(20, None)] * 17, content=100, fixed=1), -2)
    add("table-bound-64-cells", table_words([(i % 16, 1, 5 + i, None, 1 if i < 16 else 0) for i in range(64)], content=500, target=400), 0)
    add("table-bound-65-cells", table_words([(i % 16, 1, 5 + i, None, 1) for i in range(65)], content=500), -3)
    add("table-bound-natural-max", table_words([(0, 1, 262143, None, 1)], content=300), 0)
    add("table-bound-natural-past", table_words([(0, 1, 262144, None, 1)], content=300), -5)
    add("table-refuse-colspan-0", table_words([(0, 0, 10, None, 1)], content=300), -6)
    add("table-refuse-length", table_words([(0, 1, 10, None, 1)], content=300)[:-1], -1)
    add("table-refuse-mode", [2] + table_words([(0, 1, 10, None, 1)], content=300)[1:], -1)
    add("table-empty", table_words([], content=300), 0)
    add("table-empty-fixed", table_words([], content=300, fixed=1), 0)
    return out


def all_cases():
    cases = hand_cases() + grid_mix_cases() + grid_random_cases() + tie_cases() + grid_bound_cases() + table_gen_cases() + table_bound_cases()
    assert len(cases) <= 240, len(cases)
    names = [c["name"] for c in cases]
    assert len(set(names)) == len(names)
    for c in cases:
        c.setdefault("expect", None)
        c.setdefault("why", None)
        c["blob"] = encode(c["words"])
    return cases


def expected(case):
    """What the exact model says for a case: (status, hash, sum, count) with status = 0 for an accepted case."""
    r = model(case["words"], case["kind"], "exact")
    if isinstance(r, int):
        return r, None, None, None
    outs, sizes = r
    return 0, hash_out(outs), sum(sizes) << 6, len(outs)


if __name__ == "__main__":
    cs = all_cases()
    kinds = {}
    for c in cs:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        r = expected(c)
        assert r[0] == c["status"], (c["name"], r, c["status"])
        if c["expect"] is not None:
            outs = model(c["words"], c["kind"], "exact")[0]
            assert outs == c["expect"], (c["name"], outs, c["expect"])
    print(len(cs), kinds, "all statuses and hand expectations agree with the exact model")
