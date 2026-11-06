"""Deterministic case grid of the style slice (JUN-920, ADR-0287): data model, wire encoding, the digest, hand-derived
expected styles, the real component trees and sheet, a seeded random grid and the capacity cases.

A case is a dict: name, rules [(origin, selector, [(property, value, important)])], doc (tag, id, classes, [children]),
status (the expected status of the region modules: 0 or the code that refuses), ref (True when the host-native reference
must agree), styles (hand-derived computed style per element in document order, or None), raw (wire bytes overriding the
encoding, for malformed streams). Nothing here is random at run time: the grid is a function of the checked-in sources."""
import html.parser
import random
import re
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
HTML_TEST = LIB / "kotoba.html/test/native/ui_components_test.kotoba"
SHEET_SRC = LIB / "kotoba.css/kotoba/ui_components_sheet.kotoba"

# ---- bounds (README table) ----
NODE_MAX, DEPTH_MAX, CLASS_NODE_MAX, CLASS_COMPOUND_MAX = 128, 32, 8, 4
COMPOUND_SEL_MAX, SEL_MAX, COMPOUND_MAX, DECL_MAX, PROP_MAX = 8, 128, 256, 512, 16
STR_MAX, POOL_MAX, INPUT_MAX = 511, 4096, 16384

INHERITED = ("color font font-family font-size font-style font-weight font-variant font-stretch line-height letter-spacing "
             "word-spacing text-align text-indent text-transform text-shadow white-space word-break overflow-wrap word-wrap "
             "tab-size hyphens direction visibility cursor quotes list-style list-style-type list-style-position "
             "list-style-image border-collapse border-spacing caption-side empty-cells orphans widows writing-mode "
             "text-orientation").split()


# ---- wire encoding (README) ----
def u8(n):
    assert 0 <= n < 256, n
    return bytes([n])


def enc_sheet(rules):
    out = b""
    for origin, sel, decls in rules:
        sb = sel.encode()
        out += b"R" + u8(origin) + u8(len(sb)) + sb + u8(len(decls))
        for p, v, imp in decls:
            pb, vb = p.encode(), v.encode()
            out += u8(len(pb)) + pb + u8(len(vb)) + vb + u8(1 if imp else 0)
    return out + b"\x00"


def enc_doc(node):
    out = bytearray()

    def go(n):
        tag, idv, cls, kids = n
        tb, ib, cb = tag.encode(), (idv or "").encode(), (cls or "").encode()
        out.extend(b"E" + u8(len(tb)) + tb + u8(len(ib)) + ib + u8(len(cb)) + cb)
        for k in kids:
            go(k)
        out.extend(b"/")
    if node is not None:
        go(node)
    return bytes(out) + b"\x00"


def encode(case):
    return case["raw"] if case.get("raw") is not None else enc_sheet(case["rules"]) + enc_doc(case["doc"])


def flat(doc):
    """Elements in document order as (tag, id, classes, parent index, previous sibling index)."""
    out = []

    def go(n, parent, prev):
        i = len(out)
        out.append((n[0], n[1] or "", n[2] or "", parent, prev))
        p = -1
        for k in n[3]:
            p = go(k, i, p)
        return i
    if doc is not None:
        go(doc, -1, -1)
    return out


# ---- the digest (cascade_k header) ----
def pair_hash(name, value):
    h = 5381
    for b in (name + ":" + value).encode():
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    return h


def case_sum(styles):
    return sum((i + 1) * (sum(pair_hash(k, v) for k, v in st.items()) & 0xFFFFFFFF) for i, st in enumerate(styles))


# ---- reference EDN ----
def edn_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def edn_doc(n):
    if n is None:
        return "[]"
    return "[%s %s %s [%s]]" % (edn_str(n[0]), edn_str(n[1] or ""), edn_str(n[2] or ""), " ".join(edn_doc(k) for k in n[3]))


def edn_case(case):
    rules = " ".join("[%d %s [%s]]" % (o, edn_str(s), " ".join("[%s %s %d]" % (edn_str(p), edn_str(v), 1 if i else 0) for p, v, i in d))
                     for o, s, d in case["rules"])
    return "{:sheet [%s] :doc %s}" % (rules, edn_doc(case["doc"]))


# ---- the real sheet (ui_components_sheet.kotoba) ----
UNITLESS = set("animation-iteration-count border-image-outset border-image-slice border-image-width box-flex box-flex-group "
               "box-ordinal-group column-count columns flex flex-grow flex-positive flex-shrink flex-negative flex-order "
               "grid-column grid-row font-weight line-clamp line-height opacity order orphans scale tab-size widows z-index "
               "zoom".split())


def edn_parse(text):
    pos = 0

    def ws():
        nonlocal pos
        while pos < len(text) and text[pos] in " \t\n,":
            pos += 1

    def rd():
        nonlocal pos
        ws()
        c = text[pos]
        if c == "[" or c == "{":
            close = "]" if c == "[" else "}"
            pos += 1
            items = []
            while True:
                ws()
                if text[pos] == close:
                    pos += 1
                    break
                items.append(rd())
            if c == "[":
                return items
            return list(zip(items[0::2], items[1::2]))      # map as ordered pairs
        if c == '"':
            pos += 1
            s = ""
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    s += {"n": "\n", "t": "\t"}.get(text[pos], text[pos])
                else:
                    s += text[pos]
                pos += 1
            pos += 1
            return s
        m = re.compile(r"[^\s,\[\]{}\"]+").match(text, pos)
        pos = m.end()
        tok = m.group(0)
        if tok.startswith(":"):
            return ("kw", tok[1:])
        return int(tok)
    return rd()


def render_value(prop, v):
    if isinstance(v, str):
        return v
    if isinstance(v, tuple):
        return v[1]
    return str(v) if (v == 0 or prop in UNITLESS) else "%dpx" % v


def real_sheet():
    """(rules, css_text): the author sheet of the components, values rendered as css_sheet.kotoba renders them."""
    src = SHEET_SRC.read_text()
    lits = re.findall(r'\(document-edn-read "((?:[^"\\]|\\.)*)"\)', src)
    edn = lits[0].replace('\\"', '"').replace("\\\\", "\\")
    rules = []
    for sel, decls in edn_parse(edn):
        rules.append((1, sel, [(k[1], render_value(k[1], v), False) for k, v in decls]))
    text = "\n".join("%s { %s }" % (sel, " ".join("%s: %s;" % (p, v) for p, v, _ in d)) for _, sel, d in rules)
    return rules, text


# ---- the real component trees: the expected strings of ui_components_test.kotoba ----
VOID = {"meta", "input", "img", "br", "hr", "link", "area", "base", "col", "embed"}


class _P(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.roots = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = [tag, a.get("id") or "", a.get("class") or "", []]
        (self.stack[-1][3] if self.stack else self.roots).append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()


def freeze(n):
    return (n[0], n[1], n[2], [freeze(k) for k in n[3]])


def component_docs():
    src = HTML_TEST.read_text()
    out = []
    for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', src):
        if not lit.startswith("<"):
            continue
        text = bytes(lit, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in lit else lit
        text = lit.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        p = _P()
        p.feed(text)
        roots = [freeze(r) for r in p.roots]
        if not roots:
            continue
        out.append(roots[0] if len(roots) == 1 else ("div", "", "", roots))      # fragments get a synthetic div root
    return out


# ---- hand-derived cases (expected styles written out from the CSS rules and from core.cljk) ----
def T(tag, idv="", cls="", *kids):
    return (tag, idv, cls, list(kids))


def hand_cases():
    H = []

    def add(name, rules, doc, styles, **kw):
        H.append(dict(name=name, rules=rules, doc=doc, styles=styles, status=0, ref=True, **kw))
    r1 = lambda sel, *d: (1, sel, [(p, v, imp) for p, v, imp in d])
    c = lambda p, v, imp=False: (p, v, imp)
    # core_test.cljk matches-adjacent-and-general-sibling-combinators: section > h1, p1, span, p2
    sec = T("section", "", "", T("h1"), T("p"), T("span"), T("p"))
    add("adjacent-and-general-sibling", [r1("h1 + p", c("color", "red")), r1("h1 ~ p", c("border-width", "1px"))], sec,
        [{}, {}, {"color": "red", "border-width": "1px"}, {}, {"border-width": "1px"}])
    # specificity-still-decides-ties (core_test 1807): div {color:red} #hero {color:blue} -> blue
    hero = T("div", "hero")
    add("id-beats-tag", [r1("div", c("color", "red")), r1("#hero", c("color", "blue"))], hero, [{"color": "blue"}])
    add("id-beats-tag-reversed-order", [r1("#hero", c("color", "blue")), r1("div", c("color", "red"))], hero, [{"color": "blue"}])
    # same with !important on both (core_test 1887): still blue
    add("important-ties-by-specificity", [r1("div", c("color", "red", True)), r1("#hero", c("color", "blue", True))], hero, [{"color": "blue"}])
    add("important-beats-specificity", [r1("div", c("color", "red", True)), r1("#hero", c("color", "blue"))], hero, [{"color": "red"}])
    add("author-beats-user-agent", [(0, "p", [("color", "black", False)]), (1, "p", [("color", "red", False)])], T("p"), [{"color": "red"}])
    add("author-beats-user-agent-reversed", [(1, "p", [("color", "red", False)]), (0, "p", [("color", "black", False)])], T("p"), [{"color": "red"}])
    add("author-normal-beats-ua-higher-specificity", [(0, "div p", [("color", "black", False)]), (1, "p", [("color", "red", False)])], T("div", "", "", T("p")), [{}, {"color": "red"}])
    add("class-beats-two-tags", [r1("div p", c("color", "red")), r1(".a", c("color", "blue"))], T("div", "", "", T("p", "", "a")), [{}, {"color": "blue"}])
    add("two-tags-beat-nothing-but-class-wins-order", [r1(".a", c("color", "blue")), r1("p.a", c("color", "green")), r1("div p", c("color", "red"))], T("div", "", "", T("p", "", "a")), [{}, {"color": "green"}])
    add("source-order-breaks-tie", [r1(".a", c("color", "red")), r1(".b", c("color", "blue"))], T("p", "", "a b"), [{"color": "blue"}])
    add("source-order-breaks-tie-reversed", [r1(".b", c("color", "blue")), r1(".a", c("color", "red"))], T("p", "", "a b"), [{"color": "red"}])
    add("selector-list-each-own-specificity", [r1("div, .x", c("color", "red")), r1(".y", c("color", "blue"))], T("div", "", "x"), [{"color": "red"}])
    add("selector-list-loses-to-later-equal", [r1(".x, div", c("color", "red")), r1(".y", c("color", "blue"))], T("div", "", "x y"), [{"color": "blue"}])
    # inheritance: color inherits, padding does not, font-size inherits through a middle element that sets nothing
    add("inheritance", [r1(".root", c("color", "red"), c("padding", "4px"), c("font-size", "12px")), r1("span", c("color", "blue"))],
        T("div", "", "root", T("p", "", "", T("b")), T("span", "", "", T("i"))),
        [{"color": "red", "padding": "4px", "font-size": "12px"}, {"color": "red", "font-size": "12px"}, {"color": "red", "font-size": "12px"},
         {"color": "blue", "font-size": "12px"}, {"color": "blue", "font-size": "12px"}])
    add("non-inherited-property-stays-absent", [r1("div", c("display", "flex"), c("cursor", "pointer"))], T("div", "", "", T("p")),
        [{"display": "flex", "cursor": "pointer"}, {"cursor": "pointer"}])
    # backtracking: .a > .b span, the nearest .b has a .b parent, the farther one has the .a parent
    add("child-needs-backtracking", [r1(".a > .b span", c("color", "red"))], T("div", "", "a", T("div", "", "b", T("div", "", "b", T("span")))),
        [{}, {}, {}, {"color": "red"}])
    add("child-does-not-match-grandchild", [r1(".a > span", c("color", "red"))], T("div", "", "a", T("div", "", "", T("span"))), [{}, {}, {}])
    add("descendant-any-depth", [r1(".a span", c("color", "red"))], T("div", "", "a", T("div", "", "", T("p", "", "", T("span")))), [{}, {}, {}, {"color": "red"}])
    add("adjacent-does-not-reach-second", [r1("h1 + p", c("color", "red"))], T("div", "", "", T("h1"), T("p"), T("p")), [{}, {}, {"color": "red"}, {}])
    add("sibling-chain", [r1("h1 + p ~ span", c("color", "red"))], T("div", "", "", T("h1"), T("p"), T("i"), T("span")), [{}, {}, {}, {}, {"color": "red"}])
    add("universal-has-zero-specificity", [r1("*", c("color", "red")), r1("p", c("color", "blue"))], T("p"), [{"color": "blue"}])
    add("universal-loses-order-only-at-zero", [r1("p", c("color", "blue")), r1("*", c("color", "red"))], T("p"), [{"color": "blue"}])
    add("selector-tag-case-folds", [r1("DIV", c("color", "red"))], T("div"), [{"color": "red"}])
    # code beats spec: only the first #id of a compound counts (core.cljk parse-simple-selector: (first ids))
    add("first-id-only-matches", [r1("#a#b", c("color", "red"))], T("div", "a"), [{"color": "red"}], codeVsSpec="#a#b matches id=a because only the first id is kept")
    add("first-id-only-specificity-one-id", [r1("#a#b", c("color", "red")), r1("#a.c.d", c("color", "blue"))], T("div", "a", "c d"), [{"color": "blue"}],
        codeVsSpec="#a#b is one id in core.cljk (two in CSS Selectors 4), so the one-id plus two-classes rule wins here as in the code")
    add("repeated-class-counts-twice", [r1(".a.a", c("color", "red")), r1(".a.b", c("color", "blue"))], T("p", "", "a b"), [{"color": "blue"}])
    add("repeated-class-beats-two-tags", [r1(".a.a", c("color", "red")), r1("div p", c("color", "blue"))], T("div", "", "", T("p", "", "a")), [{}, {"color": "red"}])
    add("class-set-collapses-repeats", [r1(".a", c("color", "red"))], T("p", "", "a a  a"), [{"color": "red"}])
    add("empty-sheet", [], T("p"), [{}])
    add("rule-without-declarations", [r1("p")], T("p"), [{}])
    add("user-agent-sheet-inherits", [(0, "a", [("color", "blue", False), ("cursor", "pointer", False)])], T("a", "", "", T("b")), [{"color": "blue", "cursor": "pointer"}, {"color": "blue", "cursor": "pointer"}])
    add("inherit-then-override-by-author", [(0, "a", [("color", "blue", False)]), (1, ".x", [("color", "red", False)])], T("a", "", "", T("b", "", "x", T("i"))),
        [{"color": "blue"}, {"color": "red"}, {"color": "red"}])
    return H


def refusal_cases():
    R = []
    one = lambda sel, d=(("color", "red", False),): [(1, sel, list(d))]
    for name, sel in (("attribute", "a[href]"), ("pseudo-class", "a:hover"), ("pseudo-element", "p::before"), ("leading-combinator", "> a"),
                      ("trailing-combinator", "a >"), ("double-combinator", "a > > b"), ("digit-class", ".1a"), ("bare-dot", "."),
                      ("bare-hash", "#"), ("escape", ".a\\:b"), ("non-ascii", ".café"), ("star-in-middle", "a*b"),
                      ("namespace", "svg|a"), ("paren", ":not(.a)"), ("amp", "&.a"), ("percent", "a%")):
        # the host reference cannot scan a non-ASCII string: string-length counts bytes there while string-code-point-at indexes code points
        R.append(dict(name="refuse-selector-" + name, rules=one(sel), doc=T("a"), styles=None, status=12, ref=(name != "non-ascii")))
    for v in ("inherit", "INITIAL", "unset", "Revert", "revert-layer"):
        R.append(dict(name="refuse-value-" + v.lower(), rules=one("a", (("color", v, False),)), doc=T("a"), styles=None, status=13, ref=True))
    R.append(dict(name="refuse-repeated-property", rules=[(1, "a", [("color", "red", False), ("color", "blue", False)])], doc=T("a"), styles=None, status=1, ref=True))
    # a value that only looks like a keyword is not one
    R.append(dict(name="value-containing-inherit-is-fine", rules=one("a", (("content", "inherit-me", False),)), doc=T("a"), styles=[{"content": "inherit-me"}], status=0, ref=True))
    return R


def malformed_cases():
    s = enc_sheet([(1, "a", [("color", "red", False)])])
    d = enc_doc(T("a", "", "", T("b")))
    M = []

    def add(name, raw):
        M.append(dict(name="malformed-" + name, rules=[], doc=None, styles=None, status=1, ref=False, raw=raw))
    add("sheet-not-terminated", s[:-1] + b"E")
    add("unknown-sheet-op", b"X\x00")
    add("origin-two", b"R\x02\x01a\x00\x00" + d)
    add("truncated-declaration", b"R\x01\x01a\x01\x05color\x03re")
    add("zero-length-value", b"R\x01\x01a\x01\x05color\x00\x00\x00" + d)
    add("importance-flag-two", b"R\x01\x01a\x01\x05color\x03red\x02\x00" + d)
    add("unclosed-element", s + b"E\x01a\x00\x00")
    add("close-at-depth-zero", s + b"/\x00")
    add("second-root", s + enc_doc(T("a"))[:-1] + enc_doc(T("b")))
    add("unknown-doc-op", s + b"Z\x00")
    add("truncated-element", s + b"E\x05ab")
    add("zero-length-tag", s + b"E\x00\x00\x00/\x00")
    add("missing-final-zero", s + d[:-1])
    add("trailing-bytes", s + d + b"\x00")
    return M


# ---- random grid ----
TAGS = ["div", "p", "span", "a", "ul", "li", "h1", "section", "nav", "button"]
IDS = ["x1", "x2", "x3", "x4"]
CLS = ["a", "b", "c", "d", "e", "f"]
PROPS = [("color", ["red", "blue", "#111111", "green"]), ("font-size", ["12px", "14", "1em"]), ("font-weight", ["700", "400"]),
         ("line-height", ["1.2", "20px"]), ("text-align", ["left", "center"]), ("cursor", ["pointer", "default"]),
         ("visibility", ["hidden", "visible"]), ("display", ["flex", "block", "none"]), ("padding", ["4px", "6px 12px", "0"]),
         ("margin", ["0", "8px"]), ("background", ["#fff", "#e4e8ef"]), ("border", ["0", "1px solid"])]


def rand_doc(rng, n_target, depth_max):
    count = [0]

    def node(depth):
        count[0] += 1
        tag = rng.choice(TAGS)
        idv = rng.choice(IDS) if rng.random() < 0.15 else ""
        cls = " ".join(rng.sample(CLS, rng.randint(0, 3)))
        kids = []
        if depth < depth_max:
            for _ in range(rng.randint(0, 3)):
                if count[0] < n_target:
                    kids.append(node(depth + 1))
        return (tag, idv, cls, kids)
    return node(0)


def rand_compound(rng):
    s = ""
    r = rng.random()
    if r < 0.45:
        s += rng.choice(TAGS)
    elif r < 0.55:
        s += "*"
    if rng.random() < 0.1:
        s += "#" + rng.choice(IDS)
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        s += "." + rng.choice(CLS)
    return s if s else "." + rng.choice(CLS)


def rand_selector(rng):
    n = rng.choice([1, 1, 1, 2, 2, 3, 4])
    s = rand_compound(rng)
    for _ in range(n - 1):
        s += rng.choice([" ", " ", " > ", " + ", " ~ "]) + rand_compound(rng)
    return s


def rand_rules(rng, n_rules):
    rules = []
    for _ in range(n_rules):
        sel = rand_selector(rng)
        if rng.random() < 0.2:
            sel += ", " + rand_selector(rng)
        props = rng.sample(PROPS, rng.randint(1, 4))
        rules.append((rng.choice([0, 1, 1, 1]), sel, [(p, rng.choice(vs), rng.random() < 0.12) for p, vs in props]))
    return rules


def random_cases(seed, n):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        doc = rand_doc(rng, rng.choice([6, 12, 24, 40]), rng.choice([3, 5, 8]))
        out.append(dict(name="random-%03d" % i, rules=rand_rules(rng, rng.choice([3, 6, 10, 14])), doc=doc, styles=None, status=0, ref=True))
    return out


# ---- capacity cases: each bound is hit from both sides (at the bound it runs and the reference agrees; one past it is refused) ----
def chain(n, tag="div"):
    node = (tag, "", "", [])
    for _ in range(n - 1):
        node = (tag, "", "", [node])
    return node


def interned(case):
    """The distinct byte strings the region modules intern for a case, in order (selector tags lower-cased)."""
    seen = []
    add = lambda x: seen.append(x) if x and x not in seen else None
    for _, sel, decls in case["rules"]:
        for p, v, _i in decls:
            add(p)
            add(v)
        for item in sel.split(","):
            for tok in re.split(r"[ >+~]+", item.strip()):
                m = re.match(r"([A-Za-z][A-Za-z0-9_-]*)?", tok)
                if m.group(1):
                    add(m.group(1).lower())
                for k in re.findall(r"[#.]([A-Za-z_][A-Za-z0-9_-]*)", tok):
                    add(k)
    for tag, idv, cls, _k in (flat_nodes(case["doc"]) if case["doc"] else []):
        add(tag)
        add(idv)
        for c in (cls or "").split(" "):
            add(c)
    return seen


def flat_nodes(doc):
    out = [(doc[0], doc[1], doc[2], doc[3])]
    for k in doc[3]:
        out += flat_nodes(k)
    return out


def sized_input(target):
    """A valid stream of exactly `target` bytes: a sheet padded with repeated rules, then a one-element document."""
    doc = enc_doc(("div", "", "", []))
    raw = enc_sheet([(1, "div", [("color", "red", False)])])[:-1]
    pad = lambda n: enc_sheet([(1, "p", [("margin", "z" * n, False)])])[:-1]
    while target - (len(raw) + 1 + len(doc)) > len(pad(200)) + 40:
        raw += pad(200)
    last = target - (len(raw) + 1 + len(doc))
    n = 1
    while len(pad(n)) < last:
        n += 1
    assert len(pad(n)) == last, (len(pad(n)), last)
    out = raw + pad(n) + b"\x00" + doc
    assert len(out) == target
    return out


def cap_cases():
    C = []
    red = [("color", "red", False)]
    ok = lambda name, rules, doc: C.append(dict(name="bound-" + name + "-at", rules=rules, doc=doc, styles=None, status=0, ref=True))
    no = lambda name, code, rules, doc: C.append(dict(name="bound-" + name + "-past", rules=rules, doc=doc, styles=None, status=code, ref=False))
    sheet = [(1, "div", red)]
    wide = lambda n: ("div", "", "", [("p", "", "", []) for _ in range(n - 1)])
    cls = lambda k: " ".join("c%d" % i for i in range(k))
    ok("nodes-128", sheet + [(1, "p", [("color", "blue", False)])], wide(128))
    no("nodes-128", 3, sheet, wide(129))
    ok("depth-32", sheet, chain(32))
    no("depth-32", 11, sheet, chain(33))
    ok("classes-per-node-8", [(1, ".c7", red)], ("div", "", cls(8), []))
    ok("classes-per-node-repeats-collapse", [(1, ".c7", red)], ("div", "", cls(8) + " c0 c3 c7", []))
    no("classes-per-node-8", 9, sheet, ("div", "", cls(9), []))
    ok("classes-per-compound-4", [(1, ".c0.c1.c2.c3", red)], ("div", "", cls(4), []))
    no("classes-per-compound-4", 9, [(1, ".c0.c1.c2.c3.c4", red)], ("div", "", cls(5), []))
    ok("compounds-per-selector-8", [(1, "a b c d e f g h", red)], chain(8, "a"))
    no("compounds-per-selector-8", 8, [(1, "a b c d e f g h i", red)], chain(9, "a"))
    many = lambda n: [(1, ".c%d" % (i % 8), [("color", "red%d" % i, False)]) for i in range(n)]
    ok("selector-entries-128", many(128), ("div", "", cls(8), []))
    no("selector-entries-128", 6, many(129), ("div", "", cls(8), []))
    lst = lambda n: [(1, ",".join(["p"] * min(32, n - 32 * r)), red) for r in range((n + 31) // 32)]
    ok("selector-entries-128-by-list", lst(128), ("div", "", cls(8), []))
    no("selector-entries-128-by-list", 6, lst(129), ("div", "", cls(8), []))
    props16 = ["p%d" % i for i in range(16)]
    ok("properties-16", [(1, "div", [(p, "v", False) for p in props16])], ("div", "", "", []))
    no("properties-16", 10, [(1, "div", [(p, "v", False) for p in props16 + ["p16"]])], ("div", "", "", []))
    d512 = [(1, "div", [(props16[j], "v%d" % j, False) for j in range(4)]) for r in range(128)]
    ok("declarations-512", d512, ("div", "", "", []))
    no("declarations-512", 7, d512 + [(1, "div", [("p0", "last", False)])], ("div", "", "", []))
    eight = lambda n: [(1, "a b c d e f g h", red)] * n
    ok("compounds-256", eight(32), chain(8, "a"))
    no("compounds-256", 8, eight(32) + [(1, "a", red)], chain(8, "a"))
    # strings: one table of 511 (tags, ids, classes, property names and values); 4 property names, 1 tag, the rest values
    for total, code in ((511, 0), (512, 4)):
        vals = ["v%d" % i for i in range(total - 5)]
        names = ["color", "margin", "padding", "border"]
        rules = [(1, "div", [(names[j], vals[k + j], False) for j in range(min(4, len(vals) - k))]) for k in range(0, len(vals), 4)]
        case = dict(name="bound-strings-511-" + ("at" if code == 0 else "past"), rules=rules, doc=("div", "", "", []), styles=None, status=code, ref=(code == 0))
        assert len(interned(case)) == total, (len(interned(case)), total)
        C.append(case)
    # pool: 4096 bytes of string text fit, 4097 do not ("div" and "color" are 8 of them)
    for total, code in ((4096, 0), (4097, 5)):
        left, words, i = total - 8, [], 0
        while left > 0:
            n = min(200, left)
            words.append(("w%d_" % i + "k" * 200)[:n])
            left -= n
            i += 1
        case = dict(name="bound-pool-4096-" + ("at" if code == 0 else "past"), rules=[(1, "div", [("color", w, False)]) for w in words],
                    doc=("div", "", "", []), styles=None, status=code, ref=(code == 0))
        assert sum(len(x) for x in interned(case)) == total, (sum(len(x) for x in interned(case)), total)
        C.append(case)
    C.append(dict(name="bound-input-16384-at", rules=[], doc=("div", "", "", []), styles=[{"color": "red"}], status=0, ref=False, raw=sized_input(INPUT_MAX)))
    C.append(dict(name="bound-input-16384-past", rules=[], doc=None, styles=None, status=2, ref=False, raw=sized_input(INPUT_MAX + 1)))
    return C


def all_cases(seed=20261106, n_random=120):
    rules, _text = real_sheet()
    cases = hand_cases() + refusal_cases() + malformed_cases()
    for k, doc in enumerate(component_docs()):
        cases.append(dict(name="component-%02d" % k, rules=rules, doc=doc, styles=None, status=0, ref=True))
    # the real sheet over every component tree, plus a user-agent sheet of the kind a browser ships
    ua = [(0, "a", [("color", "#0000ee", False), ("cursor", "pointer", False)]), (0, "h1, h2", [("font-size", "2em", False), ("font-weight", "700", False)]),
          (0, "button", [("cursor", "default", False), ("font-size", "13px", False)]), (0, "span", [("display", "inline", False)])]
    for k, doc in enumerate(component_docs()):
        cases.append(dict(name="component-ua-%02d" % k, rules=ua + rules, doc=doc, styles=None, status=0, ref=True))
    cases += cap_cases()
    cases += random_cases(seed, n_random)
    return cases
