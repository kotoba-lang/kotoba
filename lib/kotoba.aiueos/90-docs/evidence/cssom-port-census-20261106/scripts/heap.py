#!/usr/bin/env python3
"""Heap-shape construct census over comment/string-stripped code. usage: heap.py OUT.tsv"""
import os, re, sys, os, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strip import strip_file
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../..')) + '/'
FILES = ['kotoba.cssom/src/cssom/core.cljk', 'kotoba.cssom/src/cssom/layout.cljk', 'kotoba.htmldom/src/htmldom/core.cljk',
         'kotoba.domGpu/src/kotoba/wasm/dom.cljk', 'kotoba.domGpu/src/kotoba/wasm/dom.kotoba',
         'kotoba.domGpu/src/kotoba/wasm/host/color.cljk', 'kotoba.browser/src/browser/surface.cljk',
         'kotoba.browser/src/browser/text_edit.kotoba', 'kotoba.text/src/kotoba/lang/text.cljk',
         'kotoba.text/src/kotoba/lang/text.kotoba', 'kotoba.text/src/kotoba/lang/bounded_regex.kotoba']
def calls(*names):
    return re.compile(r'\((?:' + '|'.join(re.escape(n) for n in names) + r')(?=[\s)\]])')
P = [
 ('H01-map-literal', re.compile(r'(?<![#\\\w])\{')),
 ('H02-set-literal', re.compile(r'#\{')),
 ('H03-atom-mutation', calls('atom', 'swap!', 'reset!', 'volatile!', 'vswap!', 'vreset!', 'transient', 'persistent!', 'conj!', 'assoc!')),
 ('H04-assoc-update-family', calls('assoc', 'assoc-in', 'update', 'update-in', 'dissoc', 'merge', 'merge-with', 'select-keys', 'update-vals', 'update-keys')),
 ('H05-conj-into-vec', calls('conj', 'into', 'vec', 'mapv', 'filterv', 'subvec', 'peek', 'pop', 'vector', 'concat', 'cons', 'zipmap')),
 ('H06-lookup', calls('get', 'get-in', 'contains?', 'find', 'keys', 'vals', 'nth', 'first', 'second', 'last', 'rest', 'next', 'count')),
 ('H07-seq-hof', calls('map', 'filter', 'remove', 'reduce', 'reduce-kv', 'mapcat', 'keep', 'some', 'every?', 'take', 'drop', 'take-while', 'drop-while', 'partition', 'partition-all', 'group-by', 'frequencies', 'distinct', 'sort', 'sort-by', 'reverse', 'interleave', 'range', 'repeat', 'iterate', 'doseq', 'for', 'run!')),
 ('H08-loop-recur', calls('loop', 'recur')),
 ('H09-string-ops', re.compile(r'\((?:str|subs|format)(?=[\s)])|\(str/[a-z-]+')),
 ('H10-typed-collection', re.compile(r'\(typed-[a-z-]+')),
 ('H11-defrecord-protocol', calls('defrecord', 'deftype', 'defprotocol', 'extend-protocol', 'defmulti', 'defmethod', 'reify', 'binding', 'with-redefs', 'letfn', 'lazy-seq', 'delay', 'memoize')),
 ('H12-keyword-fn-call', re.compile(r'\(:[A-Za-z][A-Za-z0-9/._-]*[\s)]')),
 ('H13-fn-literal', re.compile(r'#\(|\(fn[\s\[]')),
]
DEFN = re.compile(r'^\(defn-?[\s]')
rows = []
tot = {}
for rel in FILES:
    cnt = {k: 0 for k, _ in P}
    ndefn = 0
    lines = 0
    for ln, code, raw in strip_file(ROOT + rel):
        lines += 1
        if DEFN.match(code): ndefn += 1
        for k, rx in P:
            cnt[k] += len(rx.findall(code))
    rows.append((rel, lines, ndefn, cnt))
hdr = ['file', 'lines', 'defn_toplevel'] + [k for k, _ in P]
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t'); w.writerow(hdr)
    for rel, lines, nd, cnt in rows:
        w.writerow([rel, lines, nd] + [cnt[k] for k, _ in P])
        print(rel, lines, nd, ' '.join('%s=%d' % (k[:3], cnt[k]) for k, _ in P))
