"""Case grid, exact model and wire format of the flex_k slice (JUN-932 part 1, JUN-920 follow-up).

Nothing here runs the kernel. It holds (1) the EXACT model of the flex semantics, a literal transcription of the loop of
resolve-flexible-lengths (layout.cljk 9398-9514; cssom/flex.kotoba is the f64 transcription) over Python Fractions, so that
every proposal, freeze test and rounding is exact, and of place-main-axis / place-main-axis-auto-margins; (2) hand-derived
cases whose expected sizes were written from the CSS Flexbox 9.7 algorithm before any run (hand_cases); (3) the deterministic
case grid; (4) the wire format the QEMU profile `flex` reads (opt/aiueos/flex) and the 24-bit digest the guest leaves per case.

Units: lengths are Q6 raw (1/64 px), a flex factor is D4 raw (1/10000), `max` None means no maximum. The exact model returns
integers (one round-half-up of the exact value per item), because that is the rule of flex_q6 and flex_k.
"""
import random
import struct
from fractions import Fraction as Fr

INVALID = -(1 << 62)
NONE32 = 0xFFFFFFFF
MAXN = 16
# the domain of flex_q6 item-word / line-word, which flex_k keeps
BASE_MAX, MIN_MAX, MAX_MAX, FAC_MAX, NET_LO, NET_HI = 262143, 262143, 262142, 65535, -524288, 524287
INR = 1 << 30
MODE_START, MODE_BETWEEN, MODE_CENTER, MODE_END, MODE_AROUND, MODE_EVENLY = range(6)


def px(x):
    return int(round(x * 64))


def rhu(x):
    """round half up of a Fraction/int"""
    return (x + Fr(1, 2)).__floor__()


# ---------------------------------------------------------------- the exact model
def solve_exact(items, net):
    """items: [(base, min, max|None, factor)]. Returns (status, sizes) with sizes as exact Fractions before the final rounding.
    A literal transcription of the loop of cssom.flex/solve: sizes s, frozen f, grow decided once from the original sizes,
    weight = grow ? factor : factor * base, f_i initially (weight <= 0), used = sum(f ? s : base), remaining = net - used,
    proposal = f ? s : max(0, base + remaining * weight / total), clamp = min(max, max(min, p)); the pass answers when the
    clamp changes nothing, else s := clamp and f |= (clamp != p). (The source's guard n never fires, see the README.)"""
    n = len(items)
    if n > MAXN:
        return -1, None
    if n == 0:
        return -2, None
    for b, mn, mx, f in items:
        if not (0 <= b <= BASE_MAX and 0 <= mn <= MIN_MAX and (mx is None or 0 <= mx <= MAX_MAX) and 0 <= f <= FAC_MAX):
            return -3, None
    if not NET_LO <= net <= NET_HI:
        return -4, None
    base = [Fr(b) for b, _, _, _ in items]
    grow = net > sum(base)
    w = [Fr(f) if grow else Fr(f) * Fr(b) for b, _, _, f in items]
    s = list(base)
    fr = [not (x > 0) for x in w]
    guard = n
    while True:
        if all(fr) or guard < 0:
            return 0, s
        used = sum(s[i] if fr[i] else base[i] for i in range(n))
        rem = Fr(net) - used
        tw = sum(w[i] for i in range(n) if not fr[i])
        p = [s[i] if fr[i] else max(Fr(0), base[i] + rem * w[i] / tw) for i in range(n)]
        c = []
        for i in range(n):
            v1 = max(Fr(items[i][1]), p[i])
            c.append(v1 if items[i][2] is None else min(Fr(items[i][2]), v1))
        if all(c[i] == p[i] for i in range(n)):
            return 0, c
        s = c
        fr = [fr[i] or c[i] != p[i] for i in range(n)]
        guard -= 1


def sizes_exact(items, net):
    st, s = solve_exact(items, net)
    return st, ([rhu(x) for x in s] if st == 0 else None)


def _inr(x):
    return -INR <= x <= INR


def offsets_exact(mode, safe, container, gap, sizes, i):
    """place-main-axis: the position of item i, rounded half up once. Q6 range rules of flex_q6 offset."""
    n = len(sizes)
    total = sum(sizes)
    prefix = sum(sizes[:i])
    if not (_inr(container) and _inr(total) and _inr(gap) and gap >= 0 and _inr(prefix)):
        return INVALID
    free = Fr(container - (total + gap * (n - 1)))
    freep = max(Fr(0), free)
    fs = freep if safe else free
    nf = Fr(n)
    step = {1: gap + (freep / (nf - 1) if n > 1 else Fr(0)), 4: gap + freep / nf, 5: gap + freep / (nf + 1)}.get(mode, Fr(gap))
    start = {2: fs / 2, 3: fs, 4: freep / nf / 2, 5: freep / (nf + 1)}.get(mode, Fr(0))
    pos = start + sum(Fr(sizes[j]) + step for j in range(i))
    r = rhu(pos)
    return r if _inr(r) else INVALID


def auto_exact(container, gap, sizes, leads, trails, i):
    """place-main-axis-auto-margins: the position of item i. Bit j of leads / trails: item j has an auto margin on that side."""
    n = len(sizes)
    mask = (1 << n) - 1
    total = sum(sizes)
    totalg = total + gap * (n - 1)
    prefix = sum(sizes[:i]) + i * gap
    if not (_inr(container) and _inr(totalg) and _inr(gap) and gap >= 0 and _inr(prefix)):
        return INVALID
    nauto = bin(leads & mask).count("1") + bin(trails & mask).count("1")
    share = max(Fr(0), Fr(container - totalg)) / nauto if nauto else Fr(0)
    pos = Fr(0)
    for j in range(i):
        pos += ((leads >> j) & 1) * share + sizes[j] + ((trails >> j) & 1) * share + gap
    pos += ((leads >> i) & 1) * share
    r = rhu(pos)
    return r if _inr(r) else INVALID


# ---------------------------------------------------------------- the case record
def case(name, items, net, mode=None, safe=0, container=0, gap=0, autos=None, expect=None, status=None, group="grid"):
    """mode None: no justify-content placement; autos (leads, trails): auto-margin placement."""
    return dict(name=name, items=list(items), net=net, mode=mode, safe=safe, container=container, gap=gap, autos=autos,
                expect=expect, status=status, group=group)


def jmode(c):
    return ((c["mode"] or 0) & 7) | ((c["safe"] & 1) << 3) | ((1 << 8) if c["mode"] is not None else 0) | ((1 << 9) if c["autos"] else 0)


def u32(x):
    return x & 0xFFFFFFFF


def encode(c):
    """The wire stream of the guest: header words n, net, jmode, container, gap, leads, trails, 0, then 16 bytes per item."""
    leads, trails = c["autos"] or (0, 0)
    out = struct.pack("<8I", len(c["items"]), u32(c["net"]), jmode(c), u32(c["container"]), u32(c["gap"]), leads & 0xFFFF,
                      trails & 0xFFFF, 0)
    for b, mn, mx, f in c["items"]:
        out += struct.pack("<4I", u32(b), u32(mn), NONE32 if mx is None else u32(mx), u32(f))
    return out


def mix(h, v):
    return (h * 257 + 1 + (v & 0xFFFFFF)) & 0xFFFFFF


def model(c):
    """(status, sizes, offsets|None, autos|None) of a case under the exact model; status 0 or the refusal code."""
    st, sizes = sizes_exact(c["items"], c["net"])
    if st:
        return st, None, None, None
    n = len(sizes)
    offs = [offsets_exact(c["mode"], c["safe"], c["container"], c["gap"], sizes, i) for i in range(n)] if c["mode"] is not None else None
    au = [auto_exact(c["container"], c["gap"], sizes, c["autos"][0], c["autos"][1], i) for i in range(n)] if c["autos"] else None
    return 0, sizes, offs, au


def digest(c):
    """The record the guest leaves: status << 24 | digest24 (status 0: hash over sizes, then offsets, then auto offsets)."""
    st, sizes, offs, au = model(c)
    if st:
        return (-st) << 24
    h = (5381 + len(sizes)) & 0xFFFFFF
    for v in sizes:
        h = mix(h, v)
    for v in offs or []:
        h = mix(h, v)
    for v in au or []:
        h = mix(h, v)
    return h


# ---------------------------------------------------------------- hand-derived cases
def eq(name, n, net, base, fac, expect, mn=0, mx=None, **kw):
    return case(name, [(base, mn, mx, fac)] * n, net, expect=expect, group="hand", **kw)


def hand_cases():
    """Expected sizes derived BY HAND from CSS Flexbox 9.7 (resolve the flexible lengths: distribute free space by the flex
    factor, grow or shrink scaled by the base size, freeze items that violate min/max, repeat), not by running the model.
    The first group is the docstring table of resolve-flexible-lengths (1-4 items, as slice 3); the rest are 5..16 items."""
    out = []
    P = px
    # --- the docstring table of layout.cljk 9398 (also pinned by q6_flex_vs_f64 mode 0)
    out.append(case("t01-min150-of-2", [(0, P(150), None, 10000), (0, 0, None, 10000)], P(200), expect=[P(150), P(50)], group="hand"))
    out.append(case("t02-max60-of-2", [(0, 0, P(60), 10000), (0, 0, None, 10000)], P(300), expect=[P(60), P(240)], group="hand"))
    out.append(case("t03-min200-of-3", [(0, P(200), None, 10000), (0, 0, None, 10000), (0, 0, None, 10000)], P(300),
                    expect=[P(200), P(50), P(50)], group="hand"))
    out.append(case("t04-max30-of-3", [(0, 0, P(30), 10000), (0, 0, None, 10000), (0, 0, None, 10000)], P(300),
                    expect=[P(30), P(135), P(135)], group="hand"))
    out.append(case("t05-max30-max110-of-3", [(0, 0, P(30), 10000), (0, 0, P(110), 10000), (0, 0, None, 10000)], P(300),
                    expect=[P(30), P(110), P(160)], group="hand"))
    out.append(case("t06-shrink-min140", [(P(150), P(140), None, 10000), (P(150), 0, None, 10000)], P(200), expect=[P(140), P(60)], group="hand"))
    out.append(case("t07-shrink-max60", [(P(150), 0, P(60), 10000), (P(150), 0, None, 10000)], P(200), expect=[P(60), P(140)], group="hand"))
    # the freeze test is made on the exact proposal (slice 3, the case the grid found): 100 raw min, factor 0.0001, B max 10000
    out.append(case("t08-exact-proposal-freeze", [(100, 100, None, 1), (100000, 0, 10000, 10000)], 40100, expect=[100, 10000], group="hand"))
    # --- five to sixteen items
    out.append(eq("h01-six-equal-grow", 6, P(600), 0, 10000, [P(100)] * 6))
    out.append(case("h02-five-min150", [(0, P(150), None, 10000)] + [(0, 0, None, 10000)] * 4, P(500),
                    expect=[P(150)] + [P(87.5)] * 4, group="hand"))
    # 8 items, grow 1, base 0, net 800, items 0 and 1 capped at 50: pass 1 proposes 100, both freeze at 50, the six others share
    # 700 px = 44800 raw / 6 = 7466.67 -> 7467 each (each item rounds on its own, the sum is 2 raw over)
    out.append(case("h03-eight-two-capped", [(0, 0, P(50), 10000)] * 2 + [(0, 0, None, 10000)] * 6, P(800),
                    expect=[P(50)] * 2 + [7467] * 6, group="hand"))
    # the cascade: ten items grow 1, net 1000, item k capped at 20 (k+1) px for k < 7, three free. Pass 1: 100 px each, items 0..3
    # (20, 40, 60, 80) freeze; pass 2: 800 / 6 = 133.33, items 4, 5 (100, 120) freeze; pass 3: 580 / 4 = 145, item 6 (140) freezes;
    # pass 4: 440 / 3 = 146.67 -> 9387 raw, nothing violates.
    out.append(case("h04-cascade-four-passes",
                    [(0, 0, P(20 * (k + 1)), 10000) for k in range(7)] + [(0, 0, None, 10000)] * 3, P(1000),
                    expect=[P(20), P(40), P(60), P(80), P(100), P(120), P(140), 9387, 9387, 9387], group="hand"))
    # six items base 100 shrink 1 into 300: 50 each; item 0 min 80 freezes at 80; 300 - 80 - 500 = -280 over five equal weights
    out.append(case("h05-six-shrink-min80", [(P(100), P(80), None, 10000)] + [(P(100), 0, None, 10000)] * 5, P(300),
                    expect=[P(80)] + [P(44)] * 5, group="hand"))
    out.append(eq("h06-sixteen-equal-grow", 16, P(1600), 0, 10000, [P(100)] * 16))
    # sixteen bases 10 (k+1) px, shrink 1 into 1000: scaled by base, size = base * 1000 / 1360 (one rounding)
    out.append(case("h07-sixteen-scaled-shrink", [(P(10 * (k + 1)), 0, None, 10000) for k in range(16)], P(1000),
                    expect=[rhu(Fr(P(10 * (k + 1)) * 1000, 1360)) for k in range(16)], group="hand"))
    out.append(eq("h08-seven-zero-free-space", 7, P(700), P(100), 10000, [P(100)] * 7))
    out.append(eq("h09-five-no-shrink", 5, P(300), P(100), 0, [P(100)] * 5))                # shrink 0: bases, overflow
    out.append(eq("h10-five-all-min-30", 5, P(100), 0, 10000, [P(30)] * 5, mn=P(30)))        # every item freezes at its minimum
    out.append(case("h11-six-one-max-zero", [(0, 0, 0, 10000)] + [(0, 0, None, 10000)] * 5, P(500), expect=[0] + [P(100)] * 5, group="hand"))
    out.append(case("h12-six-grow-2-1", [(0, 0, None, 20000)] + [(0, 0, None, 10000)] * 5, P(700), expect=[P(200)] + [P(100)] * 5, group="hand"))
    out.append(case("h13-twelve-zero-factors", [(P(50), 0, None, 0)] * 12, P(1000), expect=[P(50)] * 12, group="hand"))
    out.append(case("h14-six-tie-half-up", [(0, 0, None, 10000)] * 6, 3, expect=[1] * 6, group="hand"))      # 0.5 raw each rounds up
    out.append(case("h15-five-grow-with-base", [(P(20), 0, None, 10000)] * 5, P(300), expect=[P(60)] * 5, group="hand"))
    out.append(case("h16-nine-mixed-ladder",
                    [(0, 0, None, 10000)] + [(0, P(40 * k), None, 10000) for k in range(1, 5)] + [(0, 0, P(30 * k), 10000) for k in range(1, 5)],
                    P(900), expect=[P(110)] * 3 + [P(120), P(160), P(30), P(60), P(90), P(110)], group="hand"))
    # --- justify-content on five 100 px items in 800 px (free 300 px = 19200 raw), exact multiples
    five = [(P(100), 0, None, 0)] * 5
    for name, mode, expect in (
            ("start", MODE_START, [P(100) * k for k in range(5)]),
            ("end", MODE_END, [P(300 + 100 * k) for k in range(5)]),
            ("center", MODE_CENTER, [P(150 + 100 * k) for k in range(5)]),
            ("between", MODE_BETWEEN, [P(75 * k + 100 * k) for k in range(5)]),
            ("around", MODE_AROUND, [P(30 + 160 * k) for k in range(5)]),
            ("evenly", MODE_EVENLY, [P(50 + 150 * k) for k in range(5)])):
        c = case("j-" + name, five, P(500), mode=mode, container=P(800), expect=[P(100)] * 5, group="hand")
        c["offsets"] = expect
        out.append(c)
    c = case("j-end-safe-overflow", five, P(500), mode=MODE_END, safe=1, container=P(400), expect=[P(100)] * 5, group="hand")
    c["offsets"] = [P(100) * k for k in range(5)]                        # safe: the negative free space is clamped at zero
    out.append(c)
    c = case("j-end-unsafe-overflow", five, P(500), mode=MODE_END, safe=0, container=P(400), expect=[P(100)] * 5, group="hand")
    c["offsets"] = [P(100 * k - 100) for k in range(5)]
    out.append(c)
    c = case("a-one-auto-lead", five, P(500), container=P(800), autos=(0b00100, 0), expect=[P(100)] * 5, group="hand")
    c["autos_expect"] = [0, P(100), P(500), P(600), P(700)]
    out.append(c)
    c = case("a-two-autos-split", five, P(500), container=P(800), gap=P(10), autos=(0b00010, 0b01000), expect=[P(100)] * 5, group="hand")
    # free = 800 - (500 + 40) = 260; two auto margins, 130 each: item 1 has one in front, item 4 follows two
    c["autos_expect"] = [0, P(110) + P(130), P(220) + P(130), P(330) + P(130), P(440) + P(260)]
    out.append(c)
    # --- refusals: the bound of sixteen, and the domain
    out.append(case("r-seventeen-items", [(0, 0, None, 10000)] * 17, P(100), status=1, group="hand"))
    out.append(case("r-255-items", [(0, 0, None, 10000)] * 255, P(100), status=1, group="hand"))
    out.append(case("r-no-items", [], P(100), status=2, group="hand"))
    out.append(case("r-base-262144", [(262144, 0, None, 1)], 0, status=3, group="hand"))
    out.append(case("r-min-262144", [(0, 262144, None, 1)], 0, status=3, group="hand"))
    out.append(case("r-max-262143", [(0, 0, 262143, 1)], 0, status=3, group="hand"))
    out.append(case("r-factor-65536", [(0, 0, None, 65536)], 0, status=3, group="hand"))
    out.append(case("r-net-524288", [(0, 0, None, 1)], 524288, status=4, group="hand"))
    out.append(case("r-net-minus-524289", [(0, 0, None, 1)], -524289, status=4, group="hand"))
    out.append(case("r-bad-item-after-ok", [(0, 0, None, 1)] * 5 + [(0, 262144, None, 1)], 100, status=3, group="hand"))
    return out


# ---------------------------------------------------------------- the grid
def capacity_cases():
    """Both sides of every bound: n 1/16/17, base, min, max, factor, net, and the extreme sixteen-item sums."""
    out = []
    hi = lambda **k: [(BASE_MAX, 0, None, FAC_MAX)] * 16
    out.append(case("cap-n1", [(100, 0, None, 1)], 200, group="cap"))
    out.append(case("cap-n16", [(100, 0, None, 1)] * 16, 4000, group="cap"))
    out.append(case("cap-n16-all-max-shrink", hi(), NET_LO, group="cap"))                    # weights 16 * 65535 * 262143 < 2^38
    out.append(case("cap-n16-all-max-shrink-zero", hi(), 0, group="cap"))
    out.append(case("cap-n16-all-max-grow", [(BASE_MAX, 0, None, FAC_MAX)] * 16, NET_HI, group="cap"))
    out.append(case("cap-n16-bases-max-net-max", [(BASE_MAX, 0, None, 1)] * 16, NET_HI, group="cap"))   # |R| near 2^22 on the shrink side
    out.append(case("cap-n16-bases-max-net-min", [(BASE_MAX, 0, None, 3)] * 16, NET_LO, group="cap"))
    out.append(case("cap-base-max", [(BASE_MAX, 0, None, 1), (0, 0, None, 1)], 300000, group="cap"))
    out.append(case("cap-min-max", [(0, MIN_MAX, None, 1), (0, 0, None, 1)], 100, group="cap"))
    out.append(case("cap-max-max", [(0, 0, MAX_MAX, 1), (0, 0, None, 1)], 500000, group="cap"))
    out.append(case("cap-max-zero", [(0, 0, 0, 1), (0, 0, None, 1)], 500, group="cap"))
    out.append(case("cap-factor-max", [(0, 0, None, FAC_MAX), (0, 0, None, 1)], 65536, group="cap"))
    out.append(case("cap-net-max", [(0, 0, None, 1)] * 5, NET_HI, group="cap"))
    out.append(case("cap-net-min", [(0, 0, None, 1)] * 5, NET_LO, group="cap"))
    out.append(case("cap-net-min-shrink", [(BASE_MAX, 0, None, 1)] * 5, NET_LO, group="cap"))
    for nm, items, net, st in (
            ("cap-past-n17", [(1, 0, None, 1)] * 17, 10, 1),
            ("cap-past-n32", [(1, 0, None, 1)] * 32, 10, 1),
            ("cap-past-base", [(BASE_MAX + 1, 0, None, 1)] * 5, 10, 3),
            ("cap-past-min", [(0, MIN_MAX + 1, None, 1)] * 5, 10, 3),
            ("cap-past-max", [(0, 0, MAX_MAX + 1, 1)] * 5, 10, 3),
            ("cap-past-factor", [(0, 0, None, FAC_MAX + 1)] * 5, 10, 3),
            ("cap-past-net-hi", [(0, 0, None, 1)] * 5, NET_HI + 1, 4),
            ("cap-past-net-lo", [(0, 0, None, 1)] * 5, NET_LO - 1, 4),
            ("cap-past-n-last-item", [(1, 0, None, 1)] * 15 + [(BASE_MAX + 1, 0, None, 1)], 10, 3)):
        out.append(case(nm, items, net, status=st, group="cap"))
    # placement bounds: Q6 range 2^30
    five = [(100, 0, None, 0)] * 5
    out.append(case("cap-place-container-max", five, 500, mode=MODE_END, container=INR, group="cap"))
    out.append(case("cap-place-container-past", five, 500, mode=MODE_END, container=INR + 1, group="cap"))
    out.append(case("cap-place-gap-max", five, 500, mode=MODE_START, container=INR, gap=INR, group="cap"))
    out.append(case("cap-place-gap-past", five, 500, mode=MODE_START, container=1000, gap=INR + 1, group="cap"))
    out.append(case("cap-place-result-past", five, 500, mode=MODE_END, container=INR, gap=INR // 4, group="cap"))
    out.append(case("cap-auto-container-past", five, 500, autos=(1, 0), container=INR + 1, group="cap"))
    out.append(case("cap-auto-gap-neg", five, 500, autos=(1, 0), container=1000, gap=-1, group="cap"))
    out.append(case("cap-place-negative-container", five, 500, mode=MODE_CENTER, container=-4000, gap=7, group="cap"))
    return out


def bound_cases():
    """Items sitting on a min/max bound, and one raw either side of it, in lines of 5..16 items."""
    out = []
    for n in (5, 8, 16):
        share = 6400 + 13                               # a proposal of 100 px + 13 raw for n equal grow items
        net = share * n
        for tag, mx, mn in (("max-eq", share, 0), ("max-below", share - 1, 0), ("max-above", share + 1, 0),
                            ("min-eq", None, share), ("min-above", None, share + 1), ("min-below", None, share - 1)):
            items = [(0, mn, mx, 10000)] + [(0, 0, None, 10000)] * (n - 1)
            out.append(case("bound-%s-n%d" % (tag, n), items, net, group="bound"))
        # a fractional proposal a hair beyond a bound: net n * 100 px + 1 raw over n items, max = 100 px
        out.append(case("bound-frac-above-n%d" % n, [(0, 0, 6400, 10000)] + [(0, 0, None, 10000)] * (n - 1), 6400 * n + 1, group="bound"))
        out.append(case("bound-frac-min-n%d" % n, [(0, 6400, None, 10000)] + [(0, 0, None, 10000)] * (n - 1), 6400 * n - 1, group="bound"))
        # shrink on a bound: bases 100 px, net 90 % of the sum, the first item's min equal to its proposal
        net = 5760 * n
        out.append(case("bound-shrink-min-eq-n%d" % n, [(6400, 5760, None, 10000)] + [(6400, 0, None, 10000)] * (n - 1), net, group="bound"))
        out.append(case("bound-shrink-min-above-n%d" % n, [(6400, 5761, None, 10000)] + [(6400, 0, None, 10000)] * (n - 1), net, group="bound"))
        out.append(case("bound-shrink-max-eq-n%d" % n, [(6400, 0, 5760, 10000)] + [(6400, 0, None, 10000)] * (n - 1), net, group="bound"))
        out.append(case("bound-shrink-max-below-n%d" % n, [(6400, 0, 5759, 10000)] + [(6400, 0, None, 10000)] * (n - 1), net, group="bound"))
    return out


def cascade_cases():
    """Cascades of freezes: a ladder of caps (grow) and of floors (shrink) so that every pass freezes one more item."""
    out = []
    for n in (5, 6, 9, 12, 16):
        # grow: item k capped at 40 (k + 1) px, net n * 100 px: the caps below the running share freeze one by one
        out.append(case("casc-grow-caps-n%d" % n, [(0, 0, px(40 * (k + 1)), 10000) for k in range(n)], px(100 * n), group="cascade"))
        out.append(case("casc-grow-caps-rev-n%d" % n, [(0, 0, px(40 * (n - k)), 10000) for k in range(n)], px(100 * n), group="cascade"))
        # grow with weights k+1
        out.append(case("casc-grow-weighted-n%d" % n, [(0, 0, px(30 * (k + 1)), min(65535, 5000 * (k + 1))) for k in range(n)], px(90 * n), group="cascade"))
        # shrink: floors on the large items
        out.append(case("casc-shrink-floors-n%d" % n, [(px(50 * (k + 1)), px(40 * (k + 1)), None, 10000) for k in range(n)], px(30 * n * (n + 1) // 2), group="cascade"))
        out.append(case("casc-shrink-floors-mid-n%d" % n, [(px(100), px(60 + 5 * k), None, 10000) for k in range(n)], px(55 * n), group="cascade"))
        # mixed: floors and caps freeze in different passes
        out.append(case("casc-mixed-n%d" % n, [(px(10 * k), px(8 * k) if k % 2 else 0, px(30 * k) if k % 3 == 0 and k else None, 10000) for k in range(n)], px(60 * n), group="cascade"))
        # an item that gives space back: first-pass cap, later items grow past their own proposals
        out.append(case("casc-giveback-n%d" % n, [(0, 0, 640, 10000)] + [(0, 0, px(10 * (k + 11)), 10000) for k in range(1, n)], px(12 * n), group="cascade"))
    return out


def tie_cases():
    """Exact ties of the half-up rounding: equal weights, an odd number of raw units to share."""
    out = []
    for n in (2, 4, 5, 6, 8, 10, 12, 16):
        for net in sorted({1, 3, n // 2, n // 2 + 1, n + n // 2, 2 * n - 1}):
            out.append(case("tie-n%d-net%d" % (n, net), [(0, 0, None, 10000)] * n, net, group="tie"))
    for n in (6, 10, 14):
        out.append(case("tie-weighted-n%d" % n, [(0, 0, None, 5000 + 5000 * (k % 2)) for k in range(n)], 3 * n // 2, group="tie"))
        out.append(case("tie-shrink-n%d" % n, [(2, 0, None, 10000)] * n, n, group="tie"))
    return out


def place_cases():
    """All six justify-content modes, both safe values, and auto margins, on solved lines of 5..16 items."""
    out = []
    rnd = random.Random(932)
    for n in (5, 9, 16):
        items = [(px(20 + 7 * k), 0, None, 0) for k in range(n)]
        total = sum(b for b, _, _, _ in items)
        for mode in range(6):
            for safe in (0, 1):
                for ctag, container in (("roomy", total + px(300) + 5), ("tight", total - px(10)), ("exact", total + 3 * (n - 1))):
                    out.append(case("place-n%d-m%d-s%d-%s" % (n, mode, safe, ctag), items, total, mode=mode, safe=safe, container=container,
                                    gap=3, group="place"))
        for k in range(6):
            leads, trails = rnd.getrandbits(n), rnd.getrandbits(n)
            out.append(case("autom-n%d-%d" % (n, k), items, total, autos=(leads, trails), container=total + px(100) + k, gap=k, group="place"))
        out.append(case("autom-none-n%d" % n, items, total, autos=(0, 0), container=total + px(100), gap=2, group="place"))
        out.append(case("autom-all-n%d" % n, items, total, autos=((1 << n) - 1, (1 << n) - 1), container=total + px(100) + 1, gap=0, group="place"))
        out.append(case("autom-negative-free-n%d" % n, items, total, autos=(5, 2), container=total - 50, gap=1, group="place"))
    return out


def random_cases(count, seed=9320):
    rnd = random.Random(seed)
    out = []
    bases = [0, 1, 63, 64, 65, 640, 3200, 6400, 9600, 19200, 64000, 12800]
    facs = [0, 1, 2500, 5000, 10000, 10000, 10000, 15000, 20000, 30000, 33333, 65535]
    nets = [0, 1, 12800, 19200, 38400, 76800, 262144, -1000, 524287, -524288, 6400, 25600, 9600, 102400, 1638]
    for k in range(count):
        r = rnd.random()
        n = rnd.randint(1, 4) if r < 0.2 else rnd.randint(5, 16)
        items = []
        clamp_p = rnd.choice((0.0, 0.3, 0.6, 0.9))
        for _ in range(n):
            b = rnd.choice(bases) if rnd.random() < 0.8 else rnd.randint(0, BASE_MAX)
            f = rnd.choice(facs) if rnd.random() < 0.9 else rnd.randint(0, FAC_MAX)
            mn = rnd.choice((0, 0, 1280, 3200, 6400, 9600, 12800, 19200)) if rnd.random() < clamp_p else 0
            mx = rnd.choice((0, 640, 1920, 3200, 6400, 9600, 12800, 25600)) if rnd.random() < clamp_p else None
            if rnd.random() < 0.05:
                mn = rnd.randint(0, MIN_MAX)
            if rnd.random() < 0.05:
                mx = rnd.randint(0, MAX_MAX)
            items.append((b, mn, mx, f))
        net = rnd.choice(nets) if rnd.random() < 0.6 else rnd.randint(NET_LO, NET_HI) if rnd.random() < 0.3 else rnd.randint(0, 40 * n * 64)
        if rnd.random() < 0.15:                       # a line that is almost balanced, to put free space near zero
            net = sum(b for b, _, _, _ in items) + rnd.randint(-3, 3)
            net = max(NET_LO, min(NET_HI, net))
        c = case("rnd-%04d-n%d" % (k, n), items, net, group="random")
        if rnd.random() < 0.35:
            st, sz = sizes_exact(items, net)
            tot = sum(sz) if st == 0 else 0
            c["mode"], c["safe"] = rnd.randint(0, 5), rnd.randint(0, 1)
            c["container"] = max(0, tot + rnd.randint(-2000, 20000))
            c["gap"] = rnd.choice((0, 0, 1, 64, 640, 3))
        if rnd.random() < 0.25:
            c["autos"] = (rnd.getrandbits(n), rnd.getrandbits(n))
            if c["mode"] is None:
                st, sz = sizes_exact(items, net)
                c["container"] = max(0, (sum(sz) if st == 0 else 0) + rnd.randint(-500, 30000))
                c["gap"] = rnd.choice((0, 1, 64, 5))
        out.append(c)
    return out


def small_cases(count, seed=9321):
    """Lines of one to four items, the range flex_q6 is defined on: a clamp on many items and the nets of the slice-3 differential
    grid (q6_flex_vs_f64 net-of)."""
    rnd = random.Random(seed)
    out = []
    bases = [0, 1, 63, 64, 65, 640, 3200, 6400, 9600, 19200, 64000, 262143, 12800]
    facs = [0, 1, 2500, 5000, 10000, 10000, 15000, 20000, 30000, 33333, 65535]
    mins = [0, 0, 0, 0, 1, 1280, 3200, 6400, 9600, 12800, 19200, 262143]
    maxs = [None, None, None, 0, 640, 1920, 3200, 6400, 9600, 12800]
    nets = [0, 1, 12800, 19200, 38400, 76800, 262143, -1000, 524287, -524288, 6400, 25600, 9600]
    for k in range(count):
        n = rnd.randint(1, 4)
        items = [(rnd.choice(bases) if rnd.random() < 0.85 else rnd.randint(0, BASE_MAX), rnd.choice(mins), rnd.choice(maxs), rnd.choice(facs))
                 for _ in range(n)]
        net = rnd.choice(nets) if rnd.random() < 0.7 else rnd.randint(NET_LO, NET_HI) if rnd.random() < 0.2 else rnd.randint(0, 20000)
        c = case("small-%04d-n%d" % (k, n), items, net, group="small")
        if rnd.random() < 0.3:
            st, sz = sizes_exact(items, net)
            c["mode"], c["safe"] = rnd.randint(0, 5), rnd.randint(0, 1)
            c["container"] = max(0, (sum(sz) if st == 0 else 0) + rnd.randint(-1000, 12000))
            c["gap"] = rnd.choice((0, 64, 1, 640))
        out.append(c)
    return out


def all_cases(random_count=520):
    cases = hand_cases() + capacity_cases() + bound_cases() + cascade_cases() + tie_cases() + place_cases() + random_cases(random_count) + small_cases(140)
    names = [c["name"] for c in cases]
    assert len(names) == len(set(names)), "duplicate case names"
    return cases


def expected_status(c):
    """0, or the refusal code the model assigns."""
    return model(c)[0]
