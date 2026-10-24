"""The jcs.reader corpus (kotoba/jcs/reader_gate.kotoba) and its oracle.

  python3 -I reader-corpus-20261023.py emit > kotoba/jcs/reader_gate.kotoba
  python3 -I reader-corpus-20261023.py check gate.out

`emit` writes the Kotoba driver: every case's bytes as hex, so a case can hold
what a Kotoba string literal cannot (invalid UTF-8, control bytes, a BOM).
`check` reads the image's lines and compares each with Python's json module,
set to this reader's strict profile. The profile's rules beyond RFC 8259 are
named in STRICT and applied here explicitly, so every difference from
Python's defaults is visible.
"""
import json, re, sys

CASES = [
    # (name, bytes)
    ("empty-object", b"{}"), ("empty-array", b"[]"), ("string", b'"a"'), ("zero", b"0"),
    ("minus-zero", b"-0"), ("exp", b"1.5e10"), ("neg-exp", b"-1E-2"), ("frac", b"0.25"),
    ("true", b"true"), ("false", b"false"), ("null", b"null"),
    ("spaced", b' {"a" : [1, 2, {"b": null}] } '), ("tabs-newlines", b'\t{\n"a"\r\n:\t1}\n'),
    ("escapes", b'"\\u00e9\\ud83d\\ude00\\n\\"\\\\\\/\\b\\f\\r\\t"'),
    ("raw-2", "\"\u00e9\"".encode()), ("raw-3", "\"\u20ac\"".encode()), ("raw-4", "\"\U0001f600\"".encode()),
    ("raw-del", b'"\x7f"'), ("ls-ps", "\"\u2028\u2029\"".encode()),
    ("depth-64", b"[" * 64 + b"]" * 64), ("depth-65", b"[" * 65 + b"]" * 65),
    ("depth-64-obj", b'{"a":' * 63 + b'[]' + b"}" * 63), ("big-int", b"12345678901234567890"),
    ("two-members", b'{"a":1,"b":2}'), ("nested", b'{"a":{"b":{"c":[1,{"d":"e"}]}}}'),
    ("open-object", b"{"), ("close-object", b"}"), ("trailing-comma-array", b"[1,]"),
    ("leading-comma", b"[,1]"), ("trailing-comma-object", b'{"a":1,}'), ("missing-colon", b'{"a" 1}'),
    ("bare-key", b"{a:1}"), ("leading-zero", b"01"), ("dot-end", b"1."), ("dot-start", b".5"),
    ("minus-only", b"-"), ("exp-empty", b"1e"), ("plus", b"+1"), ("nan", b"NaN"), ("infinity", b"Infinity"),
    ("minus-infinity", b"-Infinity"), ("tru", b"tru"), ("nulll", b"nulll"), ("unterminated", b'"abc'),
    ("bad-escape", b'"\\x"'), ("short-u", b'"\\u12"'), ("upper-u", b'"\\u00E9"'),
    ("lone-high", b'"\\ud800"'), ("lone-low", b'"\\udc00"'), ("high-then-a", b'"\\ud800\\u0041"'),
    ("control", b'"a\x01b"'), ("raw-tab", b'"a\tb"'), ("raw-newline", b'"a\nb"'),
    ("overlong-2", b'"\xc0\x80"'), ("overlong-3", b'"\xe0\x80\x80"'), ("utf8-surrogate", b'"\xed\xa0\x80"'),
    ("above-max", b'"\xf4\x90\x80\x80"'), ("truncated", b'"\xe2\x82"'), ("stray-continuation", b'"\x80"'),
    ("f5", b'"\xf5\x80\x80\x80"'), ("bom", b"\xef\xbb\xbf{}"), ("two-values", b"1 2"), ("empty", b""),
    ("only-space", b"  "), ("duplicate", b'{"a":1,"a":2}'), ("duplicate-nested", b'{"x":{"a":1,"b":2,"a":3}}'),
    ("same-key-other-objects", b'[{"a":1},{"a":2}]'), ("escaped-key", b'{"\\u0061":1}'),
    ("escaped-key-dup", b'{"a":1,"\\u0061":2}'), ("value-escape-ok", b'{"a":"\\u0061"}'),
    ("unclosed-nested", b'[{"a":[1,2}]'), ("mismatch", b"[}"), ("colon-in-array", b"[1:2]"),
    ("comment", b"[1]//x"), ("single-quote", b"['a']"), ("hex-number", b"0x10"),
    # canonical form
    ("canon", b'{"a":1,"b":[true,null,"x"],"c":{"d":-5}}'), ("canon-order", b'{"b":1,"a":2}'),
    ("canon-float", b'{"a":1.5}'), ("canon-control", b'{"a":"\\u0001"}'), ("canon-upper-control", b'{"a":"\\u001F"}'),
    ("canon-slash", b'{"a":"\\/"}'), ("canon-raw-e", "{\"a\":\"\u00e9\"}".encode()), ("canon-escaped-e", b'{"a":"\\u00e9"}'),
    ("canon-space", b'{"a": 1}'), ("canon-digit-keys", b'{"10":1,"9":2}'), ("canon-non-ascii-key", "{\"\u00e9\":1}".encode()),
    ("canon-prefix", b'{"a":1,"ab":2}'), ("canon-prefix-wrong", b'{"ab":1,"a":2}'), ("canon-minus-zero", b'{"a":-0}'),
    ("canon-newline-escape", b'{"a":"x\\ny"}'), ("canon-tab-u", b'{"a":"\\u0009"}'), ("canon-big", b'{"a":9007199254740992}'),
    ("canon-nested-order", b'{"a":{"y":1,"x":2}}'),
    # canonical bytes from non-canonical input
    ("recanon-mixed", b'{"b":1, "a":[3, {"d":"\\u00e9","c":"\\/"}]}'), ("recanon-minus-zero", b"-0"),
    ("recanon-space-string", b' "x" '), ("recanon-newline", b'{"a":"\\u000a"}'), ("recanon-control", b'{"a":"\\u001F"}'),
    ("recanon-deep", b'{"z":{"y":{"x":[{"b":2,"a":1}]}}}'), ("recanon-literals", b'[ true , false , null ]'),
    ("recanon-float", b'{"a":[1, 2.5]}'), ("recanon-unicode-key", "{\"\u00e9\":1, \"a\":2}".encode()),
    ("recanon-surrogate", b'"\\ud83d\\ude00"'), ("recanon-big", b"[9007199254740991, -9007199254740991]"),
]

STRICT = ["a byte order mark is not whitespace", "duplicate keys are refused", "keys may not contain escapes",
          "a \\u surrogate must be a pair", "nesting deeper than 64 is refused", "NaN and Infinity are refused"]

def depth(o):
    if isinstance(o, dict): return 1 + max([depth(v) for v in o.values()] or [0])
    if isinstance(o, list): return 1 + max([depth(v) for v in o] or [0])
    return 0

def lone(o):
    if isinstance(o, str): return any(0xD800 <= ord(ch) <= 0xDFFF for ch in o)
    if isinstance(o, dict): return any(lone(k) or lone(v) for k, v in o.items())
    if isinstance(o, list): return any(lone(v) for v in o)
    return False

# canonical form only: JavaScript holds numbers as doubles, so an integer
# beyond +-(2^53-1) would not print back the same; it is not canonical
def floats(o):
    if isinstance(o, float): return True
    if isinstance(o, int) and not isinstance(o, bool) and abs(o) > 2**53 - 1: return True
    if isinstance(o, dict): return any(floats(v) for v in o.values())
    if isinstance(o, list): return any(floats(v) for v in o)
    return False

def parse(data):
    """the value under the strict profile, or a reason it is refused"""
    if data.startswith(b"\xef\xbb\xbf"): return None, "bom"
    try: s = data.decode("utf-8")
    except UnicodeDecodeError: return None, "utf-8"
    def hook(pairs):
        if len({k for k, _ in pairs}) != len(pairs): raise ValueError("duplicate")
        return dict(pairs)
    def const(c): raise ValueError("constant")
    try: o = json.loads(s, object_pairs_hook=hook, parse_constant=const)
    except (ValueError, RecursionError): return None, "python"
    toks = [m for m in re.finditer(r'"(?:[^"\\]|\\.)*"', s)]
    for m in toks:
        rest = s[m.end():].lstrip(" \t\r\n")
        if rest.startswith(":") and "\\" in m.group(0): return None, "escaped-key"
    if lone(o): return None, "lone-surrogate"
    if depth(o) > 64: return None, "depth"
    return o, None

def canonical_bytes(data):
    """the canonical form, or None outside the domain (floats, unsafe
    integers, non-ASCII or all-digit keys)"""
    o, why = parse(data)
    if why or floats(o): return None
    def keys_ok(x):
        if isinstance(x, dict):
            return all(k.isascii() and not k.isdigit() for k in x) and all(keys_ok(v) for v in x.values())
        if isinstance(x, list): return all(keys_ok(v) for v in x)
        return True
    if not keys_ok(o): return None
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def canonical(data):
    return canonical_bytes(data) == data

def emit():
    print(";; jcs.reader-gate -- generated by docs/evidence/reader-corpus-20261023.py emit; do not edit.")
    print(";; One line per case: case <name> <valid 0|1> <end code> <canonical 0|1> <canonical bytes hex|-> [<decoded hex>|<int>].")
    print("(ns jcs.reader-gate (:export [main]))\n")
    print("(defn- rg-hex [s :string] :vector-i64")
    print("  (let [b (vector-i64-from-bytes (string-to-utf8 s)) n (quot (vector-count b) 2)]")
    print("    (loop [i 0 out (vector-alloc n)]")
    print("      (if (= i n) out")
    print("        (let [h (vector-at b (* 2 i)) l (vector-at b (+ (* 2 i) 1))")
    print("              v (+ (* 16 (if (< h 58) (- h 48) (- h 87))) (if (< l 58) (- l 48) (- l 87)))]")
    print("          (recur (+ i 1) (vector-assoc! out i v)))))))\n")
    print("(defn- rg-say [s :string] :i64 (let [x (typed-cap-call :io/write :string :string (string-concat s \"\\n\"))] 0))\n")
    print("(defn- rg-case [name :string hx :string] :i64")
    print("  (let [b (rg-hex hx) s (loop [j 0] (if (and (< j (vector-count b)) (or (= (vector-at b j) 32) (= (vector-at b j) 9) (= (vector-at b j) 10) (= (vector-at b j) 13))) (recur (+ j 1)) j))")
    print("        e (json-end b s) ok (json-valid? b)")
    print("        canon (if ok (json-canonical? b) false)")
    print("        cb (if ok (json-canonical-bytes b s) (vector-alloc 0))")
    print("        extra (cond (and ok (= (json-kind b s) 3)) (string-concat \" \" (hex (json-string-bytes b s)))")
    print("                    (and ok (= (json-kind b s) 4) (json-int-ok? b s)) (string-concat \" \" (string-from-i64 (json-int b s)))")
    print("                    :else \"\")]")
    print("    (rg-say (str \"case \" name \" \" (if ok 1 0) \" \" e \" \" (if canon 1 0) \" \" (if (> (vector-count cb) 0) (hex cb) \"-\") extra))))\n")
    print("(defn- rg-corpus [] :i64")
    print("  (let [")
    for k, (name, data) in enumerate(CASES):
        print(f'        c{k} (rg-case "{name}" "{data.hex()}")')
    print(f"        ] {len(CASES)}))\n")
    nav = ('{"schema":1,"nodes":[{"node":"b70","did":"did:key:z6Mk"},{"node":"k16","drain":true}],'
           '"name":"a\\"b\\u00e9","neg":-42,"big":9007199254740992}').encode()
    print("(defn- rg-doc [] :vector-i64 (rg-hex \"" + nav.hex() + "\"))\n")
    print("""(defn- rg-navigation [] :bool
  (let [b (rg-doc) nodes (json-member b 0 "nodes") n1 (json-element b nodes 1)]
    (and (json-valid? b) (= (json-kind b 0) 1) (= (json-count b 0) 5)
         (= (json-kind b nodes) 2) (= (json-count b nodes) 2) (= (json-element b nodes 2) -1)
         (= (json-kind b n1) 1) (= (json-string b (json-member b n1 "node")) "k16")
         (= (json-kind b (json-member b n1 "drain")) 5) (= (json-member b n1 "did") -1)
         (= (json-string b (json-member b (json-element b nodes 0) "did")) "did:key:z6Mk")
         (= (hex (json-string-bytes b (json-member b 0 "name"))) "612262c3a9")
         (= (json-int b (json-member b 0 "schema")) 1)
         (json-int-ok? b (json-member b 0 "neg")) (= (json-int b (json-member b 0 "neg")) -42)
         (not (json-int-ok? b (json-member b 0 "big")))
         (= (json-member b 0 "missing") -1) (= (json-member b nodes "node") -1))))

(defn- rg-reasons [] :bool
  (and (= (json-end (rg-hex \"""" + (b"[" * 65 + b"]" * 65).hex() + """\") 0) -2)
       (= (json-end (rg-hex \"""" + b'{"a":1,"a":2}'.hex() + """\") 0) -5)
       (= (json-end (rg-hex \"""" + b'{"\\u0061":1}'.hex() + """\") 0) -6)
       (= (json-end (rg-hex \"""" + b'"a\x01"'.hex() + """\") 0) -3)
       (= (json-end (rg-hex \"""" + b"1.".hex() + """\") 0) -4)
       (= (json-end (rg-hex \"""" + b"[1,]".hex() + """\") 0) -1)))

(defn main [] :i64
  (let [n (rg-corpus) x (rg-say (string-concat "cases " (string-from-i64 n)))]
    (+ (if (rg-navigation) 1 0) (if (rg-reasons) 2 0))))""")

def check(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    report = lines.pop()
    assert lines[-1] == f"cases {len(CASES)}", lines[-1]
    got = {l.split(" ")[1]: l.split(" ")[2:] for l in lines[:-1]}
    bad = []
    for name, data in CASES:
        o, why = parse(data)
        f = got[name]
        if (f[0] == "1") != (why is None): bad.append((name, "valid", f, why)); continue
        if f[2] != ("1" if canonical(data) else "0"): bad.append((name, "canonical", f)); continue
        cb = canonical_bytes(data) if why is None else None
        if f[3] != (cb.hex() if cb is not None else "-"): bad.append((name, "canonical-bytes", f)); continue
        if why is None and isinstance(o, str) and (len(f) < 5 or f[4] != o.encode("utf-8").hex()): bad.append((name, "string", f))
        if why is None and isinstance(o, int) and not isinstance(o, bool) and abs(o) <= 2**53 - 1 and b"." not in data and b"e" not in data.lower():
            if len(f) < 5 or int(f[4]) != o: bad.append((name, "int", f))
    print(report.split(" :fuel")[0], "|", len(CASES), "cases,", sum(1 for n, d in CASES if parse(d)[1] is None), "valid,",
          sum(1 for n, d in CASES if canonical(d)), "canonical,",
          sum(1 for n, d in CASES if parse(d)[1] is None and canonical_bytes(d) is not None), "canonicalizable,", len(bad), "disagree")
    for x in bad: print("DISAGREE", x)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    emit() if sys.argv[1] == "emit" else check(sys.argv[2])
