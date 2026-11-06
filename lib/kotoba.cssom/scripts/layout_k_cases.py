"""Deterministic case grid of the layout slice (JUN-920, ADR-0287): hand-derived documents, the real component trees (real sheet and a
block sheet over the same trees), a seeded random grid, the bounds of both slices from each side and the refusals.

A case is a dict: name, rules [(origin, selector, [(property, value, important)])], doc (tag, id, classes, [children]), vw (the
viewport width as a Q6 raw, 1/64 px), status (the status the region modules must answer: 0, or the negative code of the refusal as a
positive number), ref (True when the host-native reference must run it), boxes (hand-derived expectations, one dict per element in
document order, or None), doch (hand-derived document height in px or None), raw (wire bytes overriding the encoding).
The wire form of the style slice is reused (style_k_cases.encode); the case blob handed to the guest is
[stream length:2 big endian][viewport:4 big endian][stream]. Nothing here is random at run time: the grid is a function of the sources."""
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import style_k_cases as K  # noqa: E402

T = K.T
WORDS = ["kind", "x", "y", "w", "h", "cw", "ch", "ml", "mr", "mt", "mb", "ct", "cb", "pt", "pr", "pb", "pl", "bt", "br", "bb", "bl", "rel"]
WORD = {n: i for i, n in enumerate(WORDS)}
Q = lambda px: int(round(px * 64))
FULL_MASK = sum(1 << i for i in range(1, 22)) | (1 << 22)       # words 1..21 and the document height
SUPPORTED = ["display", "width", "height", "min-width", "max-width", "box-sizing", "margin-top", "margin-right", "margin-bottom",
             "margin-left", "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-width", "border-right-width",
             "border-bottom-width", "border-left-width"]


def R(sel, **d):
    """An author rule with declarations given as keywords (underscores become hyphens); a value may be (value, important)."""
    return (1, sel, [(k.replace("_", "-"), (v[0] if isinstance(v, tuple) else v), (isinstance(v, tuple) and v[1])) for k, v in d.items()])


def encode(case):
    return K.encode(case)


def blob(case):
    s = encode(case)
    return struct.pack(">HI", len(s), case["vw"]) + s


def flat(doc):
    return K.flat(doc)


def hand_table(case):
    """(words, masks, docmask): the kernel table words the hand-derived boxes fix (22 per element), per element the bit mask of the compared words, and bit 22 when the document height is fixed."""
    n = len(flat(case["doc"]))
    words = [0] * (22 * n)
    masks = [0] * n
    for i, b in enumerate(case["boxes"]):
        kind = b.get("kind", 1)
        words[22 * i] = kind
        for k, v in b.items():
            if k != "kind":
                words[22 * i + WORD[k]] = Q(v)
                masks[i] |= 1 << WORD[k]
    return words, masks, ((1 << 22) if case.get("doch") is not None else 0)


def H(name, rules, doc, boxes, doch=None, vw=400, note=None):
    c = dict(name="hand-" + name, rules=rules, doc=doc, vw=Q(vw), status=0, ref=True, boxes=boxes, doch=doch)
    if note:
        c["note"] = note
    return c


def B(x, y, w, h, **more):
    d = dict(x=x, y=y, w=w, h=h)
    d.update(more)
    return d


def hand_cases():
    C = []
    add = C.append
    d = lambda *kids, cls="a": T("div", "", cls, *kids)
    # ---- 10.3.3 and the box model (one box) ----
    add(H("fixed-width", [R(".a", width="100px", height="30px")], d(), [B(0, 0, 100, 30, cw=100, ch=30, ml=0, mr=300)], 30))
    add(H("auto-width-fills", [R(".a", height="30px")], d(), [B(0, 0, 400, 30, cw=400, ml=0, mr=0)], 30))
    pads = dict(padding_top="5px", padding_right="10px", padding_bottom="5px", padding_left="10px")
    bords = dict(border_top_width="1px", border_right_width="2px", border_bottom_width="1px", border_left_width="2px")
    add(H("content-box", [R(".a", width="100px", height="20px", **pads, **bords)], d(),
          [B(0, 0, 124, 32, cw=100, ch=20, pt=5, pr=10, pb=5, pl=10, bt=1, br=2, bb=1, bl=2, ml=0, mr=276)], 32))
    add(H("border-box", [R(".a", width="100px", height="20px", box_sizing="border-box", **pads, **bords)], d(),
          [B(0, 0, 100, 20, cw=76, ch=8, ml=0, mr=300)], 20))
    add(H("auto-margins-centre", [R(".a", width="100px", height="10px", margin_left="auto", margin_right="auto")], d(),
          [B(150, 0, 100, 10, ml=150, mr=150)], 10))
    add(H("margin-left-auto", [R(".a", width="100px", height="10px", margin_left="auto")], d(), [B(300, 0, 100, 10, ml=300, mr=0)], 10))
    add(H("margin-right-auto", [R(".a", width="100px", height="10px", margin_right="auto")], d(), [B(0, 0, 100, 10, ml=0, mr=300)], 10))
    add(H("over-constrained-ltr", [R(".a", width="500px", height="10px", margin_left="10px")], d(), [B(10, 0, 500, 10, ml=10, mr=-110)], 10,
          note="CSS 2.1 10.3.3: the over-constrained margin-right is ignored and recomputed (ltr)"))
    add(H("margins-px", [R(".a", height="10px", margin_left="20px", margin_right="30px")], d(), [B(20, 0, 350, 10, cw=350)], 10))
    add(H("percent-width-margin", [R(".a", width="50%", height="10px", margin_left="10%")], d(), [B(40, 0, 200, 10, ml=40, mr=160)], 10))
    add(H("percent-padding-all-against-width", [R(".a", padding_left="10%", padding_top="5%")], d(),
          [B(0, 0, 400, 20, cw=360, pt=20, pl=40, ch=0)], 20, note="padding-top: 5% is 5% of the containing WIDTH (layout.cljk percentage-box-basis)"))
    add(H("min-width-wins", [R(".a", width="50px", min_width="100px", height="10px")], d(), [B(0, 0, 100, 10, cw=100)], 10))
    add(H("max-width-wins", [R(".a", width="300px", max_width="200px", height="10px")], d(), [B(0, 0, 200, 10, cw=200)], 10))
    add(H("max-width-percent-auto-width", [R(".a", max_width="25%", height="10px")], d(), [B(0, 0, 100, 10, mr=300)], 10))
    add(H("unitless-is-px", [R(".a", width="100", height="10")], d(), [B(0, 0, 100, 10)], 10, note="layout.cljk parse-int reads a bare number as px"))
    add(H("fractional-px", [R(".a", width="10.5px", height="0.25px")], d(), [B(0, 0, 10.5, 0.25, cw=10.5, ch=0.25)], 0.25))
    # ---- nesting ----
    inner = T("div", "", "i")
    add(H("nested-auto-in-padding", [R(".o", padding_top="10px", padding_right="10px", padding_bottom="10px", padding_left="10px"), R(".i", height="30px")],
          T("div", "", "o", inner), [B(0, 0, 400, 50, cw=380, ch=30), B(10, 10, 380, 30)], 50))
    add(H("nested-centre-in-fixed", [R(".o", width="300px"), R(".i", width="100px", height="20px", margin_left="auto", margin_right="auto")],
          T("div", "", "o", inner), [B(0, 0, 300, 20), B(100, 0, 100, 20)], 20))
    add(H("nested-percent-of-content-box", [R(".o", width="200px", padding_left="20px", padding_right="20px"), R(".i", width="50%", height="10px")],
          T("div", "", "o", inner), [B(0, 0, 240, 10, cw=200), B(20, 0, 100, 10)], 10, note="a percentage is of the parent CONTENT width"))
    add(H("three-deep-offsets", [R(".o", padding_left="5px", border_left_width="3px"), R(".m", margin_left="7px", padding_left="2px"), R(".i", height="9px")],
          T("div", "", "o", T("div", "", "m", inner)), [B(0, 0, 400, 9), B(15, 0, 385, 9, cw=383), B(17, 0, 383, 9)], 9))
    # ---- 8.3.1 margin collapsing ----
    sib = lambda a, b: T("div", "", "o", T("div", "", "a"), T("div", "", "b"))
    ab = lambda **k: [R(".a", height="10px", **k.get("a", {})), R(".b", height="10px", **k.get("b", {}))]
    add(H("siblings-collapse-max", ab(a=dict(margin_bottom="20px"), b=dict(margin_top="30px")), sib(0, 0),
          [B(0, 0, 400, 50), B(0, 0, 400, 10), B(0, 40, 400, 10)], 50))
    add(H("siblings-collapse-positive-and-negative", ab(a=dict(margin_bottom="20px"), b=dict(margin_top="-8px")), sib(0, 0),
          [B(0, 0, 400, 32), B(0, 0, 400, 10), B(0, 22, 400, 10)], 32, note="the largest positive plus the most negative: 20 - 8 = 12"))
    add(H("siblings-collapse-both-negative", ab(a=dict(margin_bottom="-10px"), b=dict(margin_top="-20px")), sib(0, 0),
          [B(0, 0, 400, 0), B(0, 0, 400, 10), B(0, -10, 400, 10)], 0, note="the most negative: -20"))
    add(H("siblings-three-margins", [R(".a", height="10px", margin_bottom="20px"), R(".b", height="0px", margin_top="5px", margin_bottom="-7px"), R(".c", height="10px", margin_top="12px")],
          T("div", "", "o", T("div", "", "a"), T("div", "", "b"), T("div", "", "c")),
          [B(0, 0, 400, 33), B(0, 0, 400, 10), B(0, 30, 400, 0), B(0, 23, 400, 10)], 33,
          note="the margins 20, 5, -7 and 12 adjoin: 20 + -7 = 13, so .c is at 10 + 13 = 23 (CSS 2.1 8.3.1 and the code agree). CODE vs CSS: the "
               "empty .b is placed at ht + (20 collapsed with 5) = 30, not at the collapsed-through position 23 (layout.cljk positions a self-collapsing box "
               "with the gap computed before its own bottom margin)"))
    add(H("parent-first-child-collapse", [R(".o", margin_top="10px"), R(".a", margin_top="15px", height="10px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 15, 400, 10), B(0, 15, 400, 10)], 25, note="10 and 15 collapse to 15, outside the parent"))
    add(H("parent-border-top-blocks", [R(".o", margin_top="10px", border_top_width="2px"), R(".a", margin_top="15px", height="10px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 10, 400, 27, bt=2), B(0, 27, 400, 10)], 37))
    add(H("parent-padding-top-blocks", [R(".o", margin_top="10px", padding_top="1px"), R(".a", margin_top="15px", height="10px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 10, 400, 26), B(0, 26, 400, 10)], 36))
    add(H("last-child-bottom-collapses-out", [R(".o", margin_bottom="10px"), R(".a", height="10px", margin_bottom="25px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 0, 400, 10, cb=25), B(0, 0, 400, 10)], 35))
    add(H("explicit-height-blocks-bottom-collapse", [R(".o", height="50px"), R(".a", height="10px", margin_bottom="25px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 0, 400, 50, cb=0), B(0, 0, 400, 10)], 50))
    add(H("border-bottom-blocks-both", [R(".o", border_bottom_width="1px"), R(".a", height="10px", margin_top="6px", margin_bottom="4px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 0, 400, 21, ct=0, cb=0), B(0, 6, 400, 10)], 21,
          note="layout.cljk fc-free? tests border-top AND border-bottom: a bottom border alone also stops the TOP margin collapsing"))
    add(H("flow-root-blocks-collapse", [R(".o", margin_top="10px", display="flow-root"), R(".a", margin_top="15px", height="10px")],
          T("div", "", "o", T("div", "", "a")), [B(0, 10, 400, 25), B(0, 25, 400, 10)], 35))
    # self-collapsing boxes: layout.cljk self-collapsing-block? and the measurements in its docstring (Brave 151)
    e14 = dict(margin_top="14px", margin_bottom="14px")
    add(H("empty-between-siblings", [R(".s", height="20px"), R(".e", **e14)], T("div", "", "o", T("div", "", "s"), T("div", "", "e"), T("div", "", "s")),
          [B(0, 0, 400, 54), B(0, 0, 400, 20), B(0, 34, 400, 0), B(0, 34, 400, 20)], 54,
          note="docstring of self-collapsing-block?: the empty box and the second sibling are BOTH at y=34"))
    add(H("empty-first-then-sibling", [R(".s", height="20px"), R(".e", **e14)], T("div", "", "o", T("div", "", "e"), T("div", "", "s")),
          [B(0, 0, 400, 20), B(0, 0, 400, 0), B(0, 0, 400, 20)], 20,
          note="CODE vs CSS 2.1 8.3.1: layout.cljk (layout-children-block, the `(and first? collapse-top?) mt*` arm) replaces the margin that escaped "
               "through a self-collapsing first child by the next child's margin, so the container sits at y=0 here; CSS puts it at y=14"))
    add(H("empty-with-padding-top", [R(".s", height="20px"), R(".e", padding_top="1px", **e14)], T("div", "", "o", T("div", "", "e"), T("div", "", "s")),
          [B(0, 14, 400, 35), B(0, 14, 400, 1), B(0, 29, 400, 20)], 49,
          note="docstring: padding-top 1px is not self-collapsing, 1px tall, the sibling follows 14px later (container-relative y=15)"))
    add(H("empty-with-border-top", [R(".s", height="20px"), R(".e", border_top_width="1px", **e14)], T("div", "", "o", T("div", "", "e"), T("div", "", "s")),
          [B(0, 14, 400, 35), B(0, 14, 400, 1), B(0, 29, 400, 20)], 49))
    add(H("empty-with-padding-left", [R(".s", height="20px"), R(".e", padding_left="5px", **e14)], T("div", "", "o", T("div", "", "s"), T("div", "", "e"), T("div", "", "s")),
          [B(0, 0, 400, 54), B(0, 0, 400, 20), B(0, 34, 400, 0, cw=395, pl=5), B(0, 34, 400, 20)], 54,
          note="docstring: a horizontal padding does not stop the box self-collapsing"))
    add(H("empty-chained", [R(".s", height="20px"), R(".e", **e14)],
          T("div", "", "o", T("div", "", "s"), T("div", "", "z", T("div", "", "e")), T("div", "", "s")),
          [B(0, 0, 400, 54), B(0, 0, 400, 20), B(0, 34, 400, 0), B(0, 34, 400, 0), B(0, 34, 400, 20)], 54,
          note="docstring: an empty box whose only child is another empty box is self-collapsing, chained"))
    # ---- display ----
    add(H("display-none-sibling", [R(".a", height="10px"), R(".n", display="none", height="50px", margin_top="40px")],
          T("div", "", "o", T("div", "", "a"), T("div", "", "n"), T("div", "", "a")), [B(0, 0, 400, 20), B(0, 0, 400, 10), dict(kind=0), B(0, 10, 400, 10)], 20))
    add(H("display-none-subtree-skipped", [R(".n", display="none"), R(".f", float="left", position="absolute", margin="5px")],
          T("div", "", "o", T("div", "", "n", T("div", "", "f"))), [B(0, 0, 400, 0), dict(kind=0), dict(kind=2)], 0,
          note="a refused property inside a display:none subtree is never read"))
    add(H("hidden-tag-has-no-box", [R(".a", height="10px")], T("div", "", "a", T("script"), T("div", "", "a")),
          [B(0, 0, 400, 10), dict(kind=0), B(0, 0, 400, 10)], 10, note="non-rendered-tags: script/style/meta/link/head/title/template"))
    add(H("display-block-explicit", [R(".a", display="block", height="5px")], d(), [B(0, 0, 400, 5)], 5))
    # ---- heights ----
    add(H("percent-height-of-definite-parent", [R(".o", height="200px"), R(".i", height="50%")], T("div", "", "o", inner), [B(0, 0, 400, 200), B(0, 0, 400, 100)], 200))
    add(H("percent-height-of-auto-parent", [R(".i", height="50%")], T("div", "", "o", inner), [B(0, 0, 400, 0), B(0, 0, 400, 0)], 0,
          note="layout.cljk percentage-of: an indefinite basis makes the percentage `auto`"))
    add(H("percent-height-content-box-parent", [R(".o", height="200px", padding_top="10px", padding_bottom="10px"), R(".i", height="50%")],
          T("div", "", "o", inner), [B(0, 0, 400, 220, ch=200), B(0, 10, 400, 100)], 220))
    add(H("height-border-box", [R(".a", height="40px", box_sizing="border-box", padding_top="5px", padding_bottom="5px", border_top_width="1px")], d(),
          [B(0, 0, 400, 40, ch=29)], 40))
    add(H("content-height-from-children", [R(".o", padding_top="3px", padding_bottom="4px"), R(".a", height="10px", margin_top="6px", margin_bottom="8px")],
          T("div", "", "o", T("div", "", "a"), T("div", "", "a")), [B(0, 0, 400, 49), B(0, 9, 400, 10), B(0, 27, 400, 10)], 49,
          note="padding stops the parent/child collapse; the siblings' 8 and 6 collapse to 8; the last margin (8) stays inside (padding-bottom)"))
    add(H("viewport-width-changes-percent", [R(".a", width="25%", height="1px")], d(), [B(0, 0, 100, 1)], 1, vw=400))
    add(H("viewport-width-800", [R(".a", width="25%", height="1px")], d(), [B(0, 0, 200, 1)], 1, vw=800))
    return C


def hand_fix(C):
    """Cases whose hand-derived numbers are written next to the rule that decides them; the derivation of the dependent ones is below."""
    return C


def refusal_cases():
    C = []

    def no(name, code, rules, doc, vw=400, ref=True, **kw):
        C.append(dict(name="refuse-" + name, rules=rules, doc=doc, vw=Q(vw), status=code, ref=ref, boxes=None, doch=None, **kw))
    a = lambda **k: [R(".a", **k)]
    one = T("div", "", "a")
    # -14: display / inline-level tags
    no("tag-span", 14, [], T("div", "", "", T("span")))
    no("tag-label", 14, [], T("label"))
    no("display-inline", 14, a(display="inline"), one)
    no("display-flex", 14, a(display="flex"), one)
    no("display-inline-block", 14, a(display="inline-block"), one)
    no("display-grid", 14, a(display="grid"), one)
    no("display-table", 14, a(display="table"), one)
    no("display-list-item", 14, a(display="list-item"), one)
    no("display-contents", 14, a(display="contents"), one)
    no("display-inline-on-second-child", 14, [R(".n", display="inline")], T("div", "", "", T("div"), T("div", "", "n")))
    # -15: a property outside the slice
    for name, decl in (("float", dict(float="left")), ("clear", dict(clear="both")), ("position", dict(position="absolute")),
                       ("position-static", dict(position="static")), ("overflow", dict(overflow="hidden")), ("overflow-x", dict(overflow_x="auto")),
                       ("aspect-ratio", dict(aspect_ratio="1")), ("columns", dict(columns="2")), ("writing-mode", dict(writing_mode="vertical-rl")),
                       ("direction", dict(direction="rtl")), ("min-height", dict(min_height="5px")), ("max-height", dict(max_height="5px")),
                       ("shorthand-margin", dict(margin="0")), ("shorthand-padding", dict(padding="4px")), ("shorthand-border", dict(border="1px")),
                       ("border-width", dict(border_width="1px")), ("border-style", dict(border_style="solid")), ("border-top-style", dict(border_top_style="none")),
                       ("border-left", dict(border_left="1px solid"))):
        no("prop-" + name, 15, a(**decl), one)
    no("prop-inherited-direction-reaches-child", 15, [R(".o", direction="ltr")], T("div", "", "o", T("div")))
    no("prop-display-before-property", 14, a(display="flex", float="left"), one, note="the display check comes first")
    # -16: outside the grammar
    for name, decl in (("width-calc", dict(width="calc(10px + 5px)")), ("width-min-content", dict(width="min-content")), ("width-em", dict(width="2em")),
                       ("width-garbage", dict(width="10px 20px")), ("margin-top-em", dict(margin_top="1em")), ("padding-left-auto", dict(padding_left="auto")),
                       ("border-width-percent", dict(border_top_width="50%")), ("border-width-thin", dict(border_top_width="thin")),
                       ("min-width-auto", dict(min_width="auto")), ("max-width-auto", dict(max_width="auto")), ("height-none", dict(height="none")),
                       ("width-none", dict(width="none")), ("box-sizing-padding", dict(box_sizing="padding-box")), ("width-ten-digits", dict(width="1234567890px")),
                       ("width-trailing", dict(width="10pxx")), ("width-dot", dict(width=".")), ("width-sign-only", dict(width="-"))):
        no("grammar-" + name, 16, a(**decl), one)
    # -17: range or sign
    for name, decl in (("negative-width", dict(width="-10px")), ("negative-height", dict(height="-1px")), ("negative-padding", dict(padding_left="-5px")),
                       ("negative-padding-top", dict(padding_top="-1px")), ("negative-border", dict(border_left_width="-1px")),
                       ("negative-percent-padding", dict(padding_top="-5%")), ("negative-min-width", dict(min_width="-1px")),
                       ("width-2097152px", dict(width="2097152px")), ("margin-2097152px", dict(margin_left="2097152px")),
                       ("percent-65536", dict(width="655.36%")), ("negative-percent-height-of-definite-parent", dict(height="-10%"))):
        if name == "negative-percent-height-of-definite-parent":
            no("range-" + name, 17, [R(".o", height="100px"), R(".a", **decl)], T("div", "", "o", one))
        else:
            no("range-" + name, 17, a(**decl), one)
    # -18: geometry beyond +-2^30
    no("geometry-nine-big-siblings", 18, [R(".s", height="2000000px")], T("div", "", "", *[T("div", "", "s") for _ in range(9)]))
    no("geometry-explicit-border-box-heights", 18, [R(".a", height="2097151px", padding_top="2097151px", padding_bottom="2097151px", border_top_width="2097151px",
                                                         border_bottom_width="2097151px")], T("div", "", "", one, one),
       note="each box is 10485755 px (5 x 2097151) tall, two of them pass 2^30 Q6 raw")
    no("geometry-margin-pushes-y", 18, [R(".o", height="1px"), R(".a", margin_top="2097151px", height="1px")],
       T("div", "", "o", *[T("div", "", "a") for _ in range(9)]))
    # sheet-level refusals pass through
    no("sheet-attribute-selector", 12, [(1, "a[href]", [("width", "1px", False)])], T("a"))
    no("sheet-wide-keyword", 13, [(1, "a", [("width", "inherit", False)])], T("a"))
    no("sheet-repeated-property", 1, [(1, "a", [("width", "1px", False), ("width", "2px", False)])], T("a"))
    return C


def bound_cases():
    C = []
    wide = lambda n: ("div", "", "", [("div", "", "a", []) for _ in range(n - 1)])
    h1 = [R(".a", height="1px")]
    add = lambda name, rules, doc, status, vw=400, ref=True, **kw: C.append(dict(name="bound-" + name, rules=rules, doc=doc, vw=Q(vw) if vw < 2 ** 20 else vw,
                                                                                    status=status, ref=ref, boxes=None, doch=None, **kw))
    add("elements-128-at", h1, wide(128), 0)
    add("elements-128-past", h1, wide(129), 3, ref=False)
    add("depth-32-at", [R("div", height="1px")], K.chain(32), 0)
    add("depth-32-past", [R("div", height="1px")], K.chain(33), 11, ref=False)
    # the nested chain with a padding at every level (x and the width shrink with the depth)
    add("depth-32-padding", [R("div", padding_left="1px", padding_top="1px")], K.chain(32), 0)
    names16 = SUPPORTED[:15] + ["color"]
    add("properties-16-at", [(1, "div", [(p, "inherit-me" if p == "color" else v, False) for p, v in
                                         zip(names16, ["block", "300px", "10px", "1px", "400px", "content-box", "1px", "1px", "1px", "1px", "1px", "1px", "1px", "1px", "1px", "red"])])],
        ("div", "", "", []), 0)
    add("properties-17-past", [(1, "div", [(p, "1px", False) for p in SUPPORTED[1:5] + SUPPORTED[6:] + ["color"]])], ("div", "", "", []), 10, ref=False)
    # viewport and slot bounds
    one = ("div", "", "a", [])
    add("viewport-2^30-at", [R(".a", height="1px")], one, 0, vw=1073741824)
    add("viewport-2^30-past", [R(".a", height="1px")], one, 19, vw=1073741825, ref=False)
    add("viewport-zero", [R(".a", height="1px")], one, 0, vw=0)
    add("slot-2097151px-at", [R(".a", width="2097151px", height="1px")], one, 0)
    add("slot-2097152px-past", [R(".a", width="2097152px", height="1px")], one, 17)
    add("percent-65535-at", [R(".a", width="655.35%", height="1px")], one, 0)
    add("geometry-eight-big-siblings-at", [R(".s", height="2000000px")], ("div", "", "", [("div", "", "s", []) for _ in range(8)]), 0)
    add("geometry-nine-big-siblings-past", [R(".s", height="2000000px")], ("div", "", "", [("div", "", "s", []) for _ in range(9)]), 18)
    add("integer-part-9-digits-slot-range", [R(".a", width="123456789px", height="1px")], one, 17)
    add("integer-part-8-digits-slot-range", [R(".a", width="16777215px", height="1px")], one, 17)
    return C


def block_sheet(doc, seed):
    """A block-only sheet over the classes a tree uses (deterministic per class): every element is a block, boxes get margins,
    paddings, borders and sometimes a width or height, so real tree shapes are laid out."""
    classes = []

    def go(n):
        for c in (n[2] or "").split(" "):
            if c and c not in classes:
                classes.append(c)
        for k in n[3]:
            go(k)
    go(doc)
    rng = random.Random(seed)
    rules = [(1, "*", [("display", "block", False)])]
    for c in classes:
        r = random.Random("%s/%s" % (seed, c))
        d = []
        if r.random() < 0.5:
            d.append(("padding-top", r.choice(["2px", "6px", "12px"]), False))
            d.append(("padding-bottom", r.choice(["2px", "6px", "0px"]), False))
        if r.random() < 0.5:
            d.append(("padding-left", r.choice(["4px", "12px", "2%"]), False))
        if r.random() < 0.4:
            d.append(("margin-top", r.choice(["0px", "4px", "8px", "-3px"]), False))
            d.append(("margin-bottom", r.choice(["0px", "6px", "10px"]), False))
        if r.random() < 0.3:
            d.append(("border-top-width", r.choice(["1px", "2px"]), False))
        if r.random() < 0.25:
            d.append(("width", r.choice(["50%", "200px", "120px"]), False))
            d.append(("margin-left", "auto", False))
        if r.random() < 0.3:
            d.append(("height", r.choice(["20px", "14px"]), False))
        if d:
            rules.append((1, "." + c, d))
    del rng
    return rules


def real_cases():
    C = []
    rules, _ = K.real_sheet()
    docs = K.component_docs()
    for k, doc in enumerate(docs):
        C.append(dict(name="component-%02d" % k, rules=rules, doc=doc, vw=Q(480), status=None, ref=True, boxes=None, doch=None))
    for k, doc in enumerate(docs):
        C.append(dict(name="component-block-%02d" % k, rules=block_sheet(doc, k), doc=doc, vw=Q(480), status=None, ref=True, boxes=None, doch=None))
    return C


# ---- random grid ----
PX = ["0px", "1px", "3px", "7px", "10px", "12.5px", "20px", "33.25px", "0.5px", "100px", "250px"]
SIGNED = PX + ["-4px", "-10px", "-0.5px"]
PCT = ["10%", "25%", "33.33%", "50%", "12.5%", "100%", "0%"]


def rand_box_rules(rng, classes):
    """Rules over the classes with at most 16 distinct property names in the whole sheet."""
    names = rng.sample([s for s in SUPPORTED if s != "display"], rng.randint(5, 15)) + ["display"]
    rules = []
    if rng.random() < 0.8:
        rules.append((1, "*", [("display", "block", False)]))
    for c in classes:
        d = []
        for p in rng.sample(names, rng.randint(1, min(8, len(names)))):
            if p == "display":
                v = rng.choice(["block", "block", "block", "none", "flow-root"]) if rng.random() < 0.3 else "block"
            elif p == "box-sizing":
                v = rng.choice(["border-box", "content-box"])
            elif p in ("width", "min-width", "max-width"):
                v = rng.choice(PX + PCT + (["auto"] if p == "width" else []) + (["none"] if p == "max-width" else []))
            elif p == "height":
                v = rng.choice(PX + PCT + ["auto"])
            elif p.startswith("margin"):
                v = rng.choice(SIGNED + PCT + ["auto"])
            elif p.startswith("padding"):
                v = rng.choice(PX + PCT)
            else:
                v = rng.choice(["0px", "1px", "2px", "3.5px"])
            d.append((p, v, False))
        rules.append((1, "." + c, d))
    return rules


def random_cases(seed, n):
    rng = random.Random(seed)
    out = []
    classes = ["c%d" % i for i in range(6)]
    for i in range(n):
        doc = K.rand_doc(rng, rng.choice([6, 12, 24, 48]), rng.choice([3, 5, 9]))
        # the generator draws its classes from the style grid's list; map them to this grid's
        def remap(nd):
            cl = " ".join(sorted(set(rng.choice(classes) for _ in range(rng.randint(0, 2)))))
            return ("div", "", cl, [remap(k) for k in nd[3]])
        doc = remap(doc)
        out.append(dict(name="random-%03d" % i, rules=rand_box_rules(rng, classes), doc=doc, vw=rng.choice([Q(320), Q(480), Q(800), Q(1000.5), 25600 + 7]),
                        status=None, ref=True, boxes=None, doch=None))
    return out


def all_cases(seed=20261106, n_random=110):
    cases = hand_cases() + refusal_cases() + bound_cases() + real_cases() + random_cases(seed, n_random)
    assert len(cases) <= 480, len(cases)
    names = [c["name"] for c in cases]
    assert len(set(names)) == len(names)
    return cases


if __name__ == "__main__":
    cs = all_cases()
    print(len(cs), "cases;", sum(1 for c in cs if c.get("boxes")), "hand-derived;", max(len(encode(c)) for c in cs), "max stream bytes")
