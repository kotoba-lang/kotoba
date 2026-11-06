"""Case grid and independent host reference of the UI-document front end (JUN-856, ADR-0287): the compact UI document in a region becomes the wire
stream of the style slice (src/cssom/uidoc_k.kotoba), and style, layout and draw then run on it (the existing slices, unchanged).

A case is a dict of draw_k_cases (name, rules, doc, vw, status, ref, boxes, doch, ops, dstatus) plus, for this front end:
  blob     the compact UI document bytes handed to the kernel (made by `encode_uidoc`, or raw bytes for malformed documents)
  utree    the document tree with text placeholders (an int child = a text node of that many bytes); `doc` is the same tree without them
  ustatus  the status the front end must answer (the wire stream length for a document that expands, else the negative code), written out
           by hand in the case table where it is a refusal; None where it is the length the reference computes
  wire     the canonical wire stream (style_k_cases.encode form) the expansion must equal byte for byte, or None for a refusal
  texts    (count, bytes) of the text placeholders

The reference (`ref_expand`) is deliberately independent of uidoc_k.kotoba: it parses the document from the layout written in the module header and in
the evidence README, and produces the wire stream by building each element's record with bytes operations, not by copying. `encode_uidoc` is the host
encoder (a proposal: first use of a string gives its index). Nothing here is random at run time."""
import html.parser
import random
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import draw_k_cases as D  # noqa: E402
import layout_k_cases as L  # noqa: E402
import style_k_cases as K  # noqa: E402

Q, R, T, B = L.Q, L.R, K.T, L.B
LIB = HERE.parents[1]
INDEX_HTML = LIB / "kotoba.aiueos/resources/aiueos/session/index.html"
APPS = ("murakumo itonami yataverse aozora browser yotei shakai saifu bunsho hyokeisan zuhyo tokei wifi bluetooth settei itonami-apps updates torihiki").split()
MAGIC = b"UID1"
DOC_MAX, WIRE_MAX, STR_MAX = 8192, 16384, 255
VOID = K.VOID


# ------------------------------------------------------------------ trees with text placeholders
def strip_text(n):
    """The element-only tree (style_k_cases form) of a tree whose text children are ints."""
    return (n[0], n[1], n[2], [strip_text(k) for k in n[3] if not isinstance(k, int)])


def text_stats(n):
    """(text nodes, text bytes) of a tree."""
    c = b = 0
    for k in n[3]:
        if isinstance(k, int):
            c, b = c + 1, b + k
        else:
            x, y = text_stats(k)
            c, b = c + x, b + y
    return c, b


def count_elements(n):
    return 1 + sum(count_elements(k) for k in n[3] if not isinstance(k, int))


class _Tree(html.parser.HTMLParser):
    """Elements with id and class and text nodes of their stripped UTF-8 length; whitespace-only text, comments and every other attribute are dropped.
    With `only` it captures the subtrees whose root element has an id in `only` (the `hidden` attribute is not carried: the window is rendered open)."""

    def __init__(self, only=None):
        super().__init__(convert_charrefs=True)
        self.only, self.stack, self.roots, self.found = only, [], [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = [tag, a.get("id") or "", a.get("class") or "", []]
        if self.stack:
            self.stack[-1][3].append(node)
        elif self.only is None or (a.get("id") in self.only):
            self.roots.append(node)
            self.found[a.get("id")] = node
        else:
            return
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, d):
        if self.stack and self.stack[-1][0] not in ("script", "style") and d.strip():
            self.stack[-1][3].append(len(d.strip().encode()))


def freeze(n):
    return n if isinstance(n, int) else (n[0], n[1], n[2], [freeze(k) for k in n[3]])


def app_windows():
    """{app id: tree} of the eighteen dapp windows of the hosted session page (the checked-in generated page, read as data)."""
    p = _Tree(only=set(APPS))
    p.feed(INDEX_HTML.read_text())
    missing = [a for a in APPS if a not in p.found]
    assert not missing, ("windows not found in index.html", missing)
    return {a: freeze(p.found[a]) for a in APPS}


def component_trees():
    """The component trees of kotoba.html ui_components_test.kotoba as style_k_cases.component_docs builds them, with text placeholders."""
    src = K.HTML_TEST.read_text()
    out = []
    for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', src):
        if not lit.startswith("<"):
            continue
        p = _Tree()
        p.feed(lit.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\"))
        roots = [freeze(r) for r in p.roots]
        if roots:
            out.append(roots[0] if len(roots) == 1 else ("div", "", "", roots))
    assert [strip_text(t) for t in out] == K.component_docs(), "component trees differ from style_k_cases.component_docs"
    return out


# ------------------------------------------------------------------ the native subset sheet of the dapp window frame
# Authored for this chain, NOT the page's stylesheet: the page's rules use var(), shorthands, flex and grid, which the style / layout slices refuse or
# do not model (and the sheet may name at most 16 distinct properties). Each rule keeps the real rule's selector and its resolved values (--hig-spacing-N
# = N*4px for 3..6, hairline 1px, colours from the page's :root); where a real value cannot be written it is left out, as the comments say.
GRAY50, GRAY200, GRAY300, WHITE, KEY900 = "#f2f2f2", "#cccccc", "#b3b3b3", "#ffffff", "#0017c1"


def _four(prefix, suffix, v):
    return [(prefix + "-" + s + suffix, v, False) for s in ("top", "right", "bottom", "left")]


def dapp_sheet():
    r = lambda sel, *d: (1, sel, [x for part in d for x in (part if isinstance(part, list) else [part])])
    c = lambda p, v: (p, v, False)
    return [
        r("*", c("display", "block")),                                                    # the page shows a/span/button as inline or flex items; block here
        r(".app-window", c("max-width", "1024px"), c("margin-top", "24px"), c("margin-left", "auto"), c("margin-right", "auto"),   # margin-bottom: 16 properties max
          _four("border", "-width", "1px"), c("background-color", WHITE), c("border-color", GRAY300)),
        r(".app-window-head", c("height", "44px"), c("padding-left", "12px"), c("padding-right", "12px"), c("border-bottom-width", "1px"),  # min-height
          c("background-color", GRAY50), c("border-color", GRAY300)),
        r(".window-close", c("height", "24px"), _four("border", "-width", "1px"), c("border-color", GRAY300)),                  # width 24px: not in the 16
        r(".app-window-body", _four("padding", "", "20px")),
        r(".dds-ext-card", _four("border", "-width", "1px"), _four("padding", "", "24px"), c("background-color", WHITE), c("border-color", GRAY200)),
        r(".session-out", _four("border", "-width", "1px"), _four("padding", "", "12px"), c("background-color", GRAY50), c("border-color", GRAY300)),
        r(".app-return", c("margin-top", "16px")),
        r(".app-empty-state", _four("padding", "", "16px"), c("border-left-width", "1px"), c("background-color", GRAY50), c("border-color", KEY900)),
    ]


# ------------------------------------------------------------------ host encoder (proposal) and independent reference decoder
def encode_uidoc(rules, utree, raw_sheet=None):
    """Compact UI document bytes: header, the wire sheet without its terminator, the string table (first use gives the index), the tree ops."""
    sheet = raw_sheet if raw_sheet is not None else K.enc_sheet(rules)[:-1]
    table, index = [], {}

    def sidx(s):
        b = s.encode()
        assert 1 <= len(b) <= STR_MAX, ("string length", len(b))
        if b not in index:
            table.append(b)
            index[b] = len(table)
        return index[b]
    tree = bytearray()

    def go(n):
        tag, idv, cls, kids = n
        f = (1 if idv else 0) | (2 if cls else 0)
        tree.append(0x80 | f)
        tree.append(sidx(tag))
        if idv:
            tree.append(sidx(idv))
        if cls:
            tree.append(sidx(cls))
        for k in kids:
            if isinstance(k, int):
                tree.extend(b"\x40" + struct.pack("<H", k))
            else:
                go(k)
        tree.append(0)
    if utree is not None:
        go(utree)
    strings = b"".join(bytes([len(b)]) + b for b in table)
    assert len(table) <= 255
    return MAGIC + struct.pack("<HHHH", len(sheet), len(table), len(strings), len(tree)) + sheet + strings + bytes(tree)


def wire_of(rules, doc):
    """The canonical wire stream (style_k_cases form)."""
    return K.enc_sheet(rules) + K.enc_doc(doc)


def ref_expand(blob):
    """(status, wire, texts, text bytes): the reference of ud-run. status is the stream length (>= 2) or -30..-35; on a refusal wire is b""."""
    n = len(blob)
    if n < 12 or n > DOC_MAX or blob[:4] != MAGIC:
        return -30, b"", 0, 0
    s, cnt, g, t = struct.unpack_from("<HHHH", blob, 4)
    if cnt > 255 or 12 + s + g + t != n:
        return -30, b"", 0, 0
    sheet, table, tree = blob[12:12 + s], blob[12 + s:12 + s + g], blob[12 + s + g:]
    strings, pos = [], 0
    while len(strings) < cnt:
        ln = table[pos] if pos < len(table) else 0
        if ln == 0:
            return -31, b"", 0, 0
        strings.append(table[pos + 1:pos + 1 + ln])
        pos += 1 + ln
    if pos != len(table):
        return -31, b"", 0, 0
    out = bytearray(sheet) + b"\x00"
    depth = texts = tbytes = 0
    i = 0
    while i < len(tree):
        op = tree[i]
        if op == 0:
            if depth == 0:
                return -35, b"", 0, 0
            if len(out) + 1 > WIRE_MAX - 1:
                return -34, b"", 0, 0
            out += b"/"
            depth, i = depth - 1, i + 1
        elif op == 0x40:
            if depth == 0:
                return -35, b"", 0, 0
            if i + 3 > len(tree):
                return -32, b"", 0, 0
            texts, tbytes, i = texts + 1, tbytes + tree[i + 1] + 256 * tree[i + 2], i + 3
        elif 0x80 <= op <= 0x83:
            has_id, has_cls = op & 1, (op >> 1) & 1
            need = 2 + has_id + has_cls
            if i + need > len(tree):
                return -32, b"", 0, 0
            ops = tree[i + 1:i + need]
            if any(not (1 <= x <= cnt) for x in ops):
                return -33, b"", 0, 0
            tag = strings[ops[0] - 1]
            idv = strings[ops[1] - 1] if has_id else b""
            cls = strings[ops[1 + has_id] - 1] if has_cls else b""
            rec = b"E" + bytes([len(tag)]) + tag + bytes([len(idv)]) + idv + bytes([len(cls)]) + cls
            if len(out) + len(rec) > WIRE_MAX - 1:
                return -34, b"", 0, 0
            out += rec
            depth, i = depth + 1, i + need
        else:
            return -32, b"", 0, 0
    if depth != 0:
        return -35, b"", 0, 0
    out += b"\x00"
    return len(out), bytes(out), texts, tbytes


def fixture_blob(c):
    """One case of the fw_cfg file: [doc length:2][viewport width:4][document][wire length:2][canonical wire]. A refusal has wire length 0."""
    d = c["blob"]
    w = c["wire"] or b""
    assert len(d) <= 65535 and len(w) <= WIRE_MAX
    return struct.pack(">HI", len(d), c["vw"]) + d + struct.pack(">H", len(w)) + w


# ------------------------------------------------------------------ cases
def make(name, rules, utree, vw=400, vwq=None, **kw):
    """A case whose document expands: blob from the encoder, canonical wire from the rules and the element-only tree."""
    doc = strip_text(utree) if utree is not None else None
    wire = wire_of(rules, doc) if doc is not None else K.enc_sheet(rules) + b"\x00"
    c = dict(name=name, rules=rules, doc=doc, utree=utree, vw=Q(vw) if vwq is None else vwq, status=None, ref=False,
             boxes=None, doch=None, ops=None, dstatus=None, blob=encode_uidoc(rules, utree), wire=wire, ustatus=None,
             texts=text_stats(utree) if utree is not None else (0, 0))
    c.update(kw)
    return c


def raw(name, blob, ustatus, note=None, rules=None):
    """A document that must be refused by the front end with a fixed status (written out here, not computed)."""
    c = dict(name=name, rules=rules or [], doc=None, utree=None, vw=Q(400), status=None, ref=False, boxes=None, doch=None, ops=None, dstatus=None,
             blob=blob, wire=None, ustatus=ustatus, texts=(0, 0))
    if note:
        c["note"] = note
    return c


def hdr(sheet=b"", strings=(), tree=b"", s=None, n=None, g=None, t=None, magic=MAGIC):
    tbl = b"".join(bytes([len(x)]) + x for x in strings)
    return magic + struct.pack("<HHHH", len(sheet) if s is None else s, len(strings) if n is None else n, len(tbl) if g is None else g,
                               len(tree) if t is None else t) + sheet + tbl + tree


def tokei_case():
    """The tokei window with the dapp sheet at 1280 px, geometry and draw list written out from the CSS rules (px) and CSS 2.1 block flow."""
    w = app_windows()["tokei"]
    c = make("uidoc-hand-tokei-window", dapp_sheet(), w, vw=1280)
    z = dict(bt=0, br=0, bb=0, bl=0)
    b1 = dict(bt=1, br=1, bb=1, bl=1)
    # elements in document order: 0 section, 1 article, 2 header, 3 close, 4 title, 5 spacer, 6 state, 7 body, 8 h1, 9 p, 10 card, 11 pre, 12 return
    c["boxes"] = [B(0, 24, 1280, 179, **z), B(127, 24, 1026, 179, **b1), B(128, 25, 1024, 45, **dict(z, bb=1)), B(140, 25, 1000, 26, **b1),
                  B(140, 51, 1000, 0, **z), B(140, 51, 1000, 0, **z), B(140, 51, 1000, 0, **z), B(128, 70, 1024, 132, **z),
                  B(148, 90, 984, 0, **z), B(148, 90, 984, 0, **z), B(148, 90, 984, 76, **b1), B(173, 115, 934, 26, **b1), B(148, 182, 984, 0, **z)]
    wh, g3, g2, g5, k9 = 0xFFFFFFFF, 0xB3B3B3FF, 0xCCCCCCFF, 0xF2F2F2FF, 0
    c["ops"] = [(1, 0, 127, 24, 1026, 179, wh), (1, 1, 127, 24, 1026, 1, g3), (1, 2, 1152, 25, 1, 177, g3), (1, 3, 127, 202, 1026, 1, g3), (1, 4, 127, 25, 1, 177, g3),
                (2, 0, 128, 25, 1024, 45, g5), (2, 3, 128, 69, 1024, 1, g3),
                (3, 1, 140, 25, 1000, 1, g3), (3, 2, 1139, 26, 1, 24, g3), (3, 3, 140, 50, 1000, 1, g3), (3, 4, 140, 26, 1, 24, g3),
                (10, 0, 148, 90, 984, 76, wh), (10, 1, 148, 90, 984, 1, g2), (10, 2, 1131, 91, 1, 74, g2), (10, 3, 148, 165, 984, 1, g2), (10, 4, 148, 91, 1, 74, g2),
                (11, 0, 173, 115, 934, 26, g5), (11, 1, 173, 115, 934, 1, g3), (11, 2, 1106, 116, 1, 24, g3), (11, 3, 173, 140, 934, 1, g3), (11, 4, 173, 116, 1, 24, g3)]
    c.update(status=0, dstatus=0, doch=203, expect_ok=True)
    return c


def app_cases():
    sheet = dapp_sheet()
    out = []
    for a, tree in app_windows().items():
        c = make("uidoc-app-" + a, sheet, tree, vw=1280)
        c.update(status=0, dstatus=0, expect_ok=True)
        out.append(c)
    hand = tokei_case()
    return [hand] + out


def component_cases():
    out = []
    for k, tree in enumerate(component_trees()):
        doc = strip_text(tree)
        rules = L.block_sheet(doc, k)
        cls = []

        def go(n):
            for x in (n[2] or "").split(" "):
                if x and x not in cls:
                    cls.append(x)
            for y in n[3]:
                go(y)
        go(doc)
        rng = random.Random("uidoc/%d" % k)
        rules = rules + [(1, "." + x, [("background-color", rng.choice(D.COLORS), False), ("border-color", rng.choice(D.COLORS), False)]) for x in cls]
        out.append(make("uidoc-component-%02d" % k, rules, tree, vw=480))
    return out


def sprinkle(doc, rng, p=0.5):
    """The element tree with text placeholders of random size added between and around the children (never outside the root)."""
    kids = []
    for k in doc[3]:
        if rng.random() < p:
            kids.append(rng.choice([1, 2, 7, 40, 255, 256, 1000, 65535]))
        kids.append(sprinkle(k, rng, p))
    if rng.random() < p:
        kids.append(rng.choice([3, 12, 300]))
    return (doc[0], doc[1], doc[2], kids)


def random_cases(seed=20261107, n=40):
    out = []
    for i, c in enumerate(D.random_cases(seed, n)):
        rng = random.Random("uidoc/%s/%d" % (seed, i))
        out.append(make("uidoc-random-%03d" % i, c["rules"], sprinkle(c["doc"], rng), vwq=c["vw"]))
    return out


def hand_cases():
    C = []
    star = [(1, "*", [("display", "block", False)])]
    blk = lambda *more: star + list(more)
    add = C.append
    # attributes and strings
    add(make("uidoc-minimal-div", star, T("div"), vw=100))
    add(make("uidoc-id-only", blk(R("#x", height="10px", background_color="#123456")), T("div", "x"), vw=100))
    add(make("uidoc-class-only", blk(R(".a", height="10px", background_color="#abc")), T("div", "", "a"), vw=100))
    add(make("uidoc-id-and-class", blk(R(".a", height="10px"), R("#x", background_color="#fedcba")), T("div", "x", "a"), vw=100))
    add(make("uidoc-multi-token-class", blk(R(".b", height="7px", background_color="#0f0")), T("div", "", "a b c"), vw=100))
    add(make("uidoc-strings-deduplicated", blk(R(".r", height="3px", background_color="#111")), T("div", "", "r", T("div", "", "r"), T("div", "", "r"), T("div", "", "r")), vw=100))
    add(make("uidoc-sheet-empty", [], T("div", "", "a", T("p")), vw=100))
    add(make("uidoc-sheet-malformed-passes-through", [], T("div"), vw=100, ustatus=None,
             blob=encode_uidoc([], T("div"), raw_sheet=b"R\x01\x03div\x01"), wire=b"R\x01\x03div\x01" + b"\x00" + K.enc_doc(T("div"))))
    # text placeholders
    add(make("uidoc-text-first-between-last", blk(R(".a", height="4px", background_color="#f00")), T("div", "", "a", 5, T("p"), 9, T("p"), 11), vw=100))
    add(make("uidoc-text-nested-and-empty-elements", blk(R(".t", height="2px")), T("div", "", "t", T("div", "", "t", 3, T("div", "", "t", 4), 5), 6), vw=100))
    add(make("uidoc-text-65535-bytes", star, T("div", "", "", 65535, 65535), vw=100))
    # shapes
    chain = lambda n: (lambda f: f(f, n))(lambda f, k: T("div", "", "a", f(f, k - 1)) if k > 1 else T("div", "", "a"))
    add(make("uidoc-depth-32", blk(R(".a", padding_left="1px", border_left_width="1px")), chain(32), vw=400))
    add(make("uidoc-depth-33-cascade-refuses", blk(R(".a", padding_left="1px")), chain(33), vw=400, status=11))
    add(make("uidoc-128-elements", blk(R(".a", height="1px")), T("div", "", "a", *[T("div", "", "a") for _ in range(127)]), vw=400))
    add(make("uidoc-129-elements-cascade-refuses", blk(R(".a", height="1px")), T("div", "", "a", *[T("div", "", "a") for _ in range(128)]), vw=400, status=3))
    add(make("uidoc-no-element-tree", star, None, vw=100))
    # string table bounds: 255 distinct strings is the most the u8 operand can name
    many = T("div", "", "", *[T("div", "i%d" % i, "c%d" % i) for i in range(127)])
    c = make("uidoc-255-strings", blk(R(".c1", height="1px")), many, vw=100, status=0, dstatus=0, expect_ok=True)
    assert struct.unpack_from("<H", c["blob"], 6)[0] == 255, struct.unpack_from("<H", c["blob"], 6)
    add(c)
    # a 255-byte class token (the longest string a u8 length can carry; the style slice interns it)
    add(make("uidoc-string-255-bytes", star, T("div", "", "k" * 255), vw=100, status=0, dstatus=0, expect_ok=True))
    # the document region is 8192 bytes: 8192 passes, 8193 does not (text placeholders cost 3 bytes each and nothing in the wire stream)
    def sized(target):
        for r in range(3):
            cls = "p" * (10 + r)
            need = target - len(encode_uidoc(star, T("div", "", cls)))
            if need >= 0 and need % 3 == 0:
                return T("div", "", cls, *([1] * (need // 3)))
        raise AssertionError(target)
    c = make("uidoc-document-8192-bytes", star, sized(8192), vw=100, status=0, dstatus=0, expect_ok=True)
    assert len(c["blob"]) == 8192, len(c["blob"])
    add(c)
    c2 = make("uidoc-document-8193-bytes-refused", star, sized(8193), vw=100, ustatus=-30, wire=None)
    assert len(c2["blob"]) == 8193, len(c2["blob"])
    add(c2)
    # the wire stream is 16384 bytes at most (it leaves 8 bytes of tree room): one element of a 255-byte class costs 4 + 3 + 255 wire bytes
    def wired(extra):
        kids, k, target = [], 0, WIRE_MAX + extra
        while True:
            rem = target - len(wire_of(star, T("div", "", "", *kids)))
            if 11 <= rem <= 263:
                kids.append(T("div", "", "r" * (rem - 8)))
                return T("div", "", "", *kids)
            kids.append(T("div", "", "q" * 200))             # one shared string: the wire grows by 208 bytes, the document by 4
            k += 1
    tw = wired(0)
    cw = make("uidoc-wire-16384-bytes", star, tw, vw=100)
    assert len(cw["wire"]) == WIRE_MAX, len(cw["wire"])
    add(cw)
    to = wired(1)
    co = make("uidoc-wire-16385-bytes-refused", star, to, vw=100, ustatus=-34, wire=None)
    assert len(wire_of(star, strip_text(to))) == WIRE_MAX + 1
    add(co)
    tf = wired(5000)
    cf = make("uidoc-wire-far-over-refused", star, tf, vw=100, ustatus=-34, wire=None)
    assert len(wire_of(star, strip_text(tf))) == WIRE_MAX + 5000 and count_elements(tf) <= 128
    add(cf)
    return C


def refusal_cases():
    C = []
    add = C.append
    ok_tree = bytes([0x80, 1, 0])
    add(raw("uidoc-refuse-empty", b"", -30))
    add(raw("uidoc-refuse-11-bytes", b"UID1" + b"\x00" * 7, -30))
    add(raw("uidoc-refuse-magic", hdr(strings=[b"div"], tree=ok_tree, magic=b"UID2"), -30))
    add(raw("uidoc-refuse-sections-sum-short", hdr(strings=[b"div"], tree=ok_tree, t=2), -30, note="T says 2, the tree is 3 bytes"))
    add(raw("uidoc-refuse-sections-sum-long", hdr(strings=[b"div"], tree=ok_tree, t=4), -30))
    add(raw("uidoc-refuse-256-strings", hdr(strings=[b"div"], tree=ok_tree, n=256), -30))
    add(raw("uidoc-refuse-table-fewer-entries", hdr(strings=[b"div"], tree=ok_tree, n=2), -31, note="N says 2 entries, the table holds one"))
    add(raw("uidoc-refuse-table-more-bytes", hdr(strings=[b"div", b"p"], tree=ok_tree, n=1), -31))
    add(raw("uidoc-refuse-table-empty-entry", hdr(strings=[b"div", b""], tree=ok_tree), -31))
    add(raw("uidoc-refuse-table-entry-past-end", hdr(strings=[b"div"], tree=ok_tree).replace(b"\x03div", b"\x09div", 1), -31))
    add(raw("uidoc-refuse-unknown-op-0x01", hdr(strings=[b"div"], tree=bytes([1])), -32))
    add(raw("uidoc-refuse-unknown-op-0x84", hdr(strings=[b"div"], tree=bytes([0x84, 1, 0])), -32))
    add(raw("uidoc-refuse-unknown-op-0x41", hdr(strings=[b"div"], tree=bytes([0x41])), -32))
    add(raw("uidoc-refuse-open-operand-truncated", hdr(strings=[b"div"], tree=bytes([0x80])), -32))
    add(raw("uidoc-refuse-open-id-class-operands-truncated", hdr(strings=[b"div"], tree=bytes([0x83, 1, 1])), -32))
    add(raw("uidoc-refuse-text-length-truncated", hdr(strings=[b"div"], tree=bytes([0x80, 1, 0x40, 5])), -32))
    add(raw("uidoc-refuse-tag-index-0", hdr(strings=[b"div"], tree=bytes([0x80, 0, 0])), -33))
    add(raw("uidoc-refuse-tag-index-past-N", hdr(strings=[b"div"], tree=bytes([0x80, 2, 0])), -33))
    add(raw("uidoc-refuse-id-index-past-N", hdr(strings=[b"div"], tree=bytes([0x81, 1, 2, 0])), -33))
    add(raw("uidoc-refuse-class-index-0", hdr(strings=[b"div"], tree=bytes([0x82, 1, 0, 0])), -33))
    add(raw("uidoc-refuse-close-at-depth-0", hdr(strings=[b"div"], tree=bytes([0])), -35))
    add(raw("uidoc-refuse-close-twice", hdr(strings=[b"div"], tree=bytes([0x80, 1, 0, 0])), -35))
    add(raw("uidoc-refuse-unclosed", hdr(strings=[b"div"], tree=bytes([0x80, 1])), -35))
    add(raw("uidoc-refuse-text-outside-root", hdr(strings=[b"div"], tree=bytes([0x40, 1, 0])), -35))
    add(raw("uidoc-refuse-text-after-root", hdr(strings=[b"div"], tree=bytes([0x80, 1, 0, 0x40, 1, 0])), -35))
    # precedence: operand truncation before the string check; the first fault in tree order wins
    add(raw("uidoc-refuse-first-fault-wins", hdr(strings=[b"div"], tree=bytes([0x80, 9, 0x01])), -33))
    # a second root: the front end expands it, the style slice refuses it (not a front-end fault)
    c = make("uidoc-two-roots-pass-through", [(1, "*", [("display", "block", False)])], T("div"), vw=100)
    c["blob"] = hdr(sheet=K.enc_sheet(c["rules"])[:-1], strings=[b"div"], tree=bytes([0x80, 1, 0, 0x80, 1, 0]))
    c["wire"] = K.enc_sheet(c["rules"]) + b"E\x03div\x00\x00/" + b"E\x03div\x00\x00/" + b"\x00"
    c["doc"] = None
    c["status"] = None
    c["note"] = "two root elements: ud-run expands both, the style slice answers"
    add(c)
    return C


def all_cases():
    cases = app_cases() + component_cases() + hand_cases() + refusal_cases() + random_cases()
    names = [c["name"] for c in cases]
    assert len(set(names)) == len(names) and len(cases) <= 480, len(cases)
    return cases


def expected_front(c):
    """(status, wire, texts, text bytes) the front end must answer for a case: the hand-written status of a refusal, else the reference."""
    st, wire, tx, tb = ref_expand(c["blob"])
    if c.get("ustatus") is not None and c["ustatus"] < 0:
        assert st == c["ustatus"], (c["name"], st, c["ustatus"])
    return st, wire, tx, tb


def selftest():
    """The reference against the case table before the kernel is looked at: refusals carry their written-out status, an expanding document equals the
    canonical wire stream byte for byte, the text counts match, and the hand-derived draw list is reproduced from the hand-derived box table."""
    expanded = refused = 0
    for c in all_cases():
        st, wire, tx, tb = expected_front(c)
        if c["wire"] is None:
            assert st < 0, (c["name"], st)
            refused += 1
            continue
        assert st == len(c["wire"]) and wire == c["wire"], (c["name"], st, len(c["wire"]))
        assert (tx, tb) == tuple(c["texts"]), (c["name"], (tx, tb), c["texts"])
        expanded += 1
        if c.get("boxes") is not None and c.get("ops") is not None:
            words, _m = D.table_of(c)
            s, ops, _o = D.expected(c, words)
            assert s == c["dstatus"] and ops == D.hand_ops(c), (c["name"], s, ops)
    return {"expanded": expanded, "refused": refused}
