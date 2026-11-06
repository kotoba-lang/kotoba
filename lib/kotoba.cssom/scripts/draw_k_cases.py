"""Case grid, independent host-side reference and draw-list decoder of the draw slice (JUN-805, ADR-0287): the laid-out box table of
flow-k becomes a draw list in a shared region (src/cssom/draw_k.kotoba).

A case is a dict of layout_k_cases (name, rules, doc, vw, status = the layout status the style / layout stages must answer, ref, boxes,
doch) and, for the draw stage, `ops` (hand-derived draw list: tuples (element, role, x, y, w, h, 0xRRGGBBAA) with px coordinates) and
`dstatus` (the positive refusal code the draw stage must answer, 0 when it runs). Hand-derived cases give `boxes` in px (as the layout
grid) so the reference can also be run on the hand-derived table, and the observer compares the kernel's table with it.

The reference (`expected`) is deliberately independent of draw_k.kotoba: it has its own cascade (single compound selectors with tag, id
and classes, specificity, !important, source order), its own colour parser and its own CSS 2.1 Appendix E ordering, and works from the
box table words the kernel produced. The decoder (`decode`) reads the raw words of the region, checks the structure and returns the ops.
Nothing here is random at run time."""
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout_k_cases as L  # noqa: E402
import style_k_cases as K  # noqa: E402

T, R, Q, B = K.T, L.R, L.Q, L.B
MAGIC = 829836356
MAX_OPS = 255
ROLE = {"bg": 0, "top": 1, "right": 2, "bottom": 3, "left": 4}
W = L.WORD


# ---------------------------------------------------------------- reference
def parse_color(v):
    """None for absent / transparent, "bad" outside the grammar, else the u32 r<<24|g<<16|b<<8|255."""
    if v is None or v.lower() == "transparent":
        return None
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v)
    if not m:
        return "bad"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h, 16) << 8) | 255


def _spec(sel):
    m = re.fullmatch(r"(\*|[a-z0-9]+)?(#[A-Za-z0-9_-]+)?((?:\.[A-Za-z0-9_-]+)*)", sel)
    assert m and sel, ("selector outside the reference subset", sel)
    tag, idv, cls = m.group(1), m.group(2), [c for c in (m.group(3) or "").split(".") if c]
    return tag, (idv or "")[1:], cls


def _matches(sel, el):
    tag, idv, cls = _spec(sel)
    t, i, c, _p, _s = el
    return (tag in (None, "*") or tag == t) and (not idv or idv == i) and all(x in c.split() for x in cls)


def _specificity(sel):
    tag, idv, cls = _spec(sel)
    return (1 if idv else 0, len(cls), 1 if tag not in (None, "*") else 0)


def computed(rules, el, prop):
    """The winning value of a non-inherited property for one element, or None: important, origin, specificity, source order."""
    best = None
    for ri, (origin, sel, decls) in enumerate(rules):
        if not _matches(sel, el):
            continue
        for di, (p, v, imp) in enumerate(decls):
            if p == prop:
                key = (1 if imp else 0, origin, _specificity(sel), ri, di)
                if best is None or key > best[0]:
                    best = (key, v)
    return None if best is None else best[1]


def rect_ops(table, i, bg, bc):
    """The ops of element i in Appendix E order, each (element, role, x, y, w, h, colour); empty rectangles are left out."""
    kind, x, y, w, h = (table[22 * i + W[k]] for k in ("kind", "x", "y", "w", "h"))
    bt, br, bb, bl = (table[22 * i + W[k]] for k in ("bt", "br", "bb", "bl"))
    out = []
    if bg is not None:
        out.append((i, 0, x, y, w, h, bg))
    if bc is not None:
        out += [(i, 1, x, y, w, bt, bc), (i, 2, x + w - br, y + bt, br, h - (bt + bb), bc),
                (i, 3, x, y + h - bb, w, bb, bc), (i, 4, x, y + bt, bl, h - (bt + bb), bc)]
    return [o for o in out if o[4] > 0 and o[5] > 0]


def expected(case, table):
    """(status, ops): status 0 or the positive refusal code; on a refusal the ops emitted before it (as the kernel writes them)."""
    els = K.flat(case["doc"])
    ops = []
    for i, el in enumerate(els):
        if table[22 * i] != 1:
            continue
        bg = parse_color(computed(case["rules"], el, "background-color"))
        bc = parse_color(computed(case["rules"], el, "border-color"))
        if bg == "bad" or bc == "bad":
            return 20, ops, i + 1
        for o in rect_ops(table, i, bg, bc):
            if any(abs(v) > 1 << 30 for v in (o[2], o[3], o[2] + o[4], o[3] + o[5])):
                return 18, ops, 0
            if len(ops) >= MAX_OPS:
                return 21, ops, 0
            ops.append(o)
    return 0, ops, 0


def hand_ops(case):
    return [(e, r, Q(x), Q(y), Q(w), Q(h), c) for e, r, x, y, w, h, c in case["ops"]]


def sgn(v):
    return v - (1 << 32) if v >= 1 << 31 else v


def decode(words, nn):
    """The raw u32 words of the region (header + op slots) -> (header dict, ops); every structural fault is an AssertionError."""
    assert len(words) % 8 == 0 and len(words) >= 8, len(words)
    hdr = dict(magic=words[0], count=words[1], status=words[2], elements=words[3], height=sgn(words[4]), slot=words[5])
    assert hdr["magic"] == MAGIC, hex(hdr["magic"])
    assert hdr["slot"] == 32 and words[6] == 0 and words[7] == 0, "header slot size / reserved words"
    assert hdr["count"] <= MAX_OPS and len(words) == 8 * (hdr["count"] + 1), (hdr["count"], len(words))
    assert hdr["elements"] == nn, (hdr["elements"], nn)
    ops = []
    for s in range(1, hdr["count"] + 1):
        w = words[8 * s:8 * s + 8]
        assert w[0] == 1, ("op code", s, w[0])
        assert w[6] < nn and w[7] <= 4, ("op element / role", s, w[6], w[7])
        assert w[1] < 1 << 32 and all(0 <= sgn(v) + (1 << 31) < 1 << 32 for v in w[1:5])
        ops.append((w[6], w[7], sgn(w[1]), sgn(w[2]), sgn(w[3]), sgn(w[4]), w[5]))
    return hdr, ops


# ---------------------------------------------------------------- cases
def table_of(case):
    words, masks, dm = L.hand_table(case)
    return words, masks


def D(name, rules, doc, boxes, ops, vw=400, dstatus=0, note=None):
    c = dict(name="draw-" + name, rules=rules, doc=doc, vw=Q(vw), status=0, ref=False, boxes=boxes, doch=None, ops=ops, dstatus=dstatus)
    if note:
        c["note"] = note
    return c


def X(name, rules, doc, dstatus, vw=400, ops=None, note=None, status=0):
    c = dict(name=name, rules=rules, doc=doc, vw=Q(vw), status=status, ref=False, boxes=None, doch=None, ops=ops, dstatus=dstatus)
    if note:
        c["note"] = note
    return c


def hand_cases():
    C = []
    add = C.append
    d = lambda *kids, cls="a", idv="": T("div", idv, cls, *kids)
    red, green, blue = 0xFF0000FF, 0x00FF00FF, 0x0000FFFF
    bgc = lambda v: dict(background_color=v)
    add(D("bg-only", [R(".a", width="100px", height="30px", **bgc("#ff0000"))], d(), [B(0, 0, 100, 30)], [(0, 0, 0, 0, 100, 30, red)]))
    add(D("bg-short-hex", [R(".a", width="100px", height="30px", **bgc("#0f8"))], d(), [B(0, 0, 100, 30)], [(0, 0, 0, 0, 100, 30, 0x00FF88FF)]))
    add(D("bg-upper-hex", [R(".a", width="100px", height="30px", **bgc("#AbCdEf"))], d(), [B(0, 0, 100, 30)], [(0, 0, 0, 0, 100, 30, 0xABCDEFFF)]))
    bw = dict(border_top_width="1px", border_right_width="2px", border_bottom_width="3px", border_left_width="4px")
    box4 = B(0, 0, 106, 24, bt=1, br=2, bb=3, bl=4)
    border4 = lambda c: [(0, 1, 0, 0, 106, 1, c), (0, 2, 104, 1, 2, 20, c), (0, 3, 0, 21, 106, 3, c), (0, 4, 0, 1, 4, 20, c)]
    add(D("border-only", [R(".a", width="100px", height="20px", border_color="#000", **bw)], d(), [box4], border4(0x000000FF),
          note="top and bottom span the border box, left and right sit between them: right x = 106 - 2, height = 24 - (1 + 3)"))
    add(D("bg-and-border", [R(".a", width="100px", height="20px", border_color="#00f", **bgc("#fff"), **bw)], d(), [box4],
          [(0, 0, 0, 0, 106, 24, 0xFFFFFFFF)] + border4(blue), note="the background first, then top, right, bottom, left"))
    b1 = dict(border_top_width="1px", border_right_width="1px", border_bottom_width="1px", border_left_width="1px")
    add(D("transparent-bg-border-only", [R(".a", width="100px", height="20px", border_color="#f00", **bgc("transparent"), **b1)], d(),
          [B(0, 0, 102, 22, bt=1, br=1, bb=1, bl=1)],
          [(0, 1, 0, 0, 102, 1, red), (0, 2, 101, 1, 1, 20, red), (0, 3, 0, 21, 102, 1, red), (0, 4, 0, 1, 1, 20, red)]))
    add(D("border-color-without-widths", [R(".a", height="10px", border_color="#f00")], d(), [B(0, 0, 400, 10)], []))
    add(D("widths-without-color", [R(".a", height="10px", **b1)], d(), [B(0, 0, 400, 12, bt=1, br=1, bb=1, bl=1)], [],
          note="no border-color: currentcolor is not modelled, nothing is painted"))
    add(D("partial-borders", [R(".a", height="10px", border_bottom_width="2px", border_left_width="3px", border_color="#0f0")], d(),
          [B(0, 0, 400, 12, bb=2, bl=3)], [(0, 3, 0, 10, 400, 2, green), (0, 4, 0, 0, 3, 10, green)],
          note="zero top / right widths leave no rectangle; the left border spans h - (bt + bb) = 10"))
    pad = dict(padding_top="10px", padding_right="10px", padding_bottom="10px", padding_left="10px")
    inner = d(cls="i")
    add(D("nested-order", [R(".o", **pad, **bgc("#ff0000")), R(".i", height="20px", **bgc("#0000ff"))], T("div", "", "o", inner),
          [B(0, 0, 400, 40), B(10, 10, 380, 20)], [(0, 0, 0, 0, 400, 40, red), (1, 0, 10, 10, 380, 20, blue)], note="tree order: the parent's background before the child's"))
    ab = [R(".a", height="10px", margin_bottom="20px", **bgc("#ff0000")), R(".b", height="10px", margin_top="30px", **bgc("#0000ff"))]
    add(D("siblings-collapse", ab, T("div", "", "o", T("div", "", "a"), T("div", "", "b")), [B(0, 0, 400, 50), B(0, 0, 400, 10), B(0, 40, 400, 10)],
          [(1, 0, 0, 0, 400, 10, red), (2, 0, 0, 40, 400, 10, blue)], note="the container has no paint; the margins collapse to 30, so b is at y = 10 + 30 = 40"))
    add(D("display-none-not-painted", [R(".a", height="10px", **bgc("#00ff00")), R(".n", display="none", height="50px", **bgc("#ff0000"))],
          T("div", "", "o", T("div", "", "a"), T("div", "", "n"), T("div", "", "a")),
          [B(0, 0, 400, 20), B(0, 0, 400, 10), dict(kind=0), B(0, 10, 400, 10)], [(1, 0, 0, 0, 400, 10, green), (3, 0, 0, 10, 400, 10, green)]))
    add(D("zero-height-not-emitted", [R(".a", height="0px", **bgc("#ff0000"))], d(), [B(0, 0, 400, 0)], []))
    add(D("border-box", [R(".a", width="100px", height="20px", box_sizing="border-box", padding_top="5px", padding_bottom="5px", border_top_width="1px",
                           border_bottom_width="1px", border_color="#123456", **bgc("#abcdef"))], d(), [B(0, 0, 100, 20, bt=1, bb=1)],
          [(0, 0, 0, 0, 100, 20, 0xABCDEFFF), (0, 1, 0, 0, 100, 1, 0x123456FF), (0, 3, 0, 19, 100, 1, 0x123456FF)]))
    add(D("auto-margins-centre", [R(".a", width="100px", height="10px", margin_left="auto", margin_right="auto", **bgc("#ff00ff"))], d(),
          [B(150, 0, 100, 10)], [(0, 0, 150, 0, 100, 10, 0xFF00FFFF)]))
    add(D("fractional-q6", [R(".a", width="10.5px", height="0.25px", **bgc("#808080"))], d(), [B(0, 0, 10.5, 0.25)], [(0, 0, 0, 0, 10.5, 0.25, 0x808080FF)],
          note="Q6 raw 672 x 16"))
    add(D("id-beats-class", [R(".a", **bgc("#ff0000"), height="5px"), R("#x", **bgc("#0000ff"))], d(idv="x"), [B(0, 0, 400, 5)], [(0, 0, 0, 0, 400, 5, blue)]))
    add(D("important-beats-id", [R(".a", background_color=("#ff0000", True), height="5px"), R("#x", **bgc("#0000ff"))], d(idv="x"), [B(0, 0, 400, 5)],
          [(0, 0, 0, 0, 400, 5, red)]))
    add(D("later-rule-wins", [R(".a", **bgc("#ff0000"), height="5px"), R(".b", **bgc("#00ff00"))], d(cls="a b"), [B(0, 0, 400, 5)], [(0, 0, 0, 0, 400, 5, green)]))
    add(D("background-is-not-inherited", [R(".o", height="20px", **bgc("#ff0000")), R(".i", height="5px")], T("div", "", "o", inner),
          [B(0, 0, 400, 20), B(0, 0, 400, 5)], [(0, 0, 0, 0, 400, 20, red)]))
    # refusals of the draw stage
    for nm, rule in (("name", dict(background_color="red")), ("hex-five", dict(background_color="#abcd1")), ("hex-digit", dict(background_color="#12g")),
                     ("hash-only", dict(background_color="#")), ("hex-eight", dict(background_color="#ff000080")),
                     ("border-rgb", dict(border_color="rgb(1, 2, 3)")), ("hex-four", dict(background_color="#abcd"))):
        add(X("draw-refuse-colour-" + nm, [R(".a", height="10px", **rule)], d(), 20, ops=[]))
    add(X("draw-refuse-second-element", [R(".a", height="10px", **bgc("#ff0000")), R(".b", height="10px", **bgc("#ff0000x"))],
          T("div", "", "o", T("div", "", "a"), T("div", "", "b")), 20, note="the op of the first child is written before the refusal"))
    add(X("draw-colour-in-display-none-is-not-read", [R(".n", display="none", **bgc("red")), R(".a", height="3px", **bgc("#00ff00"))],
          T("div", "", "o", T("div", "", "n"), T("div", "", "a")), 0, ops=[(2, 0, 0, 0, 400, 3, green)]))
    return C


def many(n, extra=None):
    kid = T("div", "", "a")
    return T("div", "", "a", *[kid for _ in range(n - 1)])


def bound_cases():
    C = []
    five = [R(".a", height="2px", border_top_width="1px", border_right_width="1px", border_bottom_width="1px", border_left_width="1px",
              border_color="#0a0b0c", background_color="#ddeeff")]
    C.append(X("draw-bound-ops-255-at", five, many(51), 0, note="51 boxes x 5 ops = 255, the whole region"))
    C.append(X("draw-bound-ops-256-past", five, many(52), 21, note="the 256th op is refused, 255 are in the region"))
    C.append(X("draw-bound-elements-128-bg", [R(".a", height="1px", background_color="#010203")], many(128), 0))
    C.append(X("draw-bound-elements-128-five", five, many(128), 21))
    m = "2097151px"
    C.append(X("draw-bound-x-plus-w-past", [R(".a", margin_left=m, width=m, height="1px", background_color="#112233")],
               _chain_a(8), 18, note="x of the 8th box is 8 x 134217664 raw, x + w passes 2^30 while the layout bound is on x alone"))
    names = L.SUPPORTED[:14]
    vals = ["block", "300px", "10px", "1px", "400px", "content-box", "1px", "1px", "1px", "1px", "1px", "1px", "1px", "1px"]
    C.append(X("draw-bound-properties-16-at", [(1, "div", list(zip(names, vals, [False] * 14)) + [("background-color", "#fafafa", False), ("border-color", "#050505", False)])],
               ("div", "", "", []), 0))
    return C


def _chain_a(n):
    node = T("div", "", "a")
    for _ in range(n - 1):
        node = T("div", "", "a", node)
    return node


COLORS = ["#f00", "#FFF", "#0a1B2c", "#123456", "#abc", "transparent", "#000", "#0F0", "#fedcba"]


def random_cases(seed, n):
    rng = random.Random(seed)
    out = []
    classes = ["c%d" % i for i in range(5)]
    layout_names = ["width", "height", "margin-top", "margin-bottom", "margin-left", "padding-top", "padding-left", "padding-bottom",
                    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width", "min-width", "box-sizing"]
    for i in range(n):
        doc = K.rand_doc(rng, rng.choice([6, 12, 24, 48]), rng.choice([3, 5, 9]))

        def remap(nd):
            cl = " ".join(sorted(set(rng.choice(classes) for _ in range(rng.randint(0, 2)))))
            return ("div", "", cl, [remap(k) for k in nd[3]])
        doc = remap(doc)
        names = rng.sample(layout_names, rng.randint(4, 12))
        rules = [(1, "*", [("display", "block", False)])]
        for c in classes:
            dec = []
            for p in rng.sample(names, rng.randint(1, min(6, len(names)))):
                if p == "box-sizing":
                    v = rng.choice(["border-box", "content-box"])
                elif p.endswith("-width") and p.startswith("border"):
                    v = rng.choice(["0px", "1px", "2px", "3.5px"])
                elif p in ("width", "min-width"):
                    v = rng.choice(["50%", "120px", "250px", "33.33%", "10.5px"])
                elif p == "height":
                    v = rng.choice(["3px", "14px", "20px", "0.5px", "7px"])
                elif p.startswith("margin"):
                    v = rng.choice(["0px", "4px", "8px", "-3px", "auto"] if p == "margin-left" else ["0px", "4px", "8px", "-3px"])
                else:
                    v = rng.choice(["0px", "2px", "6px", "12px"])
                dec.append((p, v, False))
            if rng.random() < 0.7:
                dec.append(("background-color", rng.choice(COLORS), rng.random() < 0.1))
            if rng.random() < 0.5:
                dec.append(("border-color", rng.choice(COLORS), False))
            rules.append((1, "." + c, dec))
        if rng.random() < 0.3:
            rules.append((1, "div", [("background-color", rng.choice(COLORS), False)]))
        if rng.random() < 0.04:
            rules.append((1, "." + rng.choice(classes), [("background-color", "red", False)]))
        out.append(dict(name="draw-random-%03d" % i, rules=rules, doc=doc, vw=rng.choice([Q(320), Q(480), Q(800), 25600 + 7]), status=None, ref=False,
                        boxes=None, doch=None, ops=None, dstatus=None))
    return out


def real_cases():
    C = []
    for k, doc in enumerate(K.component_docs()):
        rules = L.block_sheet(doc, k)
        cls = []

        def go(n):
            for c in (n[2] or "").split(" "):
                if c and c not in cls:
                    cls.append(c)
            for x in n[3]:
                go(x)
        go(doc)
        rng = random.Random("draw/%d" % k)
        rules = rules + [(1, "." + c, [("background-color", rng.choice(COLORS), False), ("border-color", rng.choice(COLORS), False)]) for c in cls]
        C.append(dict(name="draw-component-block-%02d" % k, rules=rules, doc=doc, vw=Q(480), status=None, ref=False, boxes=None, doch=None, ops=None, dstatus=None))
    return C


def all_cases(seed=20261107, n_random=70):
    cases = hand_cases() + bound_cases() + real_cases() + random_cases(seed, n_random)
    names = [c["name"] for c in cases]
    assert len(set(names)) == len(names) and len(cases) <= 480, len(cases)
    return cases


def selftest():
    """The reference reproduces every hand-derived draw list from the hand-derived table (it must hold before the kernel is looked at)."""
    n = 0
    for c in all_cases():
        if c.get("boxes") is None or c.get("ops") is None:
            continue
        words, _masks = table_of(c)
        st, ops, _off = expected(c, words)
        assert st == c["dstatus"] and ops == hand_ops(c), (c["name"], st, ops, hand_ops(c))
        n += 1
    return n


if __name__ == "__main__":
    cs = all_cases()
    print(len(cs), "cases;", sum(1 for c in cs if c.get("ops") is not None and c.get("boxes")), "hand-derived;", selftest(), "reproduced by the reference;",
          max(len(L.encode(c)) for c in cs), "max stream bytes")
