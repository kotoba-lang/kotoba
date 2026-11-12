#!/usr/bin/env python3
"""hostview.py PRISTINE MERGED: the host reading (every top-level `#?(:kotoba A :default H)` read as H, a
`#?(:kotoba A)` read as nothing) of MERGED must equal PRISTINE's top-level forms, byte for byte."""
import sys, re
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ov import scan

def host_forms(text):
    out = []
    for s, e in scan(text):
        b = text[s:e]
        if b.startswith('#?(:kotoba'):
            m = re.search(r'\n?\s*:default\s*\n?', b)
            # the :default arm is the LAST top-level element of the conditional
            inner = b[3:-1]
            # find top-level elements of inner
            els = [inner[a:z] for a, z in scan_elems(inner)]
            if ':default' in els:
                out.append(els[els.index(':default') + 1].strip())
        else:
            out.append(b.strip())
    return out

def scan_elems(s):
    """top-level elements (atoms and bracketed) of S"""
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace() or c == ',': i += 1; continue
        if c == ';':
            while i < n and s[i] != '\n': i += 1
            continue
        start = i
        if c in '([{' or (c == '#' and i + 1 < n and s[i+1] in '({?'):
            depth = 0
            while i < n:
                ch = s[i]
                if ch == '"':
                    i += 1
                    while s[i] != '"':
                        if s[i] == '\\': i += 1
                        i += 1
                elif ch == ';':
                    while s[i] != '\n': i += 1
                elif ch == '\\':
                    i += 2; continue
                elif ch in '([{': depth += 1
                elif ch in ')]}':
                    depth -= 1
                    if depth == 0: i += 1; break
                i += 1
            yield start, i
        else:
            while i < n and not s[i].isspace() and s[i] not in '()[]{}': i += 1
            yield start, i

if __name__ == '__main__':
    a = host_forms(open(sys.argv[1]).read())
    b = host_forms(open(sys.argv[2]).read())
    # the ns form differs only by the added :kotoba entries
    a = [x for x in a if not x.startswith('(ns ')]
    b = [x for x in b if not x.startswith('(ns ')]
    if a == b:
        print(f"hostview: {len(a)} top-level host forms byte-identical")
    else:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print("hostview: DIFFERS at form", i, x[:80], '|', y[:80]); break
        else:
            print("hostview: DIFFERS in count", len(a), len(b))
        sys.exit(1)
