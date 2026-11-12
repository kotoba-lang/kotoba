#!/usr/bin/env python3
"""ledger.py FILE ROOT... : one TSV row per host definition of FILE:
module, name, host-lines, status (real | folded | deferred-nil | host), covered (1 when the Kotoba reading of the
definition is reachable, in the Kotoba call graph, from one of ROOT -- the differentially tested entries)."""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ov import items, scan
from hostview import scan_elems

def kotoba_bodies(text):
    """name -> Kotoba text of every top-level Kotoba definition (twins and helpers)"""
    out = {}
    for s, e in scan(text):
        b = text[s:e]
        if not b.startswith('#?(:kotoba'): continue
        inner = b[3:-1]
        els = [inner[a:z] for a, z in scan_elems(inner)]
        k = els[1] if len(els) > 1 else 'nil'
        m = re.match(r'\(defn-?\s+([^\s\[\]()]+)', k)
        if m: out[m.group(1)] = k
    return out

def main(path, roots):
    text, its = items(path)
    bodies = kotoba_bodies(text)
    tok = re.compile(r'[A-Za-z0-9*+!?<>=_./-]+')
    edges = {n: {t for t in tok.findall(b) if t in bodies and t != n} for n, b in bodies.items()}
    seen, stack = set(), list(roots)
    while stack:
        x = stack.pop()
        if x in seen or x not in edges: continue
        seen.add(x); stack.extend(edges[x])
    mod = path.split('/src/')[-1]
    host = {}
    for x in its:
        if x['status'] in ('declare', 'helper'): continue
        b = x['body']
        if b.startswith('#?(:kotoba'):
            inner = b[3:-1]; els = [inner[a:z] for a, z in scan_elems(inner)]
            hb = els[els.index(':default') + 1] if ':default' in els else ''
        else:
            hb = b
        print(f"{mod}\t{x['name']}\t{hb.count(chr(10)) + 1}\t{x['status']}\t{1 if x['name'] in seen else 0}")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
